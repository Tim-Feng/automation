#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import logging
import argparse
import requests
from dotenv import load_dotenv
from wordpress_api import WordPressAPI
from tag_suggestion import TagSuggester

# 載入環境變數
load_dotenv('../config/.env')

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s ℹ️ [Stage-1] [manual_test] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('manual_test')

# 初始化 WordPress API
wp_api = WordPressAPI(logger)

# 設定命令行參數
def parse_args():
    parser = argparse.ArgumentParser(description='測試 WordPress 文章標籤更新功能')
    parser.add_argument('post_id', type=int, help='要測試的文章 ID')
    parser.add_argument('--title', type=str, help='文章標題，如果不提供則從 WordPress 中獲取')
    parser.add_argument('--content', type=str, help='文章內容，如果不提供則從 WordPress 中獲取')
    return parser.parse_args()

# 取得命令行參數
args = parse_args()
post_id = args.post_id

# 如果沒有提供標題或內容，則從 WordPress 中獲取
if not args.title or not args.content:
    logger.info(f"從 WordPress 獲取文章 {post_id} 的資料")
    try:
        response = requests.get(
            f"{wp_api.api_base}/video/{post_id}?_fields=title,content",
            auth=wp_api.auth,
            headers=wp_api.headers
        )
        if response.status_code == 200:
            data = response.json()
            title = args.title or data.get('title', {}).get('rendered', '')
            content = args.content or data.get('content', {}).get('rendered', '')
            # 移除 HTML 標籤
            import re
            content = re.sub('<[^<]+?>', '', content)
            logger.info(f"成功獲取文章資料: {title[:30]}...")
        else:
            logger.error(f"無法獲取文章資料: {response.status_code}")
            sys.exit(1)
    except Exception as e:
        logger.error(f"獲取文章資料時發生錯誤: {str(e)}")
        sys.exit(1)
else:
    title = args.title
    content = args.content

# 初始化標籤建議器
tag_suggester = TagSuggester()

# 生成標籤
logger.info(f"開始為文章 {post_id} 生成標籤")
tags_result = tag_suggester.suggest_tags(title, content)
logger.info(f"生成的標籤: {tags_result}")

# 轉換標籤為 ID 並更新
if 'existing_tags' in tags_result and 'new_tag_suggestions' in tags_result:
    tag_ids = wp_api.convert_tags_to_ids(tags_result)
    logger.info(f"轉換後的標籤 ID: {tag_ids}")
    
    if tag_ids:
        result = wp_api.update_post_tags(post_id, tag_ids)
        logger.info(f"標籤更新結果: {result}")
    else:
        logger.error("沒有有效的標籤 ID，無法更新文章標籤")
else:
    logger.error("標籤生成失敗，無法更新文章標籤")

# 驗證標籤是否已關聯到文章
response = requests.get(f"{wp_api.api_base}/video/{post_id}?_fields=video_tag", auth=wp_api.auth, headers=wp_api.headers)
if response.status_code == 200:
    data = response.json()
    logger.info(f"文章 {post_id} 的標籤: {data.get('video_tag', [])}")
else:
    logger.error(f"無法獲取文章 {post_id} 的標籤: {response.status_code}")
