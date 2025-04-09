#!/usr/bin/env python3
# test_id_to_slug.py
#
# 歸檔說明：
# 這是一個測試腳本，用於測試根據文章 ID 獲取 WordPress 文章的功能。
# 創建日期：2025-04-09 之前
# 作者：Cascade
#
# 用途：
# 該腳本用於測試根據文章 ID 查詢 WordPress 文章資訊的功能。
# 它是在開發 sync_youtube_links.py 腳本時用於測試和驗證的輔助工具。
#
# 歸檔原因：
# 我們已經將工作流程修改為在文章創建時直接記錄 ID 到 Google Sheets 的 I 欄位，
# 因此不再需要這個測試腳本。
# 保留此腳本作為參考，以便將來可能需要類似的功能。

import os
import sys
import requests
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from logger import get_workflow_logger
from wordpress_api import WordPressAPI

# 設定日誌
logger = get_workflow_logger('1', 'test_id_to_slug')

def get_post_by_id(wp: WordPressAPI, post_id: int) -> Optional[Dict[str, Any]]:
    """根據 ID 獲取文章資訊
    
    Args:
        wp: WordPressAPI 實例
        post_id: 文章 ID
        
    Returns:
        Dict[str, Any]: 文章資訊，如果獲取失敗則返回 None
    """
    try:
        # 構建 API 端點
        endpoint = f"{wp.api_base}/video/{post_id}"
        
        # 發送請求
        response = requests.get(endpoint, auth=wp.auth)
        
        if response.status_code != 200:
            logger.error(f"獲取文章 {post_id} 失敗 - Status: {response.status_code}, Response: {response.text}")
            return None
            
        # 解析回應
        data = response.json()
        return data
        
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
            logger.error("請提供文章 ID 作為參數")
            sys.exit(1)
            
        # 獲取文章 ID
        try:
            post_id = int(sys.argv[1])
        except ValueError:
            logger.error(f"無效的文章 ID: {sys.argv[1]}")
            sys.exit(1)
            
        logger.info(f"測試文章 ID: {post_id}")
        
        # 初始化 WordPress API
        wp = WordPressAPI(logger)
        
        # 獲取文章資訊
        post_data = get_post_by_id(wp, post_id)
        
        if not post_data:
            logger.error(f"無法獲取文章 {post_id} 的資訊")
            sys.exit(1)
            
        # 提取 slug
        slug = post_data.get('slug')
        
        if not slug:
            logger.error(f"文章 {post_id} 沒有 slug")
            sys.exit(1)
            
        logger.info(f"文章 {post_id} 的 slug: {slug}")
        
        # 提取其他有用的資訊
        title = post_data.get('title', {}).get('rendered', '')
        status = post_data.get('status', '')
        link = post_data.get('link', '')
        
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
