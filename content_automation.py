import os
import subprocess
import gspread
from google.oauth2.service_account import Credentials
import yt_dlp
from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler

# ========== 全域功能開關（如需 GPT/WordPress） ==========
ENABLE_OPENAI = False     
ENABLE_WORDPRESS = False  
# =================================

# 載入環境變數（若無 .env 可移除）
load_dotenv()

# 定義等級到圖示的映射
LEVEL_ICONS = {
    'INFO': 'ℹ️',
    'ERROR': '❌',
    'SUCCESS': '✓',
}

# 自定義 Formatter
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

def write_log(level, message):
    """
    簡化的日誌函式
    """
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
    """
    連線 Google Sheets
    """
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
    """
    A欄可能有舊 ID，從第三列開始，找目前最大的 ID 並加1
    """
    id_values = sheet.col_values(1)[2:]  # 跳過前兩列(標題)
    id_numbers = [int(x) for x in id_values if x.isdigit()]
    max_id = max(id_numbers) if id_numbers else 0
    return max_id + 1

def get_video_metadata(youtube_url):
    """
    使用 yt_dlp 擷取影片標題和時長
    """
    write_log("INFO", f"擷取影片資訊: {youtube_url}")
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'forcejson': True,
        'noplaylist': True
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url, download=False)

    title = info.get('title', '無標題')
    duration = info.get('duration', 0)  # 以秒為單位

    # 時長轉換為 HH:MM:SS 格式
    minutes, seconds = divmod(duration, 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        formatted_duration = f"{int(hours)}:{int(minutes):02}:{int(seconds):02}"
    else:
        formatted_duration = f"{int(minutes)}:{int(seconds):02}"

    write_log("INFO", f"影片標題: {title}, 時長: {formatted_duration}")
    return title, formatted_duration

def download_only(youtube_url, video_id, download_dir):
    """
    只使用 yt_dlp 下載，不做後處理
    """
    write_log("INFO", f"開始下載影片 ID {video_id}: {youtube_url}")
    ydl_opts = {
        'outtmpl': os.path.join(download_dir, f"{video_id}.%(ext)s"),
        'format': 'bestvideo[height>=1080]+bestaudio/best',  
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([youtube_url])

    write_log("INFO", f"下載完成 (純檔案) - 影片 ID {video_id}")

def find_downloaded_file(download_dir, video_id):
    """
    嘗試在 download_dir 中找到前綴為 {video_id} 的檔案
    可能是 .webm / .mkv / .mp4 / ...
    """
    for fname in os.listdir(download_dir):
        if fname.startswith(str(video_id) + "."):
            return os.path.join(download_dir, fname)
    return None

def ffmpeg_reencode(input_file, output_file):
    """
    以 subprocess.run() 呼叫 ffmpeg，重新編碼成 H.264 + AAC + .mp4
    """
    write_log("INFO", f"開始 ffmpeg 轉檔：{input_file} -> {output_file}")

    cmd = [
        "ffmpeg",
        "-i", input_file,
        "-c:v", "libx264",
        "-crf", "23",
        "-preset", "medium",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        output_file
    ]
    # 顯示命令供除錯
    write_log("INFO", f"ffmpeg cmd: {cmd}")

    completed = subprocess.run(cmd, capture_output=True, text=True)

    if completed.returncode != 0:
        # 出錯, 印出 stderr
        write_log("ERROR", f"ffmpeg 轉檔失敗: {completed.stderr}")
        raise RuntimeError("ffmpeg re-encode failed")

    write_log("INFO", f"轉檔完成，輸出檔：{output_file}")

def download_and_convert(youtube_url, video_id, download_dir):
    """
    1) 下載 (純檔案)
    2) 尋找剛下載的檔
    3) 用 ffmpeg re-encode 成 mp4
    4) 刪除原始檔
    5) 回傳 output mp4 檔路徑
    """
    # (1) 只下載
    download_only(youtube_url, video_id, download_dir)

    # (2) 找到剛下載的檔名 (可能是 .webm / .mkv / ...)
    in_file = find_downloaded_file(download_dir, video_id)
    if not in_file:
        raise FileNotFoundError(f"找不到下載檔案: {video_id}.*")

    # (3) ffmpeg re-encode -> mp4
    out_file = os.path.join(download_dir, f"{video_id}.mp4")
    ffmpeg_reencode(in_file, out_file)

    # (4) 刪除原始檔（若成功轉檔才刪除）
    if os.path.exists(in_file) and in_file != out_file:
        os.remove(in_file)
        write_log("INFO", f"已刪除原始檔：{in_file}")

    return out_file

def process_one_row(row_index, youtube_url, assigned_id, sheet, updates, download_dir):
    """
    處理單筆 row: 
      - 下載 & 轉檔 
      - 取得標題/時長
      - (若需要) GPT / WP draft
      - 更新欄位 B/E/J
    """
    try:
        # 1) 下載 & re-encode
        output_file = download_and_convert(youtube_url, assigned_id, download_dir)

        # 2) 取得標題 / 時長
        title, length = get_video_metadata(youtube_url)  

        # 3) 更新試算表 B/E/J 欄
        updates.append({
            'range': f'B{row_index}',
            'values': [[title]]
        })
        updates.append({
            'range': f'E{row_index}',
            'values': [[length]]
        })
        updates.append({
            'range': f'J{row_index}',
            'values': [['done']]
        })

        write_log("SUCCESS", f"影片 ID {assigned_id} 已完成處理，並標記為 'done'")

    except Exception as e:
        write_log("ERROR", f"下載或處理影片 ID {assigned_id} 時發生錯誤: {e}")
        updates.append({
            'range': f'J{row_index}',
            'values': [['error']]
        })
        raise  # 讓外層捕捉 & 統計

def check_pending_and_process(sheet):
    """
    主邏輯：找到 A欄為空、D欄有連結、J欄 != 'done' 的列，為其分配 ID，下載 & 轉檔 & 更新欄位
    """
    # 確保下載目錄
    download_dir = "/Users/Mac/Movies"  
    os.makedirs(download_dir, exist_ok=True)

    # 取得表資料
    all_values = sheet.get_all_values()

    next_id = get_next_id(sheet)

    updates = []
    success_count = 0
    fail_count = 0

    write_log("INFO", f"開始掃描資料，共 {len(all_values)-2} 筆資料可供檢查(跳過前兩列)")

    for i, row in enumerate(all_values, start=1):
        if i <= 2:
            # 跳過前兩列
            continue

        if len(row) < 10:
            # 資料不足 10 欄, 跳過
            continue

        video_id_in_sheet = row[0].strip()
        youtube_url = row[3].strip()
        status = row[9].strip().lower()

        # 判斷 A欄空 & D欄有連結 & J欄 != 'done'
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

    write_log("INFO", f"處理完成，共成功 {success_count} 筆，失敗 {fail_count} 筆")

def main():
    sheet = setup_google_sheets()
    check_pending_and_process(sheet)

if __name__ == "__main__":
    main()
