#!/usr/bin/env python3
# sync_youtube_links.py

import os
import re
import json
import requests
import gspread
from typing import Dict, List, Optional, Tuple, Any
from dotenv import load_dotenv
from logger import get_workflow_logger
from wordpress_api import WordPressAPI
import google_sheets
from google.oauth2.service_account import Credentials

# 設定日誌
logger = get_workflow_logger('1', 'sync_youtube_links')

def get_sheet(sheet_id: str, sheet_name: str) -> Optional[gspread.Worksheet]:
    """獲取 Google Sheet 工作表
    
    Args:
        sheet_id: Google Sheet ID
        sheet_name: 工作表名稱
        
    Returns:
        gspread.Worksheet: Google Sheet 工作表，如果獲取失敗則返回 None
    """
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        service_account_path = os.path.join(base_dir, creds_path.lstrip('./'))
        
        if not os.path.exists(service_account_path):
            logger.error(f"找不到憑證檔案：{service_account_path}")
            return None
            
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file",
            "https://www.googleapis.com/auth/drive"
        ]
        
        creds = Credentials.from_service_account_file(service_account_path, scopes=scope)
        client = gspread.authorize(creds)
        
        spreadsheet = client.open_by_key(sheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)
        
        logger.info(f"成功獲取 Google Sheet: {sheet_name}")
        return worksheet
        
    except Exception as e:
        logger.error(f"獲取 Google Sheet 失敗: {str(e)}")
        return None

def load_custom_slug_mapping(filename: str = 'custom_slug_mapping.json') -> Dict[str, int]:
    """載入自定義 slug 到 ID 的映射表
    
    Args:
        filename: 映射表文件名
        
    Returns:
        Dict[str, int]: 自定義 slug 到 ID 的映射表
    """
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            mapping = json.load(f)
            
        logger.info(f"已載入 {len(mapping)} 個映射")
        return mapping
        
    except FileNotFoundError:
        logger.error(f"找不到映射表文件: {filename}")
        return {}
        
    except Exception as e:
        logger.error(f"載入映射表時發生錯誤: {str(e)}")
        return {}

def extract_custom_slug_from_url(url: str) -> Optional[str]:
    """從 WordPress URL 中提取自定義 slug
    
    Args:
        url: WordPress 文章 URL
        
    Returns:
        str: 自定義 slug，如果無法提取則返回 None
    """
    try:
        # 嘗試匹配已發布文章 URL (如 https://referee.ad/video/YRdG5pJaDz/)
        match = re.search(r'/video/([a-zA-Z0-9]+)/?', url)
        if match:
            return match.group(1)
            
        # 嘗試匹配編輯器 URL (如 https://referee.ad/wp-admin/post.php?post=7419&action=edit)
        match = re.search(r'post=(\d+)', url)
        if match:
            return match.group(1)
            
        logger.warning(f"無法從 URL 提取自定義 slug 或 ID: {url}")
        return None
        
    except Exception as e:
        logger.error(f"提取自定義 slug 時發生錯誤: {str(e)}")
        return None

def get_post_meta(wp: WordPressAPI, post_id: int) -> Dict[str, Any]:
    """獲取文章的 meta 欄位
    
    Args:
        wp: WordPressAPI 實例
        post_id: 文章 ID
        
    Returns:
        Dict[str, Any]: 文章的 meta 欄位
    """
    try:
        endpoint = f"{wp.api_base}/video/{post_id}"
        response = requests.get(endpoint, auth=wp.auth)
        
        if response.status_code != 200:
            logger.error(f"獲取文章 {post_id} 失敗 - Status: {response.status_code}")
            return {}
            
        data = response.json()
        return data.get('meta', {})
        
    except Exception as e:
        logger.error(f"獲取文章 meta 欄位時發生錯誤: {str(e)}")
        return {}

def update_post_meta(wp: WordPressAPI, post_id: int, meta: Dict[str, Any]) -> bool:
    """更新文章的 meta 欄位
    
    Args:
        wp: WordPressAPI 實例
        post_id: 文章 ID
        meta: 要更新的 meta 欄位
        
    Returns:
        bool: 更新是否成功
    """
    try:
        endpoint = f"{wp.api_base}/video/{post_id}"
        data = {
            'meta': meta
        }
        
        response = requests.post(endpoint, auth=wp.auth, json=data)
        
        if response.status_code not in [200, 201]:
            logger.error(f"更新文章 {post_id} 失敗 - Status: {response.status_code}, Response: {response.text}")
            return False
            
        logger.info(f"成功更新文章 {post_id} 的 meta 欄位")
        return True
        
    except Exception as e:
        logger.error(f"更新文章 meta 欄位時發生錯誤: {str(e)}")
        return False

