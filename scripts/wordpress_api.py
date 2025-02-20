#!/usr/bin/env python3
# wordpress_api.py

import os
import re
import json
import time
import requests
import yt_dlp
from requests.auth import HTTPBasicAuth
from typing import Optional, List, Dict, Union
from pathlib import Path
from datetime import datetime, timedelta
from PIL import Image
from io import BytesIO

class WordPressAPI:

    def __init__(self, logger):
        """初始化 WordPress API 客戶端"""
        self.logger = logger
        self.site_url = os.getenv("WP_SITE_URL").rstrip('/')
        self.api_base = f"{self.site_url}/wp-json/wp/v2"
        self.auth = HTTPBasicAuth(
            os.getenv("WP_USERNAME"),
            os.getenv("WP_APP_PASSWORD")
        )

    def get_thumbnail_url(self, video_url: str) -> Optional[str]:
        """從 YouTube 影片 URL 獲取縮圖"""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                if 'thumbnail' in info:
                    return info['thumbnail']
                    
            return None
        except Exception as e:
            self.logger.error(f"獲取影片縮圖失敗: {str(e)}")
            return None

    def compress_image(self, image_data: bytes, max_size: int = 1024, quality: int = 85) -> bytes:
        """壓縮圖片
        
        Args:
            image_data: 原始圖片資料
            max_size: 最大尺寸（寬度或高度）
            quality: JPEG 壓縮品質 (1-100)
            
        Returns:
            bytes: 壓縮後的圖片資料
        """
        try:
            # 從二進位資料讀取圖片
            img = Image.open(BytesIO(image_data))
            
            # 轉換為 RGB 模式（如果是 RGBA）
            if img.mode in ('RGBA', 'LA'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[-1])
                img = background
            
            # 調整大小
            if max(img.size) > max_size:
                ratio = max_size / max(img.size)
                new_size = tuple(int(dim * ratio) for dim in img.size)
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            # 儲存壓縮後的圖片
            output = BytesIO()
            img.save(output, format='JPEG', quality=quality, optimize=True)
            
            return output.getvalue()
            
        except Exception as e:
            self.logger.error(f"壓縮圖片時發生錯誤: {str(e)}")
            return image_data  # 如果壓縮失敗，返回原始資料

    def download_thumbnail(self, thumbnail_url: str) -> Optional[str]:
        """下載並壓縮縮圖到暫存目錄"""
        try:
            import tempfile
            import requests
            from pathlib import Path
            
            # 建立暫存目錄
            temp_dir = Path(tempfile.gettempdir()) / "wp_thumbnails"
            temp_dir.mkdir(exist_ok=True)
            
            # 下載縮圖
            response = requests.get(thumbnail_url)
            if response.status_code == 200:
                # 壓縮圖片
                compressed_data = self.compress_image(
                    response.content,
                    max_size=1024,  # 最大 1024px
                    quality=85      # 85% 品質
                )
                
                # 儲存檔案
                temp_file = temp_dir / f"thumbnail_{int(time.time())}.jpg"
                with open(temp_file, 'wb') as f:
                    f.write(compressed_data)
                    
                return str(temp_file)
            return None
        except Exception as e:
            self.logger.error(f"下載縮圖失敗: {str(e)}")
            return None

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
        
        data = {
            'title': title,
            'content': content,
            'status': 'draft',
            'comment_status': 'closed',  # 關閉評論
            'ping_status': 'closed',     # 關閉 pingbacks
            'meta': {
                'video_url': video_url,
                'length': video_length
            }
        }
        
        if video_tag:
            data['video_tag'] = video_tag
            
        try:
            # 1. 先建立草稿
            response = requests.post(endpoint, auth=self.auth, json=data)
            
            if response.status_code != 201:
                self.logger.error(f"建立草稿失敗 - Status: {response.status_code}, Response: {response.text}")
                return None
                
            result = response.json()
            post_id = result['id']
            
            # 2. 處理縮圖
            if 'youtube.com' in video_url or 'youtu.be' in video_url:
                # 獲取並下載縮圖
                thumbnail_url = self.get_thumbnail_url(video_url)
                if thumbnail_url:
                    thumbnail_path = self.download_thumbnail(thumbnail_url)
                    if thumbnail_path:
                        # 上傳縮圖
                        media_result = self.upload_media(thumbnail_path, post_id)
                        if media_result:
                            # 設定特色圖片
                            self.logger.info(f"設定文章 {post_id} 的特色圖片: {media_result['id']}")
                            update_response = requests.post(
                                f"{endpoint}/{post_id}",
                                auth=self.auth,
                                json={'featured_media': media_result['id']}
                            )
                            if update_response.status_code != 200:
                                self.logger.error(f"設定特色圖片失敗 - Status: {update_response.status_code}")
                            
                        # 刪除暫存檔案
                        os.unlink(thumbnail_path)
            
            # 3. 如果有標籤但回應中沒有標籤，嘗試再次更新
            if video_tag and 'video_tag' not in result:
                self.logger.info("標籤可能未設置成功，嘗試更新文章...")
                update_response = requests.post(
                    f"{endpoint}/{post_id}",
                    auth=self.auth,
                    json={'video_tag': video_tag}
                )
                if update_response.status_code == 200:
                    result = update_response.json()
                    self.logger.info("標籤更新成功")
                else:
                    self.logger.error(f"標籤更新失敗 - Status: {update_response.status_code}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"建立草稿時發生錯誤: {str(e)}")
            return None

    def upload_media(self, file_path: Union[str, Path], post_id: Optional[int] = None) -> Dict:
        """上傳媒體檔案到 WordPress
        
        Args:
            file_path: 檔案路徑
            post_id: 關聯的文章 ID（可選）
            
        Returns:
            Dict: 上傳結果
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"找不到檔案: {file_path}")
            
        # 準備上傳資料
        endpoint = f"{self.api_base}/media"
        files = {
            'file': (
                file_path.name,
                open(file_path, 'rb'),
                'text/vtt' if file_path.suffix.lower() == '.vtt' else None
            )
        }
        
        data = {'title': file_path.stem}
        if post_id:
            data['post'] = post_id
            
        try:
            # 上傳檔案
            response = requests.post(
                endpoint,
                auth=self.auth,
                files=files,
                data=data
            )
            
            if response.status_code not in (201, 200):
                self.logger.error(f"文章 {post_id} 的檔案 {file_path.name} 上傳失敗 - Status: {response.status_code}, Response: {response.text}")
                return None
                
            return response.json()
            
        except Exception as e:
            self.logger.error(f"文章 {post_id} 的檔案 {file_path.name} 上傳時發生錯誤: {str(e)}")
            return None

    def upload_featured_image(self, post_id: int, file_path: Union[str, Path]):
        """上傳特色圖片到 WordPress
        
        Args:
            post_id: 文章 ID
            file_path: 檔案路徑
        """
        try:
            # 上傳檔案
            media_result = self.upload_media(file_path, post_id)
            
            if media_result:
                # 設定特色圖片
                self.logger.info(f"設定文章 {post_id} 的特色圖片: {media_result['id']}")
                update_response = requests.post(
                    f"{self.api_base}/video/{post_id}",  # 使用 video 端點
                    auth=self.auth,
                    json={'featured_media': media_result['id']}
                )
                if update_response.status_code != 200:
                    self.logger.error(f"設定特色圖片失敗 - Status: {update_response.status_code}, Response: {update_response.text}")
                    return False
                return True
                    
        except Exception as e:
            self.logger.error(f"上傳特色圖片時發生錯誤: {str(e)}")
            return False

    def has_featured_image(self, post_id: int) -> bool:
        """檢查文章是否已有特色圖片
        
        Args:
            post_id (int): 文章 ID
            
        Returns:
            bool: 是否已有特色圖片
        """
        try:
            response = requests.get(
                f"{self.api_base}/posts/{post_id}",
                auth=self.auth,
                params={'_fields': 'featured_media'}
            )
            
            if response.status_code != 200:
                self.logger.error(f"檢查特色圖片失敗 - Status: {response.status_code}")
                return False
                
            return bool(response.json().get('featured_media'))
            
        except Exception as e:
            self.logger.error(f"檢查特色圖片時發生錯誤: {str(e)}")
            return False