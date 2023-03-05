# NozomiPy-Async
Async nozomi.la API for Python3.

NozomiPy-Async is an Async Python3 library for nozomi.la API.

NozomiPy-Async also provides a commandline tool to download images and tags from nozomi.la.

Based on Python-Nozomi: https://github.com/Alfa-Q/python-nozomi

## Install
```
pip install nozomipy-async
```

## Import packages
```python
from nozomipy.async_api import api
```

## API Usages
### API init
```python
import asyncio
from nozomipy.async_api import api

nozomi_api = api(semaphore=8,proxy="http://127.0.0.1:1080")
```

### Download images
```python
# The tags that the posts retrieved must contain
positive_tags = ['veigar', 'wallpaper']

# Gets all posts with the tags 'veigar', 'wallpaper'
posts = await nozomi_api.get_posts()
# download all images
await asyncio.gather(*[download_img_tags(post,path) for post in posts])
```

## Create dataset
Download images and tags during a period to a folder named with positive tags.
```bash
nozomi --path "./" --positive_tags 'miyase_mahiro' --start_date 2022-02-22 --end_date 2022-01-22 --num_process=8 --proxy http://127.0.0.1:7890
```