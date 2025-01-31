#!/usr/bin/env python3
# upload_vtt.py

import os
import sys
from pathlib import Path
import re
from dotenv import load_dotenv
from logger import setup_logger
from wordpress_api import WordPressAPI
from google_sheets import setup_google_sheets

def get_post_id_from_sheets(video_id: str, logger) -> int:
    """從 Google Sheets H 欄取得 WordPress 文章 ID"""
    sheet = setup_google_sheets()
    all_values = sheet.get_all_values()
    
    # 搜尋符合的影片 ID
    for row in all_values[2:]:  # 跳過前兩行標題
        if row[0].strip() == video_id:
            if not row[7].strip():
                logger.error(f"影片 {video_id} 在 Google Sheets 中沒有 WordPress 連結")
                return None
                
            wp_url = row[7].strip()
            logger.info(f"找到 WordPress 連結: {wp_url}")
            
            # 從 URL 提取文章 ID
            match = re.search(r'[?&](?:post|p)=(\d+)', wp_url)
            if match:
                post_id = match.group(1) or match.group(2)
                logger.info(f"解析出文章 ID: {post_id}")
                return int(post_id)
            else:
                logger.error(f"無法從連結解析出文章 ID: {wp_url}")
                return None
    
    logger.error(f"在 Google Sheets 中找不到影片 ID: {video_id}")
    return None

def find_vtt_files(folder_path: str, video_id: str, logger) -> list:
    """找出指定資料夾中符合影片 ID 的 VTT 檔案"""
    vtt_files = []
    folder = Path(folder_path)
    
    logger.info(f"搜尋資料夾: {folder}")
    pattern = f"{video_id}*.vtt"
    logger.info(f"搜尋 pattern: {pattern}")
    
    # 搜尋所有符合格式的 VTT 檔案
    for vtt_file in folder.glob(pattern):
        logger.info(f"找到 VTT 檔案: {vtt_file}")
        vtt_files.append(vtt_file)
    
    if not vtt_files:
        logger.error(f"在 {folder} 中找不到符合 {pattern} 的檔案")
        
    return vtt_files

def main():
    if len(sys.argv) < 3:
        print("Usage: upload_vtt.py <folder_path> <video_ids>")
        sys.exit(1)
        
    # 設定環境變數和 logger
    dotenv_path = Path(__file__).parent.parent / 'config' / '.env'
    load_dotenv(str(dotenv_path))
    logger = setup_logger('wordpress_upload')
    
    folder_path = sys.argv[1]
    video_ids = sys.argv[2].split()  # 支援多個影片 ID
    
    logger.info(f"處理資料夾: {folder_path}")
    logger.info(f"處理影片 ID: {video_ids}")
    
    wp = WordPressAPI(logger)
    
    for video_id in video_ids:
        logger.info(f"開始處理影片 ID: {video_id}")
        
        # 直接從 Google Sheets 取得 WordPress 文章 ID
        post_id = get_post_id_from_sheets(video_id, logger)
        if not post_id:
            continue
            
        # 找出所有相關的 VTT 檔案
        vtt_files = find_vtt_files(folder_path, video_id, logger)
        if not vtt_files:
            continue
            
        # 上傳每個 VTT 檔案
        for vtt_file in vtt_files:
            try:
                result = wp.upload_vtt(post_id, vtt_file)
                logger.info(f"上傳結果: {result}")
            except Exception as e:
                logger.error(f"上傳字幕 {vtt_file.name} 失敗: {str(e)}")

if __name__ == "__main__":
    main()