from pathlib import Path
import argparse
import asyncio

from nozomi_async.async_api import api

async def dataset(args):
    dataset_path,reports = await nozomi_api.init_dataset(Path(args.path),args.positive_tags,args.negative_tags,args.start_date,args.end_date)
    await nozomi_api.download_dataset(reports,dataset_path)

if __name__=="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", type=str, default=None,help='Path to create a dataset')
    parser.add_argument("--positive_tags", type=str, default=None, nargs='*',help='Positive tags')
    parser.add_argument("--negative_tags", type=str, default=None, nargs='*',help='Negative tags')
    parser.add_argument("--start_date", type=str, default=None, help="Start filter date")
    parser.add_argument("--end_date", type=str, default=None, help="End filter date")
    parser.add_argument("--num_process", type=int, default=1,help='Num of process')
    parser.add_argument("--proxy", type=str, default=None,help='Proxy to use')
    args = parser.parse_args()

    nozomi_api = api(semaphore=args.num_process,proxy=args.proxy)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(dataset(args))
    asyncio.run(nozomi_api.session.close())