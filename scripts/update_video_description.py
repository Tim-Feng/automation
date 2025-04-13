#!/usr/bin/env python3
# update_video_description.py

import os
import sys
import logging
import requests
import json
from pathlib import Path
from typing import Dict, Optional, Tuple

# 導入現有的模組
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.wordpress_api import WordPressAPI
from scripts.gemini_video_analyzer import GeminiVideoAnalyzer

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s \u2139\uFE0F [Stage-1] [%(name)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/update_description.log', encoding='utf-8')
    ]
)

logger = logging.getLogger('update_description')

class VideoDescriptionUpdater:
    """使用 Gemini 分析影片並更新 WordPress 文章的 video_description 欄位"""

    def __init__(self):
        """初始化 VideoDescriptionUpdater"""
        self.wp_api = WordPressAPI(logger)
        self.gemini_analyzer = GeminiVideoAnalyzer()  # GeminiVideoAnalyzer 不需要 logger 參數
        self.temp_dir = Path('temp_videos')
        self.temp_dir.mkdir(exist_ok=True)

    def get_video_url(self, post_id: int) -> Optional[str]:
        """從文章中獲取影片 URL
        
        Args:
            post_id: 文章 ID
            
        Returns:
            str: 影片 URL 或 None（如果沒有影片）
        """
        endpoint = f"{self.wp_api.api_base}/video/{post_id}"
        
        try:
            response = requests.get(endpoint, auth=self.wp_api.auth, headers=self.wp_api.headers)
            
            if response.status_code != 200:
                logger.error(f"取得文章失敗 - Status: {response.status_code}, Response: {response.text}")
                return None
                
            post_data = response.json()
            video_url = post_data.get('meta', {}).get('video_url', '')
            
            if not video_url:
                logger.error(f"文章 {post_id} 沒有影片 URL")
                return None
                
            return video_url
            
        except Exception as e:
            logger.error(f"取得文章時發生錯誤: {str(e)}")
            return None

    def download_video(self, video_url: str, video_id: str) -> Optional[str]:
        """下載影片
        
        Args:
            video_url: 影片 URL
            video_id: 影片 ID
            
        Returns:
            str: 下載的影片路徑或 None（如果下載失敗）
        """
        try:
            # 使用 yt-dlp 下載影片
            from yt_dlp import YoutubeDL
            
            video_path = self.temp_dir / f"{video_id}.mp4"
            
            ydl_opts = {
                'format': 'best[ext=mp4]/best',
                'outtmpl': str(video_path),
                'quiet': True,
                'no_warnings': True,
            }
            
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])
                
            if video_path.exists():
                logger.info(f"影片下載成功: {video_path}")
                return str(video_path)
            else:
                logger.error(f"影片下載失敗: {video_path}")
                return None
                
        except Exception as e:
            logger.error(f"下載影片時發生錯誤: {str(e)}")
            return None

    def analyze_video(self, video_path: str) -> Optional[str]:
        """使用 Gemini 分析影片
        
        Args:
            video_path: 影片路徑
            
        Returns:
            str: 影片描述或 None（如果分析失敗）
        """
        try:
            # 使用 GeminiVideoAnalyzer 分析影片，指定不使用 WordPress 格式
            video_description = self.gemini_analyzer.analyze_video_file(video_path, use_wordpress_format=False)
            
            if video_description:
                # 只需要簡單清理多餘的空白和換行
                import re
                video_description = re.sub(r'\n\s*\n', '\n\n', video_description)
                video_description = video_description.strip()
                
                logger.info(f"影片分析成功，描述長度: {len(video_description)} 字元")
                return video_description
            else:
                logger.error("影片分析失敗，沒有獲得描述")
                return None
                
        except Exception as e:
            logger.error(f"分析影片時發生錯誤: {str(e)}")
            return None

    def update_video_description(self, post_id: int, description: str) -> bool:
        """更新文章的 video_description 欄位
        
        Args:
            post_id: 文章 ID
            description: 影片描述
            
        Returns:
            bool: 更新是否成功
        """
        try:
            # 使用 WordPress API 更新 video_description 欄位
            endpoint = f"{self.wp_api.api_base}/video/{post_id}"
            data = {
                'meta': {
                    'video_description': description
                }
            }
            
            response = requests.post(
                endpoint,
                json=data,
                auth=self.wp_api.auth,
                headers=self.wp_api.headers
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"文章 {post_id} 的 video_description 欄位更新成功")
                return True
            else:
                logger.error(f"文章 {post_id} 的 video_description 欄位更新失敗 - Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"更新 video_description 欄位時發生錯誤: {str(e)}")
            return False

    def process_post(self, post_id: int) -> bool:
        """處理文章：分析影片並更新 video_description 欄位
        
        Args:
            post_id: 文章 ID
            
        Returns:
            bool: 處理是否成功
        """
        # 獲取影片 URL
        video_url = self.get_video_url(post_id)
        if not video_url:
            return False
            
        logger.info(f"文章 {post_id} 的影片 URL: {video_url}")
        
        # 從 URL 中提取影片 ID
        import re
        video_id = None
        
        # 嘗試從 YouTube URL 中提取 ID
        youtube_patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]+)',
            r'youtube\.com/embed/([a-zA-Z0-9_-]+)',
            r'youtube\.com/v/([a-zA-Z0-9_-]+)'
        ]
        
        for pattern in youtube_patterns:
            match = re.search(pattern, video_url)
            if match:
                video_id = match.group(1)
                break
                
        if not video_id:
            # 如果不是 YouTube URL，使用隨機 ID
            import uuid
            video_id = str(uuid.uuid4())
            
        # 下載影片
        video_path = self.download_video(video_url, video_id)
        if not video_path:
            return False
            
        # 分析影片
        description = self.analyze_video(video_path)
        if not description:
            return False
            
        # 更新 video_description 欄位
        success = self.update_video_description(post_id, description)
        
        # 清理臨時檔案
        try:
            os.remove(video_path)
            logger.info(f"已刪除臨時影片檔案: {video_path}")
        except Exception as e:
            logger.warning(f"刪除臨時影片檔案時發生錯誤: {str(e)}")
            
        return success


def main():
    if len(sys.argv) < 2:
        print("用法: python update_video_description.py <post_id>")
        return
        
    try:
        post_id = int(sys.argv[1])
    except ValueError:
        print(f"錯誤: 文章 ID 必須是數字，收到的是 '{sys.argv[1]}'")
        return
        
    updater = VideoDescriptionUpdater()
    success = updater.process_post(post_id)
    
    if success:
        print(f"成功更新文章 {post_id} 的 video_description 欄位")
    else:
        print(f"更新文章 {post_id} 的 video_description 欄位失敗")


if __name__ == "__main__":
    main()