def sync_youtube_links(sheet_id: str, sheet_name: str, wp_url_column: str, youtube_url_column: str, test_row: int = None, wp_id_column: str = 'I'):
    """同步 YouTube 連結
    
    Args:
        sheet_id: Google Sheet ID
        sheet_name: 工作表名稱
        wp_url_column: WordPress URL 欄位（可以是欄位名稱或列號，如 'H'）
        youtube_url_column: YouTube URL 欄位（可以是欄位名稱或列號，如 'D'）
        test_row: 測試行號，如果提供，則只處理這一行
    """
    try:
        # 載入環境變數
        dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', '.env')
        load_dotenv(dotenv_path)
        
        # 初始化 WordPress API
        wp = WordPressAPI(logger)
        
        # 載入自定義 slug 到 ID 的映射表
        mapping = load_custom_slug_mapping()
        
        if not mapping:
            logger.error("無法載入映射表，請先執行 build_url_mapping.py")
            return
            
        # 獲取 Google Sheet 數據
        logger.info(f"從 Google Sheet 獲取數據: {sheet_id}, {sheet_name}")
        sheet = get_sheet(sheet_id, sheet_name)
        
        if not sheet:
            logger.error("無法獲取 Google Sheet 數據")
            return
            
        # 檢查是否提供了測試行號
        if test_row:
            logger.info(f"只處理第 {test_row} 行")
            # 獲取指定行的數據
            # 列號轉換為字母列號（A=1, B=2, ...）
            col_to_letter = lambda col: chr(ord('A') + int(col) - 1) if col.isdigit() else col
            wp_url_col_letter = col_to_letter(wp_url_column) if wp_url_column.isdigit() else wp_url_column
            youtube_url_col_letter = col_to_letter(youtube_url_column) if youtube_url_column.isdigit() else youtube_url_column
            
            # 獲取指定行的數據
            wp_url = sheet.acell(f"{wp_url_col_letter}{test_row}").value
            youtube_url = sheet.acell(f"{youtube_url_col_letter}{test_row}").value
            wp_id = sheet.acell(f"{wp_id_column}{test_row}").value
            
            logger.info(f"WordPress ID: {wp_id}")
            
            logger.info(f"WordPress URL: {wp_url}")
            logger.info(f"YouTube URL: {youtube_url}")
            
            # 處理單一行
            if not youtube_url:
                logger.warning(f"第 {test_row} 行缺少 YouTube URL，跳過")
                return
                
            if not wp_url and not wp_id:
                logger.warning(f"第 {test_row} 行缺少 WordPress URL 和網站 ID，跳過")
                return
                
            # 獲取文章 ID
            post_id = None
            
            # 優先使用網站 ID 欄位
            if wp_id and wp_id.strip():
                if wp_id.isdigit():
                    post_id = int(wp_id)
                    logger.info(f"從網站 ID 欄位獲取到 ID: {post_id}")
            # 如果沒有網站 ID，則從 WordPress URL 提取
            elif wp_url:
                custom_slug = extract_custom_slug_from_url(wp_url)
                
                if not custom_slug:
                    logger.warning(f"無法從 URL 提取自定義 slug 或 ID: {wp_url}，跳過")
                    return
                    
                # 如果是數字，可能是直接從 URL 提取的 ID
                if custom_slug.isdigit():
                    post_id = int(custom_slug)
                    logger.info(f"從 URL 直接提取到 ID: {post_id}")
                else:
                    # 從映射表中查找 ID
                    post_id = mapping.get(custom_slug)
                
            if not post_id:
                logger.warning(f"無法找到自定義 slug 對應的文章 ID: {custom_slug}，跳過")
                return
                
            # 獲取文章的 meta 欄位
            meta = get_post_meta(wp, post_id)
            
            if not meta:
                logger.warning(f"無法獲取文章 {post_id} 的 meta 欄位，跳過")
                return
                
            # 檢查 video_url 是否需要更新
            current_video_url = meta.get('video_url', '')
            
            if current_video_url == youtube_url:
                logger.info(f"文章 {post_id} 的 video_url 已經是最新的，跳過")
                return
                
            # 更新 video_url
            logger.info(f"更新文章 {post_id} 的 video_url: {current_video_url} -> {youtube_url}")
            meta['video_url'] = youtube_url
            
            # 更新文章的 meta 欄位
            if update_post_meta(wp, post_id, meta):
                logger.info(f"成功更新文章 {post_id} 的 video_url")
            else:
                logger.error(f"更新文章 {post_id} 的 video_url 失敗")
            
            return
        
        # 如果沒有指定測試行，則只處理 H 欄位有值的行
        # 獲取所有 H 欄位的值
        h_column_values = sheet.col_values(8)  # H 欄位是第 8 列（A=1, B=2, ..., H=8）
        logger.info(f"獲取到 {len(h_column_values)} 行 H 欄位數據")
        
        # 同步 YouTube 連結
        updated_count = 0
        skipped_count = 0
        error_count = 0
        
        # 跳過標題行
        for i, wp_url in enumerate(h_column_values[1:], 2):  # 從第 2 行開始，因為第 1 行是標題
            try:
                # 如果 H 欄位空，則跳過
                if not wp_url:
                    skipped_count += 1
                    continue
                    
                # 獲取對應的 D 欄位值（YouTube URL）和 I 欄位值（網站 ID）
                youtube_url = sheet.cell(i, 4).value  # D 欄位是第 4 列（A=1, B=2, C=3, D=4）
                wp_id = sheet.cell(i, 9).value  # I 欄位是第 9 列（A=1, B=2, ..., I=9）
                
                if not youtube_url:
                    logger.warning(f"第 {i} 行缺少 YouTube URL，跳過")
                    skipped_count += 1
                    continue
                    
                if not wp_url and not wp_id:
                    logger.warning(f"第 {i} 行缺少 WordPress URL 和網站 ID，跳過")
                    skipped_count += 1
                    continue
                    
                # 檢查是否為 WordPress 草稿 URL
                is_draft = False
                if "wp-admin/post.php" in wp_url and "action=edit" in wp_url:
                    logger.info(f"第 {i} 行是 WordPress 草稿 URL: {wp_url}")
                    is_draft = True
                
                # 獲取文章 ID
                post_id = None
                
                # 優先使用網站 ID 欄位
                if wp_id and wp_id.strip():
                    if wp_id.isdigit():
                        post_id = int(wp_id)
                        logger.info(f"從網站 ID 欄位獲取到 ID: {post_id}")
                # 如果沒有網站 ID，則從 WordPress URL 提取
                elif wp_url:
                    custom_slug = extract_custom_slug_from_url(wp_url)
                    
                    if not custom_slug:
                        logger.warning(f"無法從 URL 提取自定義 slug 或 ID: {wp_url}，跳過")
                        skipped_count += 1
                        continue
                        
                    # 如果是草稿 URL，則直接使用提取的 ID
                    if is_draft and custom_slug.isdigit():
                        post_id = int(custom_slug)
                        logger.info(f"從草稿 URL 直接提取到 ID: {post_id}")
                    # 如果是數字，可能是直接從 URL 提取的 ID
                    elif custom_slug.isdigit():
                        post_id = int(custom_slug)
                        logger.info(f"從 URL 直接提取到 ID: {post_id}")
                    else:
                        # 從映射表中查找 ID
                        post_id = mapping.get(custom_slug)
                    
                if not post_id:
                    logger.warning(f"無法找到自定義 slug 對應的文章 ID: {custom_slug}，跳過")
                    skipped_count += 1
                    continue
                    
                # 獲取文章的 meta 欄位
                meta = get_post_meta(wp, post_id)
                
                if not meta:
                    logger.warning(f"無法獲取文章 {post_id} 的 meta 欄位，跳過")
                    skipped_count += 1
                    continue
                    
                # 檢查 video_url 是否需要更新
                current_video_url = meta.get('video_url', '')
                
                if current_video_url == youtube_url:
                    logger.info(f"文章 {post_id} 的 video_url 已經是最新的，跳過")
                    skipped_count += 1
                    continue
                    
                # 更新 video_url
                logger.info(f"更新文章 {post_id} 的 video_url: {current_video_url} -> {youtube_url}")
                meta['video_url'] = youtube_url
                
                # 更新文章的 meta 欄位
                if update_post_meta(wp, post_id, meta):
                    updated_count += 1
                else:
                    error_count += 1
                    
            except Exception as e:
                logger.error(f"處理第 {i+2} 行時發生錯誤: {str(e)}")
                error_count += 1
                
        logger.info(f"同步完成: 更新 {updated_count} 篇文章，跳過 {skipped_count} 篇文章，錯誤 {error_count} 篇文章")
        
    except Exception as e:
        logger.error(f"同步 YouTube 連結時發生錯誤: {str(e)}")

