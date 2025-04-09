#!/usr/bin/env python3
# fill_wp_id.py
#
# 歸檔說明：
# 這是一個一次性腳本，用於從 WordPress URL 中提取文章 ID 並填充到 Google Sheets 的 I 欄位（網站 ID）。
# 創建日期：2025-04-09
# 作者：Cascade
#
# 用途：
# 該腳本通過分析 Google Sheets 中的 WordPress URL（H 欄位），提取文章 ID 並填充到 I 欄位。
# 它支持兩種 URL 格式：
# 1. 已發布文章 URL（如 https://referee.ad/video/YRdG5pJaDz/）
# 2. 草稿 URL（如 https://referee.ad/wp-admin/post.php?post=7419&action=edit）
#
# 歸檔原因：
# 此腳本已完成其一次性任務，填充了現有的 Google Sheets 數據。
# 未來的工作流程已修改為在文章創建時直接記錄 ID，因此不再需要這個腳本進行批量處理。
# 保留此腳本作為參考，以便將來可能需要類似的批量處理功能。

import os
import re
import json
import gspread
from typing import Dict, List, Optional, Tuple, Any
from dotenv import load_dotenv
from logger import get_workflow_logger
from google.oauth2.service_account import Credentials

# 設定日誌
logger = get_workflow_logger('1', 'fill_wp_id')

def get_sheet(sheet_id: str, sheet_name: str) -> Optional[gspread.Worksheet]:
    """獲取 Google Sheet 工作表"""
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
    """載入自定義 slug 到 ID 的映射表"""
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
    """從 WordPress URL 中提取自定義 slug"""
    try:
        # 嘗試匹配已發布文章 URL (如 https://referee.ad/video/YRdG5pJaDz/)
        match = re.search(r'/video/([a-zA-Z0-9]+)/?', url)
        if match:
            return match.group(1)
            
        # 嘗試匹配編輯器 URL (如 https://referee.ad/wp-admin/post.php?post=7419&action=edit)
        match = re.search(r'post=(\d+)', url)
        if match:
            return match.group(1)
            
        return None
        
    except Exception as e:
        logger.error(f"提取自定義 slug 時發生錯誤: {str(e)}")
        return None

def fill_wp_id(sheet_id: str, sheet_name: str, wp_url_column: str = 'H', wp_id_column: str = 'I'):
    """填充網站 ID 欄位"""
    try:
        # 載入環境變數
        dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', '.env')
        load_dotenv(dotenv_path)
        
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
            
        # 獲取所有 WordPress URL
        wp_url_col_index = ord(wp_url_column) - ord('A') + 1
        wp_urls = sheet.col_values(wp_url_col_index)
        
        # 跳過標題行
        wp_urls = wp_urls[1:]
        
        logger.info(f"獲取到 {len(wp_urls)} 行 WordPress URL")
        
        # 準備批量更新的數據
        update_cells = []
        
        # 處理每個 URL
        for i, wp_url in enumerate(wp_urls, 2):  # 從第 2 行開始，因為第 1 行是標題
            if not wp_url:
                continue
                
            # 檢查是否為 WordPress 草稿 URL
            is_draft = False
            if "wp-admin/post.php" in wp_url and "action=edit" in wp_url:
                is_draft = True
                
            # 從 WordPress URL 提取自定義 slug 或 ID
            custom_slug = extract_custom_slug_from_url(wp_url)
            
            if not custom_slug:
                logger.warning(f"第 {i} 行: 無法從 URL 提取自定義 slug 或 ID: {wp_url}，跳過")
                continue
                
            # 獲取文章 ID
            post_id = None
            
            # 如果是草稿 URL，則直接使用提取的 ID
            if is_draft and custom_slug.isdigit():
                post_id = int(custom_slug)
                logger.info(f"第 {i} 行: 從草稿 URL 直接提取到 ID: {post_id}")
            # 如果是數字，可能是直接從 URL 提取的 ID
            elif custom_slug.isdigit():
                post_id = int(custom_slug)
                logger.info(f"第 {i} 行: 從 URL 直接提取到 ID: {post_id}")
            else:
                # 從映射表中查找 ID
                post_id = mapping.get(custom_slug)
                
            if not post_id:
                logger.warning(f"第 {i} 行: 無法找到自定義 slug 對應的文章 ID: {custom_slug}，跳過")
                continue
                
            update_cells.append({
                'row': i,
                'col': ord(wp_id_column) - ord('A') + 1,
                'value': str(post_id)
            })
            
        # 批量更新 I 欄位
        if update_cells:
            # 將更新拆分為較小的批次，避免超過 API 限制
            batch_size = 100
            total_updated = 0
            
            for i in range(0, len(update_cells), batch_size):
                batch = update_cells[i:i+batch_size]
                cells_to_update = []
                
                for cell in batch:
                    cells_to_update.append(gspread.Cell(
                        row=cell['row'],
                        col=cell['col'],
                        value=cell['value']
                    ))
                    
                sheet.update_cells(cells_to_update)
                total_updated += len(cells_to_update)
                logger.info(f"已更新 {total_updated}/{len(update_cells)} 個單元格")
                
            logger.info(f"成功填充 {len(update_cells)} 行網站 ID")
        else:
            logger.warning("沒有需要更新的單元格")
            
    except Exception as e:
        logger.error(f"填充網站 ID 時發生錯誤: {str(e)}")

def main():
    """主程序"""
    try:
        # 檢查命令列參數
        import sys
        
        if len(sys.argv) < 2:
            print("用法: python fill_wp_id.py <sheet_id> [sheet_name] [wp_url_column] [wp_id_column]")
            print("例如: python fill_wp_id.py 1-xJ5bFishE3FhbExzXu9cvb2yI3m9FUomKDwlr9qLzk '廣告清單' 'H' 'I'")
            sys.exit(1)
            
        # 獲取參數
        sheet_id = sys.argv[1]
        sheet_name = "廣告清單"  # 默認值
        wp_url_column = "H"  # 默認值
        wp_id_column = "I"  # 默認值
        
        if len(sys.argv) > 2:
            sheet_name = sys.argv[2]
            
        if len(sys.argv) > 3:
            wp_url_column = sys.argv[3]
            
        if len(sys.argv) > 4:
            wp_id_column = sys.argv[4]
            
        # 填充網站 ID
        fill_wp_id(sheet_id, sheet_name, wp_url_column, wp_id_column)
        
    except Exception as e:
        logger.error(f"執行過程中發生錯誤: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
