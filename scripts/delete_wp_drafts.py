#!/usr/bin/env python3
# 批次刪除 WordPress 影片草稿

from dotenv import load_dotenv
import os

# 載入 .env 檔案
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', '.env')
load_dotenv(env_path, override=True)

from wordpress_api import WordPressAPI
from logger import get_workflow_logger

# 請將要刪除的 post_id 填入這個列表
POST_IDS = [
    11306, 11309, 11312, 11315, 11318, 11321, 11324, 11327, 11330, 11333, 11336, 11339, 11342, 11345, 11348, 11351, 11354
]

def main():
    logger = get_workflow_logger('4', 'wp_batch_delete')
    wp = WordPressAPI(logger)
    success, fail = [], []

    for pid in POST_IDS:
        logger.info(f"準備刪除文章 {pid}...")
        if wp.delete_post(pid):
            success.append(pid)
        else:
            fail.append(pid)

    print("\n=== 刪除結果 ===")
    print(f"成功刪除: {success}")
    print(f"刪除失敗: {fail}")

if __name__ == "__main__":
    main()
