import os
import subprocess
import gspread
from google.oauth2.service_account import Credentials
import yt_dlp
from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler
import requests
from requests.auth import HTTPBasicAuth
from typing import Optional, Dict, List
import time  # 用於重試延遲
import glob  # 用於查找部分下載的文件

# ========== 全域功能開關 ==========
ENABLE_OPENAI = False     
ENABLE_WORDPRESS = True  
# =================================

# 載入環境變數
load_dotenv()

# 定義等級到圖示的映射
LEVEL_ICONS = {
    'INFO': 'ℹ️',
    'ERROR': '❌',
    'SUCCESS': '✓',
}

class IconFormatter(logging.Formatter):
    def format(self, record):
        icon = LEVEL_ICONS.get(record.levelname, '')
        return f"{self.formatTime(record, '%Y-%m-%d %H:%M:%S')} {icon} [{record.levelname}] {record.getMessage()}"

# 創建 Logger
logger = logging.getLogger('content_automation')
logger.setLevel(logging.INFO)

# 創建 RotatingFileHandler，最大 5MB，保留 5 個備份
log_file_path = os.path.expanduser("~/Library/Logs/content_automation.log")
rotating_handler = RotatingFileHandler(log_file_path, maxBytes=5*1024*1024, backupCount=5)
rotating_handler.setLevel(logging.INFO)

# 設置自定義 Formatter
formatter = IconFormatter('%(asctime)s - %(levelname)s - %(message)s')
rotating_handler.setFormatter(formatter)

# 將處理器添加到 Logger
logger.addHandler(rotating_handler)

class WordPressAPI:
    def __init__(self):
        """初始化 WordPress API 客戶端"""
        self.site_url = os.getenv("WP_SITE_URL").rstrip('/')
        self.api_base = f"{self.site_url}/wp-json/wp/v2"
        self.auth = HTTPBasicAuth(
            os.getenv("WP_USERNAME"),
            os.getenv("WP_APP_PASSWORD")
        )
        
    def create_draft(
        self,
        title: str,
        content: str,
        video_url: str,
        video_length: str = "",
        video_tag: Optional[List[int]] = None,
    ) -> Dict:
        """建立影片草稿"""
        endpoint = f"{self.api_base}/video"
        
        # 使用 Gutenberg blocks 格式的內容
        formatted_content = f"""<!-- wp:paragraph -->
<p>{content}</p>
<!-- /wp:paragraph -->"""
        
        # 準備主要資料
        data = {
            "title": title,
            "content": formatted_content,
            "status": "draft",
            "comment_status": "closed",
            "ping_status": "closed",
            # 使用 meta 欄位設定影片資訊
            "meta": {
                "video_url": video_url,
                "length": video_length,
                "_length": video_length,
                "video_length": video_length
            }
        }
        
        # 加入影片標籤
        if video_tag:
            data["video_tag"] = video_tag
            
        response = requests.post(
            endpoint,
            auth=self.auth,
            json=data
        )
        
        if response.status_code != 201:
            raise Exception(f"建立草稿失敗: {response.text}")
        
        return response.json()
    

def write_log(level, message):
    """簡化的日誌函式"""
    level_up = level.upper()
    if level_up == 'INFO':
        logger.info(message)
    elif level_up == 'ERROR':
        logger.error(message)
    elif level_up == 'SUCCESS':
        logger.info(message)
    else:
        logger.info(message)

def setup_google_sheets():
    """連線 Google Sheets"""
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = Credentials.from_service_account_file(
        os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
        scopes=scope
    )
    client = gspread.authorize(creds)

    spreadsheet = client.open("影片廣告資料庫清單")
    sheet = spreadsheet.worksheet("廣告清單")
    return sheet

def get_next_id(sheet):
    """A欄可能有舊 ID，從第三列開始，找目前最大的 ID 並加1"""
    id_values = sheet.col_values(1)[2:]  # 跳過前兩列(標題)
    id_numbers = [int(x) for x in id_values if x.isdigit()]
    max_id = max(id_numbers) if id_numbers else 0
    return max_id + 1