def main():
    """主程序"""
    try:
        # 檢查命令列參數
        import sys
        
        if len(sys.argv) < 5:
            print("用法: python sync_youtube_links.py <sheet_id> <sheet_name> <wp_url_column> <youtube_url_column> [test_row] [wp_id_column]")
            print("例如: python sync_youtube_links.py 1abcdefg 'Sheet1' 'H' 'D' 4965 'I'")
            sys.exit(1)
            
        # 獲取參數
        sheet_id = sys.argv[1]
        sheet_name = sys.argv[2]
        wp_url_column = sys.argv[3]
        youtube_url_column = sys.argv[4]
        
        # 檢查是否提供了測試行號和網站 ID 欄位
        test_row = None
        wp_id_column = 'I'  # 默認使用 I 欄位
        
        if len(sys.argv) > 5:
            test_row = int(sys.argv[5])
            print(f"只處理第 {test_row} 行")
            
        if len(sys.argv) > 6:
            wp_id_column = sys.argv[6]
            print(f"使用 {wp_id_column} 欄位作為網站 ID")
        
        # 同步 YouTube 連結
        sync_youtube_links(sheet_id, sheet_name, wp_url_column, youtube_url_column, test_row, wp_id_column)
        
    except Exception as e:
        logger.error(f"執行過程中發生錯誤: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
