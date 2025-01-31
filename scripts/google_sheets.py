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

def get_video_info(video_ids: List[str], convert_duration: bool = True) -> Dict[str, Dict[str, Any]]:
    """取得多個影片的資訊"""
    sheet = setup_google_sheets()
    info = {}
    logger.info(f"Getting info for videos: {video_ids}")
    
    for video_id in video_ids:
        duration = get_column_value(sheet, 'E', video_id)
        wp_url = get_column_value(sheet, 'H', video_id)
        logger.debug(f"Video {video_id} - Duration: {duration}, URL: {wp_url}")
        
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
                    logger.debug(f"Processed duration for {video_id}: {info[video_id]['duration']}")
                except (ValueError, TypeError) as e:
                    logger.warning(f"無法轉換時長格式 {duration}: {str(e)}")
                    info[video_id]['duration'] = duration
    
    logger.info(f"Final video info: {info}")
    return info

def get_durations_for_split(video_info: Dict[str, Dict[str, Any]], video_ids: List[str]) -> str:
    """從完整影片資訊中提取用於拆分的時長列表"""
    logger.info(f"Getting durations for videos: {video_ids}")
    logger.debug(f"Video info received: {video_info}")
    
    durations = []
    # 只處理除了最後一個以外的影片
    for video_id in video_ids[:-1]:
        logger.debug(f"Processing video ID: {video_id}")
        if video_id in video_info and 'duration' in video_info[video_id]:
            duration = video_info[video_id]['duration']
            logger.debug(f"Found duration for {video_id}: {duration}")
            durations.append(video_info[video_id]['duration'])
        else:
            logger.warning(f"Missing duration for video {video_id}")
    
    result = ' '.join(durations)
    logger.info(f"Final durations string: {result}")
    return result

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

def main():
    import json
    parser = argparse.ArgumentParser(description='Google Sheets 操作工具')
    parser.add_argument('--get-value', nargs=2, 
                      metavar=('COLUMN', 'VIDEO_ID'),
                      help='取得指定欄位的值')
    parser.add_argument('--get-next-id', action='store_true',
                      help='取得下一個可用的 ID')
    parser.add_argument('--get-info', nargs='+',
                      help='取得多個影片的資訊')
    parser.add_argument('--get-durations', nargs='+',
                      help='Get durations for videos')
    args = parser.parse_args()
    
    dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', '.env')
    load_dotenv(dotenv_path)
    
    try:
        if args.get_durations:
            logger.info(f"Processing --get-durations with args: {args.get_durations}")
            video_info = get_video_info(args.get_durations)
            logger.debug(f"Retrieved video info: {video_info}")
            durations = get_durations_for_split(video_info, args.get_durations)
            logger.debug(f"Calculated durations: {durations}")
            print(durations)  # 輸出空格分隔的時長列表
            
        elif args.get_info:
            logger.info(f"Processing --get-info with args: {args.get_info}")
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
        logger.error(f"執行失敗: {str(e)}")
        raise  # 讓錯誤繼續往上傳遞，以便 AppleScript 能捕獲它

if __name__ == "__main__":
    main()