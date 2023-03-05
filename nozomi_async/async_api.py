"""Web Async API functions."""

import logging
import struct
import json
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Union

import aiohttp
import asyncio
from dacite import from_dict
import tqdm

from .data import Post
from .exceptions import InvalidTagFormat, InvalidUrlFormat,InvalidDateFormat
from .helpers import sanitize_tag, create_tag_filepath, create_post_filepath, parse_post_id, solve_date


_LOGGER = logging.getLogger(__name__)


class api:
    def __init__(self,semaphore:int,proxy:str) -> None:
        '''
        semaphore: number of process
        proxy: proxy to use
        '''
        self.semaphore = asyncio.Semaphore(semaphore)
        self.proxy = proxy
        self.session = aiohttp.ClientSession()
        self.pbar = None

    async def get_post(self,url: str) -> Post:
        """Retrieve a single post.

        Args:
            url: The URL of the post to retrieve.

        Returns:
            A post in JSON format if it exists.

        """
        _LOGGER.debug('Retrieving a post from URL "%s"', url)
        try:
            post_id = parse_post_id(url)
            post_url = create_post_filepath(post_id)
            resp = await self.session.get(post_url,proxy=self.proxy)
            post_data = await resp.json()
            _LOGGER.debug(post_data)
            return from_dict(data_class=Post, data=post_data)
        except InvalidUrlFormat:
            raise
        except Exception as ex:
            _LOGGER.exception(ex)
            raise


    async def get_posts(self,positive_tags: List[str], negative_tags: List[str]=None, progress:bool=True) -> Iterable[Post]:
        """Retrieve all post data that contains and doesn't contain certain tags.

        Args:
            positive_tags: The tags that the posts retrieved must contain.
            negative_tags: Optional, blacklisted tags.
            progress: Display progress bar

        Yields:
            A post in JSON format, which contains the positive tags and doesn't contain the negative
            tags.

        """
        async def post(post_url):
            async with self.semaphore:
                resp = await self.session.get(post_url,proxy=self.proxy)
                post_data = await resp.json()
            if type(self.pbar)==tqdm.tqdm:
                self.pbar.update(1)
            _LOGGER.debug(post_data)
            if post_data["date"] is not None:
                return from_dict(data_class=Post, data=post_data)
            else:
                _LOGGER.debug('Skip missing tags post')

        if negative_tags is None:
            negative_tags = list()
        _LOGGER.debug('Retrieving posts with positive_tags=%s and negative_tags=%s',
                    str(positive_tags), str(negative_tags))
        try:
            positive_post_urls = await self._get_post_urls(positive_tags)
            negative_post_urls = await self._get_post_urls(negative_tags)
            relevant_post_urls = set(positive_post_urls) - set(negative_post_urls)
            if progress:
                self.pbar = tqdm.tqdm(relevant_post_urls,desc="Initialize Dataset:")
            return await asyncio.gather(*[post(post_url) for post_url in relevant_post_urls])
        except InvalidTagFormat:
            raise
        except Exception as ex:
            _LOGGER.exception(ex)
            raise


    async def download_media(self,post: Post, filepath: Path) -> List[str]:
        """Download all media on a post and save it.

        Args:
            post: The post to download.
            filepath: The file directory to save the media. The directory will be created if it doesn't
                already exist.

        Returns:
            The names of the images downloaded.

        """
        images_downloaded = []
        filepath.mkdir(parents=True, exist_ok=True)
        for media_meta_data in post.imageurls:
            image_url = media_meta_data.imageurl
            image_name = image_url.split('/')[-1]
            image_filepath = filepath.joinpath(image_name)
            await self._download_media(image_url, image_filepath)
            images_downloaded.append(image_name)
        return images_downloaded


    async def _download_media(self,image_url: str, filepath: Path):
        """Download an image and save it.

        Args:
            image_url: The image URL.
            filepath: The file directory to save the media. The directory will be created if it doesn't
                already exist.

        """
        headers = {
            'Host': 'i.nozomi.la',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:69.0) Gecko/20100101 Firefox/69.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,/;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Referer': 'https://nozomi.la/',
            'Upgrade-Insecure-Requests': '1',
            'TE': 'Trailers',
            'Pragma': 'no-cache',
            'Cache-Control': 'no-cache'
        }
        # with requests.get(image_url, stream=True, headers=headers) as r:
        # async with self.session.get(image_url, headers=headers, proxy=self.proxy) as r:
        #     with open(filepath, 'wb') as f:
        #         shutil.copyfileobj(r.raw, f)
        async with self.semaphore:
            file = await self.session.get(image_url,proxy=self.proxy,headers=headers)
            total = int(file.headers.get('content-length', 0))
            basename = filepath.stem
            with open(filepath, 'wb') as f,tqdm.tqdm(desc=basename,total=total,
                    unit='iB',unit_scale=True,unit_divisor=1024,leave=None) as bar:
                async for data in file.content.iter_chunked(1024):
                    size = f.write(data)
                    bar.update(size)
        _LOGGER.debug('Image downloaded %s', filepath)

    async def _get_post_urls(self,tags: List[str]) -> List[str]:
        """Retrieve the links to all of the posts that contain the tags.

        Args:
            tags: The tags that the posts must contain.

        Returns:
            A list of post urls that contain all of the specified tags.

        """
        if len(tags) == 0: return tags
        _LOGGER.debug('Retrieving all URLs that contain the tags %s', str(tags))
        sanitized_tags = [sanitize_tag(tag) for tag in tags]
        nozomi_urls  = [create_tag_filepath(sanitized_tag) for sanitized_tag in sanitized_tags]
        tag_post_ids = [await self._get_post_ids(nozomi_url) for nozomi_url in nozomi_urls]
        tag_post_ids = set.intersection(*map(set, tag_post_ids)) # Flatten list of tuples on intersection
        post_urls = [create_post_filepath(post_id) for post_id in tag_post_ids]
        _LOGGER.debug('Got %d post urls containing the tags %s', len(tags), str(tags))
        return post_urls

    async def _get_post_ids(self,tag_filepath_url: str) -> List[int]:
        """Retrieve the .nozomi data file.

        Args:
            tag_filepath_url: The URL to a tag's .nozomi file.

        Returns:
            A list containing all of the post IDs that contain the tag.

        """
        _LOGGER.debug('Getting post IDs from %s', tag_filepath_url)
        try:
            headers = {'Accept-Encoding': 'gzip, deflate, br', 'Content-Type': 'arraybuffer'}
            async with self.session.get(tag_filepath_url, headers=headers, proxy=self.proxy) as response:
                _LOGGER.debug('RESPONSE: %s', response)
                content = await response.read()
                total_ids = len(content) // 4  # divide by the size of uint
                _LOGGER.info('Unpacking .nozomi file... Expecting %d post ids.', total_ids)
                post_ids = list(struct.unpack(f'!{total_ids}I', bytearray(content)))
                _LOGGER.debug('Unpacked data... Got %d total post ids! %s', len(post_ids), str(post_ids))
        except Exception as ex:
            _LOGGER.exception(ex)
        return post_ids
    
    async def write_tags(self,post:Post, filepath:Path):
        """Download all tags on a post and save it.

            Args:
                post: The post to download.
                filepath: The file directory to save the media. The directory will be created if it doesn't
                    already exist.
        """
        tag_name = post.dataid+".txt"
        tag_filepath = filepath.joinpath(tag_name)
        tags = ' '.join([Tag.tag for Tag in post.general])
        with open(tag_filepath,"w") as txt:
            txt.write(tags) 

    async def init_dataset(self,
                           path: Path, positive_tags: List[str], negative_tags: List[str] = None,
                           start_date: str = None, end_date: str = None
                           )->Union[Path,List[Post]]:
        """ Initialize a dataset and writing posts' metadata to metadata.json 
        Args:
            path: Dataset dir to save imgs and tags
            positive_tags: The tags that the posts retrieved must contain.
            negative_tags: Optional, blacklisted tags.
            start_date: Start filter date (2022-02-22 etc)
            end_date: End filter date (2022-02-22 etc)
        Return:
            dataset_path: dataset_dir
            reports: Posts to download to dataset
        """
        # Initialize dataset
        metadata = {"positive_tags": positive_tags, "negative_tags": negative_tags,
                    "start_date": start_date, "end_date": end_date, "posts": []}
        if (start_date is not None) and (end_date is not None):
            try:
                start_date, end_date = datetime.strptime(start_date, '%Y-%m-%d'), datetime.strptime(end_date, '%Y-%m-%d')
            except:
                raise InvalidDateFormat
        dataset_name = "__".join(positive_tags)
        dataset_path = path.joinpath(dataset_name)
        dataset_path.mkdir(parents=True, exist_ok=True)
        # create metadata
        reports = []
        posts = await self.get_posts(positive_tags, negative_tags)
        for post in posts:
            if post:
                date_object = datetime.strptime("-".join(post.date.split("-")[:-1]), '%Y-%m-%d %H:%M:%S')
                if solve_date(date_object,start_date,end_date):
                    metadata["posts"].append(post.dict())
                    reports.append(post)
        metadata["post_count"] = len(metadata["posts"])
        with open(dataset_path.joinpath("metadata.json"), "w") as meta:
            json.dump(metadata, meta, indent=3, ensure_ascii=False, sort_keys=True)
        return dataset_path,reports
    
    async def download_dataset(self,posts:List[Post],path:Path,progress:bool=True):
        """ Download pictures and positive_tags to a dataset in .txt refer to metadata.json 
        Args:
            posts: List of Posts to download
            path: dataset dir to save imgs and tags
        """
        async def download_img_tags(post:Post,path:Path):
            await self.download_media(post,path)
            await self.write_tags(post,path)
            self.pbar.update(1)
        if progress:
            self.pbar = tqdm.tqdm(posts,desc="Download Posts:")
        await asyncio.gather(*[download_img_tags(post,path) for post in posts])