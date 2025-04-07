#!/usr/bin/env python3
"""
同步 Google Sheets 和 WordPress 之間的 YouTube 連結。
"""
import os
import re
import sys
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv
import requests
from logger import get_workflow_logger
from wordpress_api import WordPressAPI
from google_sheets import setup_google_sheets

# 設定日誌
logger = get_workflow_logger('1', 'sync_youtube_links')

def extract_post_id(wp_url: str) -> Optional[int]:
    """從 WordPress URL 中提取文章 ID
    
    Args:
        wp_url: WordPress 文章 URL
        
    Returns:
        int: 文章 ID，如果無法提取則返回 None
    """
    # 支援兩種格式：
    # 1. https://referee.ad/wp-admin/post.php?post=9852&action=edit
    # 2. https://referee.ad/?post_type=video&p=10571
    try:
        # 嘗試提取 post 參數
        post_match = re.search(r'[?&]post=(\d+)', wp_url)
        if post_match:
            return int(post_match.group(1))
            
        # 嘗試提取 p 參數
        p_match = re.search(r'[?&]p=(\d+)', wp_url)
        if p_match:
            return int(p_match.group(1))
            
        return None
    except Exception as e:
        logger.error(f"提取文章 ID 時發生錯誤: {str(e)}")
        return None

def get_wordpress_video_url(wp: WordPressAPI, post_id: int) -> Optional[str]:
    """從 WordPress 文章中獲取 YouTube 連結
    
    Args:
        wp: WordPressAPI 實例
        post_id: 文章 ID
        
    Returns:
        str: YouTube 連結，如果找不到則返回 None
    """
    try:
        endpoint = f"{wp.api_base}/video/{post_id}"
        response = requests.get(endpoint, auth=wp.auth)
        
        if response.status_code != 200:
            logger.error(f"獲取文章失敗 - Status: {response.status_code}, Response: {response.text}")
            return None
            
        post_data = response.json()
        return post_data.get('meta', {}).get('video_url')
        
    except Exception as e:
        logger.error(f"獲取文章 {post_id} 的 YouTube 連結時發生錯誤: {str(e)}")
        return None

def update_wordpress_video_url(wp: WordPressAPI, post_id: int, video_url: str) -> bool:
    """更新 WordPress 文章的 YouTube 連結
    
    Args:
        wp: WordPressAPI 實例
        post_id: 文章 ID
        video_url: 新的 YouTube 連結
        
    Returns:
        bool: 是否更新成功
    """
    try:
        endpoint = f"{wp.api_base}/video/{post_id}"
        data = {
            'meta': {
                'video_url': video_url
            }
        }
        
        response = requests.post(endpoint, auth=wp.auth, json=data)
        
        if response.status_code != 200:
            logger.error(f"更新文章失敗 - Status: {response.status_code}, Response: {response.text}")
            return False
            
        logger.info(f"成功更新文章 {post_id} 的 YouTube 連結")
        return True
        
    except Exception as e:
        logger.error(f"更新文章 {post_id} 的 YouTube 連結時發生錯誤: {str(e)}")
        return False

def process_row(wp: WordPressAPI, sheet, row: int) -> Tuple[bool, str]:
    """處理單行資料
    
    Args:
        wp: WordPressAPI 實例
        sheet: Google Sheet worksheet
        row: 行號
        
    Returns:
        Tuple[bool, str]: (是否成功, 狀態訊息)
    """
    try:
        # 讀取 WordPress URL（H 欄）和 YouTube 連結（D 欄）
        wp_url = sheet.cell(row, 8).value  # H 欄
        sheets_video_url = sheet.cell(row, 4).value  # D 欄
        
        if not wp_url or not sheets_video_url:
            return False, "缺少必要資料"
            
        # 提取文章 ID
        post_id = extract_post_id(wp_url)
        if not post_id:
            return False, f"無法從 URL 提取文章 ID: {wp_url}"
            
        # 獲取 WordPress 中的 YouTube 連結
        wp_video_url = get_wordpress_video_url(wp, post_id)
        if not wp_video_url:
            return False, f"無法獲取文章 {post_id} 的 YouTube 連結"
            
        # 比較連結
        if wp_video_url != sheets_video_url:
            # 更新 WordPress 中的連結
            if update_wordpress_video_url(wp, post_id, sheets_video_url):
                return True, f"已更新文章 {post_id} 的 YouTube 連結"
            else:
                return False, f"更新文章 {post_id} 的 YouTube 連結失敗"
        else:
            return True, "連結相同，無需更新"
            
    except Exception as e:
        return False, f"處理時發生錯誤: {str(e)}"

def main():
    """主程序"""
    try:
        # 載入環境變數
        load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'config', '.env'))
        
        # 初始化 WordPress API
        wp = WordPressAPI(logger)
        
        # 連接 Google Sheets
        sheet = setup_google_sheets()
        if not sheet:
            logger.error("無法連接 Google Sheets")
            return 1
            
        # 取得所有資料（跳過標題列）
        all_rows = sheet.get_all_values()[2:]  # 跳過前兩行
        total = len(all_rows)
        updated = 0
        errors = 0
        
        logger.info(f"開始處理 {total} 筆資料")
        
        # 處理每一行
        for i, _ in enumerate(all_rows, start=3):  # 從第 3 行開始
            success, message = process_row(wp, sheet, i)
            if success:
                if "已更新" in message:
                    updated += 1
                logger.info(f"Row {i}: {message}")
            else:
                errors += 1
                logger.error(f"Row {i}: {message}")
                
        logger.info(f"處理完成！總計 {total} 筆資料，更新 {updated} 筆，錯誤 {errors} 筆")
        return 0
        
    except Exception as e:
        logger.error(f"執行過程中發生錯誤：{str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
