import os
import yt_dlp
from dotenv import load_dotenv
from typing import Optional, Dict
import time
import glob
from logger import get_workflow_logger
from google_sheets import setup_google_sheets, get_next_id, batch_update
from wordpress_api import WordPressAPI
from dependency_manager import check_and_update_ytdlp

logger = get_workflow_logger('1', 'content_automation')  

# ========== 全域功能開關 ==========
ENABLE_OPENAI = False     
ENABLE_WORDPRESS = True  
# =================================

# 影片下載策略配置
format_strategies = [
    {
        'format': 'bestvideo[height<=1080]+bestaudio[acodec!=opus][ext=m4a]/best[height<=1080]',
        'postprocessor_args': ['-c:v', 'libx264', '-crf', '23']
    }
]

def get_video_metadata(youtube_url, max_retries=3):
    """使用 yt_dlp 擷取影片標題和時長"""
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
                    'ffmpeg': ['-c:v', 'libx264', '-crf', '23', '-c:a', 'aac', '-b:a', '192k']
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

def extract_youtube_id(url: str) -> Optional[str]:
    """從 YouTube URL 提取影片 ID"""
    try:
        # 使用 yt_dlp 提取影片 ID
        ydl = yt_dlp.YoutubeDL({'quiet': True})
        info = ydl.extract_info(url, download=False)
        return info.get('id')
    except Exception as e:
        logger.error(f"提取 YouTube ID 失敗：{str(e)}")
        return None

def process_one_row(row_index, youtube_url, assigned_id, sheet, updates, download_dir, wp):
    """處理單筆資料"""
    try:
        # 1) 下載 & re-encode
        output_file = download_and_convert(youtube_url, assigned_id, download_dir)

        # 2) 取得標題 / 時長
        title, length = get_video_metadata(youtube_url)
        logger.info(f"取得影片 {assigned_id} 資訊成功")
        logger.debug(f"標題: {title}")
        logger.debug(f"時長: {length}")

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
                # 使用 Perplexity API 生成內容
                from perplexity_client import PerplexityClient
                perplexity = PerplexityClient()
                draft_content = perplexity.search(title)

                # 如果沒有成功獲取內容，使用預設內容
                if not draft_content:
                    logger.warning(f"Perplexity API 未返回內容，使用預設內容")
                    draft_content = f"這是 {title} 的介紹影片。"

                # 使用 TagSuggester 生成標籤
                from tag_suggestion import TagSuggester
                tag_suggester = TagSuggester()
                tags = tag_suggester.suggest_tags(title=title, content=draft_content)
                
                # 初始化標籤列表，始終包含 featured 標籤
                tag_ids = [136]  # "featured" 標籤的 ID
                
                if tags:
                    # 將 Assistant 返回的標籤轉換為 WordPress 標籤 ID
                    additional_tags = wp.convert_tags_to_ids(tags)
                    if additional_tags:
                        tag_ids.extend(additional_tags)
                    else:
                        logger.warning("無法建立標籤，僅使用 featured 標籤")
                else:
                    logger.warning("無法生成標籤建議，僅使用 featured 標籤")
                
                # 移除重複的標籤 ID 並設置
                tag_ids = list(set(tag_ids))
                
                # 提取 YouTube 影片 ID
                youtube_id = extract_youtube_id(youtube_url)
                
                result = wp.create_draft(
                    title=title,
                    content=draft_content,
                    video_url=youtube_url,
                    video_length=length,
                    video_tag=tag_ids,
                    video_id=youtube_id
                )
                
                # 取得草稿連結並更新到 H 欄
                # 轉換為標準 Gutenberg 編輯器 URL
                post_id = result.get('id')
                if post_id:
                    draft_link = f"{wp.site_url}/wp-admin/post.php?post={post_id}&action=edit"
                else:
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
                raise wp_error

        # 5) 更新狀態為完成
        updates.append({
            'range': f'J{row_index}',
            'values': [['done']]
        })

        return True

    except Exception as e:
        logger.error(f"處理失敗: {str(e)}")
        updates.append({
            'range': f'J{row_index}',
            'values': [['error']]
        })
        raise e

def check_pending_and_process(sheet):
    """主要處理邏輯"""
    download_dir = "/Users/Mac/Movies"  
    os.makedirs(download_dir, exist_ok=True)

    all_values = sheet.get_all_values()
    next_id = get_next_id(sheet)
    updates = []
    success_count = 0
    fail_count = 0
    
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
    
    logger.info(f"處理完成，成功 {success_count} 筆，失敗 {fail_count} 筆")

def main():
    # 確保在程式開始時就載入環境變數
    dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', '.env')
    load_dotenv(dotenv_path)
    
    # 檢查並更新 yt-dlp
    success, message = check_and_update_ytdlp()
    if not success:
        logger.error(f"yt-dlp 更新檢查失敗：{message}")
        return
    logger.info(message)
    
    sheet = setup_google_sheets()
    check_pending_and_process(sheet)

if __name__ == "__main__":
    main()