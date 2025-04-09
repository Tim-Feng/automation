#!/usr/bin/env python3
# test_custom_slug.py
#
# 歸檔說明：
# 這是一個測試腳本，用於測試根據自定義 slug 獲取 WordPress 文章的功能。
# 創建日期：2025-04-09 之前
# 作者：Cascade
#
# 用途：
# 該腳本用於測試從 WordPress URL 中提取自定義 slug，並根據該 slug 查詢文章資訊的功能。
# 它是在開發 sync_youtube_links.py 腳本時用於測試和驗證的輔助工具。
#
# 歸檔原因：
# 我們已經將工作流程修改為在文章創建時直接記錄 ID 到 Google Sheets 的 I 欄位，
# 因此不再需要使用自定義 slug 來查找文章 ID。
# 保留此腳本作為參考，以便將來可能需要類似的功能。

import os
import sys
import requests
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from logger import get_workflow_logger
from wordpress_api import WordPressAPI

# 設定日誌
logger = get_workflow_logger('1', 'test_custom_slug')

def get_post_by_custom_slug(wp: WordPressAPI, custom_slug: str) -> Optional[Dict[str, Any]]:
    """根據自定義 slug 獲取文章資訊
    
    Args:
        wp: WordPressAPI 實例
        custom_slug: 自定義 slug（如 YRdG5pJaDz）
        
    Returns:
        Dict[str, Any]: 文章資訊，如果獲取失敗則返回 None
    """
    try:
        # 嘗試方法 1: 使用標準 slug 參數查詢
        logger.info(f"嘗試使用標準 slug 參數查詢: {custom_slug}")
        endpoint = f"{wp.api_base}/video"
        params = {
            'slug': custom_slug
        }
        
        response = requests.get(endpoint, auth=wp.auth, params=params)
        logger.info(f"回應狀態碼: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"回應資料長度: {len(data) if isinstance(data, list) else '非列表'}")
            
            if data and isinstance(data, list) and len(data) > 0:
                return data[0]
        
        # 嘗試方法 2: 使用搜索 API
        logger.info(f"嘗試使用搜索 API: {custom_slug}")
        endpoint = f"{wp.site_url}/wp-json/wp/v2/search"
        params = {
            'search': custom_slug,
            'per_page': 20,
            'type': 'post'
        }
        
        response = requests.get(endpoint, auth=wp.auth, params=params)
        logger.info(f"回應狀態碼: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"搜索結果: {len(data)} 項")
            
            if data and len(data) > 0:
                # 搜索結果通常只包含 ID 和 URL，需要再次查詢完整資訊
                for item in data:
                    if custom_slug in item.get('url', ''):
                        post_id = item.get('id')
                        logger.info(f"找到匹配的文章 ID: {post_id}")
                        return get_post_by_id(wp, post_id)
        
        # 嘗試方法 3: 獲取所有文章並過濾
        logger.info(f"嘗試獲取所有文章並過濾: {custom_slug}")
        endpoint = f"{wp.api_base}/video"
        params = {
            'per_page': 100
        }
        
        response = requests.get(endpoint, auth=wp.auth, params=params)
        logger.info(f"回應狀態碼: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"獲取到 {len(data)} 篇文章")
            
            for post in data:
                link = post.get('link', '')
                if custom_slug in link:
                    logger.info(f"找到匹配的文章: {post.get('id')}")
                    return post
            
            # 檢查是否有下一頁
            headers = response.headers
            if 'X-WP-TotalPages' in headers and int(headers['X-WP-TotalPages']) > 1:
                logger.info(f"文章有多頁，但目前只檢查了第一頁")
        
        logger.error(f"無法找到匹配自定義 slug 的文章: {custom_slug}")
        return None
        
    except Exception as e:
        logger.error(f"獲取文章時發生錯誤: {str(e)}")
        return None

def get_post_by_id(wp: WordPressAPI, post_id: int) -> Optional[Dict[str, Any]]:
    """根據 ID 獲取文章資訊
    
    Args:
        wp: WordPressAPI 實例
        post_id: 文章 ID
        
    Returns:
        Dict[str, Any]: 文章資訊，如果獲取失敗則返回 None
    """
    try:
        endpoint = f"{wp.api_base}/video/{post_id}"
        response = requests.get(endpoint, auth=wp.auth)
        
        if response.status_code != 200:
            logger.error(f"獲取文章 {post_id} 失敗 - Status: {response.status_code}")
            return None
            
        return response.json()
        
    except Exception as e:
        logger.error(f"獲取文章 {post_id} 時發生錯誤: {str(e)}")
        return None

def main():
    """主程序"""
    try:
        # 載入環境變數
        dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', '.env')
        load_dotenv(dotenv_path)
        
        # 檢查命令列參數
        if len(sys.argv) < 2:
            logger.error("請提供自定義 slug 作為參數")
            sys.exit(1)
            
        # 獲取自定義 slug
        custom_slug = sys.argv[1]
        logger.info(f"測試自定義 slug: {custom_slug}")
        
        # 初始化 WordPress API
        wp = WordPressAPI(logger)
        
        # 獲取文章資訊
        post_data = get_post_by_custom_slug(wp, custom_slug)
        
        if not post_data:
            logger.error(f"無法獲取匹配自定義 slug 的文章: {custom_slug}")
            sys.exit(1)
            
        # 提取資訊
        post_id = post_data.get('id')
        slug = post_data.get('slug')
        title = post_data.get('title', {}).get('rendered', '')
        status = post_data.get('status', '')
        link = post_data.get('link', '')
        
        logger.info(f"文章 ID: {post_id}")
        logger.info(f"文章 slug: {slug}")
        logger.info(f"文章標題: {title}")
        logger.info(f"文章狀態: {status}")
        logger.info(f"文章連結: {link}")
        
        # 提取 meta 欄位
        meta = post_data.get('meta', {})
        video_url = meta.get('video_url', '')
        
        logger.info(f"文章 video_url: {video_url}")
        
    except Exception as e:
        logger.error(f"執行過程中發生錯誤: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
