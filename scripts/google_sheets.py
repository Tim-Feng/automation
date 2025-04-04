import os
import argparse
import gspread
from google.oauth2.service_account import Credentials
from logger import get_workflow_logger
from dotenv import load_dotenv
from typing import List, Dict, Any
import sys

logger = get_workflow_logger('1', 'content_automation')  # Stage 1 因為這是內容準備階段

def _summarize_cell_data(data: List[List[Any]]) -> str:
    """摘要化儲存格數據，避免記錄過多細節"""
    if not data:
        return "空數據"
    return f"{len(data)} 列 x {len(data[0])} 欄"

def setup_google_sheets():
    """設定並連接 Google Sheets"""
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        service_account_path = os.path.join(base_dir, creds_path.lstrip('./'))
        
        if not os.path.exists(service_account_path):
            raise FileNotFoundError(f"找不到憑證檔案：{service_account_path}")
            
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file",
            "https://www.googleapis.com/auth/drive"
        ]
        
        creds = Credentials.from_service_account_file(service_account_path, scopes=scope)
        client = gspread.authorize(creds)
        
        spreadsheet = client.open("影片廣告資料庫清單")
        return spreadsheet.worksheet("廣告清單")
        
    except Exception as e:
        logger.error(f"Google Sheets 連接失敗: {str(e)}")
        raise

def get_next_id(sheet) -> int:
    """取得下一個可用的 ID
    
    邏輯：
    1. 取得所有已分配的 ID
    2. 從最大的 ID 往上掃描，找出第一個空缺的 ID
    3. 如果沒有空缺，則從最大 ID + 1 開始
    
    Returns:
        int: 下一個可用的 ID
    """
    # 取得所有 ID（跳過標題列）
    id_values = sheet.col_values(1)[2:]
    
    # 建立已分配 ID 的集合（用於快速查找）
    assigned_ids = {int(x) for x in id_values if x.isdigit()}
    
    if not assigned_ids:
        return 1
        
    # 取得最大和最小的 ID
    max_id = max(assigned_ids)
    min_id = min(assigned_ids)
    
    # 從最小 ID 開始掃描，找出第一個空缺的 ID
    current_id = min_id
    while current_id <= max_id:
        if current_id not in assigned_ids:
            return current_id
        current_id += 1
    
    # 重新取得最大值，確保不會漏掉新加入的 ID
    max_id = max(assigned_ids)
    next_id = max_id + 1
    while next_id in assigned_ids:
        next_id += 1
    
    return next_id

def get_column_value(sheet, column: str, video_id: str) -> str:
    """取得指定欄位的值"""
    try:
        id_list = sheet.col_values(1)
        try:
            row_idx = id_list.index(video_id) + 1
        except ValueError:
            logger.warning(f"找不到 ID: {video_id}")
            return ""
            
        col_idx = ord(column.upper()) - ord('A') + 1
        return sheet.cell(row_idx, col_idx).value or ""
        
    except Exception as e:
        logger.error(f"讀取欄位 {column} 失敗: {str(e)}")
        return ""

def get_video_info(video_ids: List[str], convert_duration: bool = True) -> Dict[str, Dict[str, Any]]:
    """取得多個影片的資訊"""
    sheet = setup_google_sheets()
    info = {}
    
    for video_id in video_ids:
        duration = get_column_value(sheet, 'E', video_id)
        wp_url = get_column_value(sheet, 'H', video_id)
        logger.debug(f"影片 {video_id} - 時長：{duration}，網址：{wp_url}")
        
        if duration or wp_url:
            info[video_id] = {
                'wordpress_url': wp_url
            }
            
            # 處理時長格式
            if duration:
                try:
                    if convert_duration:
                        minutes, seconds = map(int, duration.split(':'))
                        info[video_id]['duration'] = str(minutes * 60 + seconds)
                    else:
                        info[video_id]['duration'] = duration
                except (ValueError, TypeError) as e:
                    logger.warning(f"無法轉換時長格式 {duration}：{str(e)}")
                    info[video_id]['duration'] = duration
    
    logger.debug(f"影片資訊：{info}")
    return info

def get_durations_for_split(video_info: Dict[str, Dict[str, Any]], video_ids: List[str]) -> str:
    """從完整影片資訊中提取用於拆分的時長列表"""
    durations = []
    # 只處理除了最後一個以外的影片
    for video_id in video_ids[:-1]:
        if video_id in video_info and 'duration' in video_info[video_id]:
            durations.append(video_info[video_id]['duration'])
        else:
            logger.warning(f"找不到影片 {video_id} 的時長資訊")
    
    return ' '.join(durations)

def batch_update(sheet, updates: List[Dict[str, Any]]) -> None:
    """批量更新表格
    
    Args:
        sheet: Google Sheet worksheet
        updates: [{'range': 'A1', 'values': [['value']]}]
    """
    try:
        sheet.batch_update(updates)
    except Exception as e:
        logger.error(f"批量更新失敗: {str(e)}")
        raise

def main():
    import json
    parser = argparse.ArgumentParser(description='Google Sheets 操作工具')
    parser.add_argument('--get-value', nargs=2,
                      help='取得指定欄位的值 (欄位代號 影片ID)')
    parser.add_argument('--get-next-id', action='store_true',
                      help='取得下一個可用的 ID')
    parser.add_argument('--get-info', nargs='+',
                      help='取得多個影片的資訊')
    parser.add_argument('--get-durations', nargs='+',
                      help='取得影片時長列表')
    args = parser.parse_args()
    
    dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', '.env')
    load_dotenv(dotenv_path)
    
    try:
        if args.get_durations:
            video_info = get_video_info(args.get_durations)
            durations = get_durations_for_split(video_info, args.get_durations)
            print(durations)  # 輸出空格分隔的時長列表
            
        elif args.get_info:
            video_info = get_video_info(args.get_info)
            print(json.dumps(video_info))
            
        elif args.get_value:
            column, video_id = args.get_value
            sheet = setup_google_sheets()
            value = get_column_value(sheet, column, video_id)
            print(value)
            
        elif args.get_next_id:
            sheet = setup_google_sheets()
            next_id = get_next_id(sheet)
            print(next_id)
    except Exception as e:
        logger.error(f"執行過程發生錯誤：{str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()