import os
import argparse
import gspread
from google.oauth2.service_account import Credentials
from logger import setup_logger
from dotenv import load_dotenv
from typing import List, Dict, Any

logger = setup_logger('google_sheets')

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
    """取得下一個可用的 ID"""
    id_values = sheet.col_values(1)[2:]  # 跳過前兩列(標題)
    id_numbers = [int(x) for x in id_values if x.isdigit()]
    max_id = max(id_numbers) if id_numbers else 0
    return max_id + 1

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

def batch_update(sheet, updates: List[Dict[str, Any]]) -> None:
    """批量更新表格
    Args:
        sheet: Google Sheet worksheet
        updates: [{'range': 'A1', 'values': [['value']]}]
    """
    try:
        sheet.batch_update(updates)
        logger.info(f"批量更新完成，共 {len(updates)} 筆")
    except Exception as e:
        logger.error(f"批量更新失敗: {str(e)}")
        raise

def get_pending_tasks(sheet) -> List[Dict[str, Any]]:
    """取得待處理的任務"""
    all_values = sheet.get_all_values()
    tasks = []
    
    for i, row in enumerate(all_values[2:], start=3):  # 跳過標題列
        if len(row) < 10:
            continue
            
        video_id = row[0].strip()
        youtube_url = row[3].strip()  # D欄
        status = row[9].strip().lower()  # J欄
        
        if youtube_url and not video_id and status != 'done':
            tasks.append({
                'row': i,
                'youtube_url': youtube_url
            })
            
    return tasks

def main():
    parser = argparse.ArgumentParser(description='Google Sheets 操作工具')
    parser.add_argument('--get-value', nargs=2, 
                      metavar=('COLUMN', 'VIDEO_ID'),
                      help='取得指定欄位的值')
    parser.add_argument('--get-next-id', action='store_true',
                      help='取得下一個可用的 ID')
    parser.add_argument('--get-pending', action='store_true',
                      help='取得待處理的任務')
    args = parser.parse_args()
    
    dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', '.env')
    load_dotenv(dotenv_path)
    sheet = setup_google_sheets()
    
    if args.get_value:
        column, video_id = args.get_value
        value = get_column_value(sheet, column, video_id)
        print(value)
    elif args.get_next_id:
        next_id = get_next_id(sheet)
        print(next_id)
    elif args.get_pending:
        tasks = get_pending_tasks(sheet)
        print(tasks)

if __name__ == "__main__":
    main()