def get_video_metadata(youtube_url, max_retries=3):
    """使用 yt_dlp 擷取影片標題和時長"""
    write_log("INFO", f"擷取影片資訊: {youtube_url}")
    
    for attempt in range(max_retries):
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
                'forcejson': True,
                'noplaylist': True,
                'no_cookies': True
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(youtube_url, download=False)
                
                title = info.get('title', '無標題')
                duration = info.get('duration', 0)
                
                # 時長轉換為 MM:SS 格式
                minutes, seconds = divmod(duration, 60)
                formatted_duration = f"{int(minutes)}:{int(seconds):02}"
                
                write_log("INFO", f"影片標題: {title}, 時長: {formatted_duration}")
                return title, formatted_duration
                
        except Exception as e:
            if attempt < max_retries - 1:
                write_log("ERROR", f"擷取資訊失敗 (嘗試 {attempt + 1}/{max_retries}): {str(e)}")
                time.sleep(5)
                continue
            raise

def download_video(youtube_url, video_id, download_dir, max_retries=3):
    """下載 YouTube 影片的主要函數"""
    write_log("INFO", f"開始下載影片 ID {video_id}: {youtube_url}")
    
    # 清理可能存在的部分下載文件
    pattern = f"{video_id}.f*.mp4"
    partial_files = glob.glob(os.path.join(download_dir, pattern))
    for file in partial_files:
        try:
            os.remove(file)
            write_log("INFO", f"已清理部分下載文件: {file}")
        except Exception as e:
            write_log("ERROR", f"清理文件失敗 {file}: {str(e)}")
    
    # 定義下載策略順序
    format_strategies = [
        {
            'format': 'bestvideo[height>=1080][vcodec^=avc1]+bestaudio/best',
            'postprocessor_args': [
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-movflags', '+faststart',
                '-threads', '0'
            ]
        },
        {
            'format': 'bestvideo[height>=1080]+bestaudio/best',
            'postprocessor_args': [
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-movflags', '+faststart',
                '-pix_fmt', 'yuv420p',
                '-profile:v', 'main',
                '-level', '3.1',
                '-preset', 'ultrafast',
                '-threads', '0'
            ]
        },
        {
            'format': 'best',
            'postprocessor_args': [
                '-c:v', 'copy',
                '-c:a', 'copy'
            ]
        }
    ]

    for attempt in range(max_retries):
        try:
            # 選擇當前策略
            strategy = format_strategies[min(attempt, len(format_strategies) - 1)]
            
            ydl_opts = {
                'outtmpl': os.path.join(download_dir, f"{video_id}.%(ext)s"),
                'format': strategy['format'],
                'merge_output_format': 'mp4',
                'no_cookies': True,
                'quiet': False,
                'verbose': True,
                'noplaylist': True,
                'concurrent_fragment_downloads': 8,
                'retries': 10,
                'fragment_retries': 10,
                'ffmpeg_location': '/usr/local/bin/ffmpeg',  # 指定 ffmpeg 路徑
                'postprocessor_args': {
                    'ffmpeg': strategy['postprocessor_args']
                }
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    write_log("INFO", f"使用下載策略 {attempt + 1}: {strategy['format']}")
                    
                    start_time = time.time()
                    info = ydl.extract_info(youtube_url)
                    selected_format = info.get('format_id', 'unknown')
                    resolution = info.get('height', 'unknown')
                    write_log("INFO", f"選擇的格式: {selected_format}, 解析度: {resolution}p")
                    
                    end_time = time.time()
                    write_log("SUCCESS", f"下載成功，耗時: {end_time - start_time:.1f} 秒")
                    return True
                    
                except Exception as e:
                    error_msg = str(e)
                    if "HTTP Error 403" in error_msg:
                        write_log("ERROR", f"策略 {attempt + 1} 失敗: {error_msg}")
                        continue
                    raise
                    
        except Exception as e:
            write_log("ERROR", f"下載失敗 (嘗試 {attempt + 1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                write_log("INFO", "等待 5 秒後使用下一個策略...")
                time.sleep(5)
            continue
    
    raise Exception("所有下載嘗試均失敗")

def find_downloaded_file(download_dir, video_id):
    """尋找下載的檔案，優先找 .mp4"""
    # 先找 .mp4
    mp4_file = os.path.join(download_dir, f"{video_id}.mp4")
    if os.path.exists(mp4_file):
        return mp4_file
        
    # 找其他可能的檔案
    for fname in os.listdir(download_dir):
        if fname.startswith(str(video_id) + "."):
            return os.path.join(download_dir, fname)
    return None

def download_and_convert(youtube_url, video_id, download_dir):
    """下載並確保輸出為 MP4 格式"""
    try:
        success = download_video(youtube_url, video_id, download_dir)
        if not success:
            raise Exception("下載失敗")
        
        # 找尋下載的檔案
        output_file = find_downloaded_file(download_dir, video_id)
        if not output_file:
            raise FileNotFoundError(f"找不到下載檔案: {video_id}.*")
            
        return output_file
        
    except Exception as e:
        write_log("ERROR", f"下載過程發生錯誤: {str(e)}")
        raise

def process_one_row(row_index, youtube_url, assigned_id, sheet, updates, download_dir):
    """處理單筆資料"""
    try:
        # 1) 下載 & re-encode
        output_file = download_and_convert(youtube_url, assigned_id, download_dir)

        # 2) 取得標題 / 時長
        title, length = get_video_metadata(youtube_url)

        # 3) 更新試算表 B/E 欄
        updates.append({
            'range': f'B{row_index}',
            'values': [[title]]
        })
        updates.append({
            'range': f'E{row_index}',
            'values': [[length]]
        })

        # 4) 如果啟用 WordPress，建立草稿
        if ENABLE_WORDPRESS:
            try:
                wp = WordPressAPI()
                
                # 建立影片草稿
                draft_content = f"這是 {title} 的介紹影片。"
                
                # 只加入 "featured" 標籤
                featured_tag = [136]  # "featured" 標籤的 ID
                
                result = wp.create_draft(
                    title=title,
                    content=draft_content,
                    video_url=youtube_url,
                    video_length=length,
                    video_tag=featured_tag
                )
                
                # 取得草稿連結並更新到 H 欄
                draft_link = result.get('link', '建立草稿失敗')
                updates.append({
                    'range': f'H{row_index}',
                    'values': [[draft_link]]
                })
                
                write_log("SUCCESS", f"WordPress 草稿建立成功: {draft_link}")
                
            except Exception as wp_error:
                write_log("ERROR", f"WordPress 錯誤: {wp_error}")
                updates.append({
                    'range': f'H{row_index}',
                    'values': [['WordPress 錯誤']]
                })
                updates.append({
                    'range': f'J{row_index}',
                    'values': [['error']]
                })
                raise  # 向上拋出錯誤

        # 5) 全部成功才更新狀態為 done
        updates.append({
            'range': f'J{row_index}',
            'values': [['done']]
        })

        write_log("SUCCESS", f"影片 ID {assigned_id} 已完成處理")

    except Exception as e:
        write_log("ERROR", f"處理影片 ID {assigned_id} 時發生錯誤: {e}")
        updates.append({
            'range': f'J{row_index}',
            'values': [['error']]
        })
        raise

def check_pending_and_process(sheet):
    """主要處理邏輯"""
    download_dir = "/Users/Mac/Movies"  
    os.makedirs(download_dir, exist_ok=True)

    all_values = sheet.get_all_values()
    next_id = get_next_id(sheet)
    updates = []
    success_count = 0
    fail_count = 0

    write_log("INFO", f"開始掃描資料，共 {len(all_values)-2} 筆資料可供檢查")

    for i, row in enumerate(all_values, start=1):
        if i <= 2:  # 跳過前兩列
            continue

        if len(row) < 10:  # 資料不足，跳過
            continue

        video_id_in_sheet = row[0].strip()
        youtube_url = row[3].strip()  # D欄
        status = row[9].strip().lower()  # J欄

        if youtube_url and not video_id_in_sheet and status != 'done':
            assigned_id = next_id
            next_id += 1

            # 先標記 pending
            updates.append({'range': f'A{i}', 'values': [[assigned_id]]})
            updates.append({'range': f'J{i}', 'values': [['pending']]})

            try:
                process_one_row(i, youtube_url, assigned_id, sheet, updates, download_dir)
                success_count += 1
            except:
                fail_count += 1

    if updates:
        sheet.batch_update(updates)
        write_log("INFO", f"已批量更新 {len(updates)} 個儲存格")
    else:
        write_log("INFO", "沒有符合條件的列可處理")

    write_log("INFO", f"處理完成，成功 {success_count} 筆，失敗 {fail_count} 筆")

def main():
    sheet = setup_google_sheets()
    check_pending_and_process(sheet)

if __name__ == "__main__":
    main()