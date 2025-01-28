import os
import yt_dlp
from dotenv import load_dotenv
from typing import Optional, Dict
import time
import glob
from logger import setup_logger
from google_sheets import setup_google_sheets, get_next_id, batch_update
from wordpress import WordPressAPI  # 引入新的 WordPress 模組

logger = setup_logger('content_automation')

# ========== 全域功能開關 ==========
ENABLE_OPENAI = False     
ENABLE_WORDPRESS = True  
# =================================

# 影片下載策略配置
format_strategies = [
    {
        'format': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]',
        'postprocessor_args': ['-c:v', 'libx264', '-crf', '23']
    }
]

def get_video_metadata(youtube_url, max_retries=3):
    """使用 yt_dlp 擷取影片標題和時長"""
    logger.info(f"擷取影片資訊: {youtube_url}")
    
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
                
                logger.info(f"影片標題: {title}, 時長: {formatted_duration}")
                return title, formatted_duration
                
        except Exception as e:
            if attempt < max_retries - 1:
                logger.error(f"擷取資訊失敗 (嘗試 {attempt + 1}/{max_retries}): {str(e)}")
                time.sleep(5)
                continue
            raise

def download_video(youtube_url, video_id, download_dir, max_retries=3):
    """下載 YouTube 影片的主要函數"""
    logger.info(f"開始下載影片 ID {video_id}")
    
    # 清理可能存在的部分下載文件
    pattern = f"{video_id}.f*.mp4"
    partial_files = glob.glob(os.path.join(download_dir, pattern))
    for file in partial_files:
        try:
            os.remove(file)
        except Exception as e:
            logger.error(f"清理文件失敗 {file}: {str(e)}")
    
    for attempt in range(max_retries):
        try:
            # 選擇當前策略
            strategy = format_strategies[min(attempt, len(format_strategies) - 1)]
            
            ydl_opts = {
                'outtmpl': os.path.join(download_dir, f"{video_id}.%(ext)s"),
                'format': strategy['format'],
                'merge_output_format': 'mp4',
                'no_cookies': True,
                'quiet': True,
                'verbose': False,
                'noplaylist': True,
                'concurrent_fragment_downloads': 8,
                'retries': 10,
                'fragment_retries': 10,
                'ffmpeg_location': '/usr/local/bin/ffmpeg',
                'postprocessor_args': {
                    'ffmpeg': strategy['postprocessor_args']
                }
            }
            
            start_time = time.time()
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    info = ydl.extract_info(youtube_url)
                    end_time = time.time()
                    duration = end_time - start_time
                    logger.info(f"影片 ID {video_id} 下載完成，耗時 {duration:.1f} 秒")
                    return True
                    
                except Exception as e:
                    error_msg = str(e)
                    if "HTTP Error 403" in error_msg:
                        logger.error(f"下載嘗試 {attempt + 1} 失敗")
                        continue
                    raise
                    
        except Exception as e:
            logger.error(f"下載失敗 (嘗試 {attempt + 1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
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
        logger.error(f"下載過程發生錯誤: {str(e)}")
        raise

def process_one_row(row_index, youtube_url, assigned_id, sheet, updates, download_dir, wp):
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
                # 使用新的 WordPress API
                draft_content = f"這是 {title} 的介紹影片。"
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
                
            except Exception as wp_error:
                logger.error(f"WordPress 錯誤: {wp_error}")
                updates.append({
                    'range': f'H{row_index}',
                    'values': [['WordPress 錯誤']]
                })
                updates.append({
                    'range': f'J{row_index}',
                    'values': [['error']]
                })
                raise

        # 5) 全部成功才更新狀態為 done
        updates.append({
            'range': f'J{row_index}',
            'values': [['done']]
        })

        logger.info(f"影片 ID {assigned_id} 已完成處理")

    except Exception as e:
        logger.error(f"處理影片 ID {assigned_id} 時發生錯誤: {e}")
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

    logger.info(f"開始掃描資料，共 {len(all_values)-2} 筆資料可供檢查")
    
    # 初始化 WordPress API
    wp = WordPressAPI(logger) if ENABLE_WORDPRESS else None

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
                process_one_row(i, youtube_url, assigned_id, sheet, updates, download_dir, wp)
                success_count += 1
            except:
                fail_count += 1

    if updates:
        batch_update(sheet, updates)
        logger.info(f"已批量更新 {len(updates)} 個儲存格")
    else:
        logger.info("沒有符合條件的列可處理")

    logger.info(f"處理完成，成功 {success_count} 筆，失敗 {fail_count} 筆")

def main():
    # 確保在程式開始時就載入環境變數
    dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', '.env')
    load_dotenv(dotenv_path)
    
    sheet = setup_google_sheets()
    check_pending_and_process(sheet)

if __name__ == "__main__":
    main()