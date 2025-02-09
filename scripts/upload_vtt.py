#!/usr/bin/env python3
# upload_vtt.py

import os
import sys
from pathlib import Path
import re
from dotenv import load_dotenv
from logger import get_workflow_logger
from wordpress_api import WordPressAPI
from google_sheets import setup_google_sheets

logger = get_workflow_logger('3', 'vtt_uploader')  # Stage 3 因為這是字幕處理階段

def get_post_id_from_sheets(video_id: str) -> int:
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
            
            # 從 URL 提取文章 ID
            match = re.search(r'[?&](?:post|p)=(\d+)', wp_url)
            if match:
                post_id = match.group(1) or match.group(2)
                return int(post_id)
            else:
                logger.error(f"無法從連結解析出文章 ID: {wp_url}")
                return None
    
    logger.error(f"在 Google Sheets 中找不到影片 ID: {video_id}")
    return None

def find_vtt_files(folder_path: str, video_id: str) -> list:
    """找出指定資料夾中符合影片 ID 的 VTT 檔案"""
    vtt_files = []
    folder = Path(folder_path)
    
    pattern = f"{video_id}*.vtt"
    
    for vtt_file in folder.glob(pattern):
        vtt_files.append(str(vtt_file))
        
    if not vtt_files:
        logger.error(f"找不到符合的 VTT 檔案: {pattern}")
        
    return vtt_files

def _extract_key_info(response: dict) -> dict:
    """從 WordPress API 響應中提取關鍵信息"""
    if not response:
        return {}
    return {
        'id': response.get('id'),
        'status': response.get('status'),
        'type': response.get('type'),
        'link': response.get('link'),
        'title': response.get('title', {}).get('raw') if isinstance(response.get('title'), dict) else response.get('title'),
        'meta': response.get('meta', {})
    }

def main():
    if len(sys.argv) < 3:
        print("Usage: upload_vtt.py <folder_path> <video_ids>")
        sys.exit(1)
        
    # 設定環境變數
    dotenv_path = Path(__file__).parent.parent / 'config' / '.env'
    load_dotenv(str(dotenv_path))
    
    folder_path = sys.argv[1]
    video_ids = sys.argv[2].split()  # 支援多個影片 ID
    
    wp = WordPressAPI(logger)
    
    for video_id in video_ids:
        # 直接從 Google Sheets 取得 WordPress 文章 ID
        post_id = get_post_id_from_sheets(video_id)
        if not post_id:
            continue
            
        # 找出所有相關的 VTT 檔案
        vtt_files = find_vtt_files(folder_path, video_id)
        if not vtt_files:
            continue
            
        # 上傳每個 VTT 檔案
        for vtt_file in vtt_files:
            try:
                # 從檔名判斷語系
                lang = Path(vtt_file).stem.split('-')[-1]
                
                # 上傳字幕檔案
                upload_result = wp.upload_vtt(post_id, vtt_file)
                if not upload_result:
                    continue
                
                # 移除重複的 log，因為 stage3-subtitling.applescript 已經有相同的 log
            except Exception as e:
                logger.error(f"上傳字幕 {vtt_file} 失敗: {str(e)}")

if __name__ == "__main__":
    main()