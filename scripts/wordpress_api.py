#!/usr/bin/env python3
# wordpress_api.py

import os
import re
import json
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

    def create_draft(
        self,
        title: str,
        content: str,
        video_url: str,
        video_length: str = "",
        video_tag: Optional[List[int]] = None,
        video_id: str = None,
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
            # 如果有提供影片 ID，嘗試下載並上傳縮圖
            if video_id:
                thumbnail_url = self.get_thumbnail_url(video_id)
                if thumbnail_url:
                    # 下載縮圖
                    image_data = self.download_thumbnail(thumbnail_url)
                    if image_data:
                        # 壓縮圖片
                        compressed_data = self.compress_image(image_data)
                        
                        # 上傳縮圖
                        media = self.upload_media(
                            file_data=compressed_data,
                            filename=f"{video_id}-thumbnail.jpg"
                        )
                        if media and 'id' in media:
                            data['featured_media'] = media['id']

            response = requests.post(endpoint, auth=self.auth, json=data)
            
            if response.status_code != 201:
                self.logger.error(f"建立草稿失敗 - Status: {response.status_code}, Response: {response.text}")
                return None
                
            result = response.json()
            
            # 如果有標籤但回應中沒有標籤，嘗試再次更新
            if video_tag and 'video_tag' not in result:
                self.logger.info("標籤可能未設置成功，嘗試更新文章...")
                update_response = requests.post(
                    f"{endpoint}/{result['id']}",
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
            
    def upload_media(self, file_data: Union[str, Path, bytes], filename: Optional[str] = None, post_id: Optional[int] = None) -> Optional[Dict]:
        """上傳媒體檔案到 WordPress
        
        Args:
            file_data: 檔案路徑或二進制數據
            filename: 如果 file_data 是二進制數據，需要提供檔案名
            post_id: 關聯的文章 ID（可選）
            
        Returns:
            Dict: 上傳結果
        """
        try:
            endpoint = f"{self.api_base}/media"
            headers = {}
            
            if isinstance(file_data, (str, Path)):
                # 如果是檔案路徑
                files = {
                    'file': open(file_data, 'rb')
                }
                if post_id:
                    headers['post'] = str(post_id)
            else:
                # 如果是二進制數據
                if not filename:
                    raise ValueError("當上傳二進制數據時必須提供檔案名")
                files = {
                    'file': (filename, file_data, 'image/jpeg')
                }
            
            response = requests.post(
                endpoint,
                headers=headers,
                files=files,
                auth=self.auth
            )
            
            if response.status_code in [201, 200]:
                return response.json()
            else:
                self.logger.error(f"上傳媒體失敗: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            self.logger.error(f"上傳媒體時發生錯誤: {str(e)}")
            return None
            
    def upload_vtt(self, post_id: int, vtt_path: Union[str, Path]) -> Dict:
        """上傳 VTT 字幕檔案，並更新文章的字幕設定
        
        Args:
            post_id: 文章 ID
            vtt_path: 字幕檔案路徑
            
        Returns:
            Dict: 上傳結果
        """
        vtt_path = Path(vtt_path)
        if not vtt_path.exists():
            raise FileNotFoundError(f"找不到字幕檔案: {vtt_path}")
            
        # 上傳字幕檔案
        upload_result = self.upload_media(vtt_path, post_id)
        if not upload_result:
            return None
            
        # 從上傳結果中取得字幕 URL
        subtitle_url = upload_result.get('source_url')
        if not subtitle_url:
            self.logger.error(f"文章 {post_id} 的字幕上傳成功，但無法取得字幕 URL")
            return None
            
        # 從檔名判斷語系
        lang = vtt_path.stem.split('-')[-1]
        
        # 更新文章的字幕設定
        endpoint = f"{self.api_base}/video/{post_id}"
        data = {
            'meta': {
                'text_tracks': {
                    'languages': [lang],
                    'sources': [subtitle_url],
                    'action': ''
                }
            }
        }
        
        try:
            response = requests.post(endpoint, auth=self.auth, json=data)
            
            if response.status_code not in (200, 201):
                self.logger.error(f"文章 {post_id} 的字幕設定更新失敗 - Status: {response.status_code}, Response: {response.text}")
                return None
                
            return response.json()
            
        except Exception as e:
            self.logger.error(f"文章 {post_id} 的字幕設定更新時發生錯誤: {str(e)}")
            return None
            
    def get_post_id_by_title(self, title: str) -> Union[int, None]:
        """根據標題取得文章 ID"""
        endpoint = f"{self.api_base}/video"
        params = {
            'search': title,
            'per_page': 1
        }
        
        try:
            response = requests.get(endpoint, auth=self.auth, params=params)
            
            if response.status_code != 200:
                self.logger.error(f"搜尋文章失敗 - Status: {response.status_code}, Response: {response.text}")
                return None
                
            results = response.json()
            if not results:
                return None
                
            return results[0]['id']
            
        except Exception as e:
            self.logger.error(f"搜尋文章時發生錯誤: {str(e)}")
            return None
            
    def convert_tags_to_ids(self, tags: Dict) -> List[int]:
        """將 Assistant 返回的標籤轉換為 WordPress 標籤 ID"""
        tag_ids = []
        processed_tags = set()  # 用於追蹤已處理的標籤
        
        try:
            # 檢查是否有 existing_tags
            if "existing_tags" in tags:
                existing_tags = tags["existing_tags"]
                
                # 處理 categories 和 tags
                for tag_type, tag_groups in existing_tags.items():
                    if isinstance(tag_groups, dict):
                        for group_name, group_data in tag_groups.items():
                            if isinstance(group_data, dict):
                                for subgroup_name, values in group_data.items():
                                    if isinstance(values, list):
                                        for value in values:
                                            if value not in processed_tags:
                                                processed_tags.add(value)
                                                tag_id = self.create_tag(value)
                                                if tag_id:
                                                    tag_ids.append(tag_id)
                                                    self.logger.debug(f"建立標籤: {value} -> ID: {tag_id}")
                            elif isinstance(group_data, list):
                                for value in group_data:
                                    if value not in processed_tags:
                                        processed_tags.add(value)
                                        tag_id = self.create_tag(value)
                                        if tag_id:
                                            tag_ids.append(tag_id)
                                            self.logger.debug(f"建立標籤: {value} -> ID: {tag_id}")
            
            if not tag_ids:
                self.logger.warning("沒有成功處理任何標籤")
                
            return list(set(tag_ids))  # 確保返回的 ID 列表沒有重複
            
        except Exception as e:
            self.logger.error(f"轉換標籤時發生錯誤: {str(e)}")
            return []
            
    def create_tag(self, name):
        """創建新標籤，如果標籤已存在則返回現有標籤的 ID"""
        endpoint = f"{self.api_base}/video_tag"
        response = requests.post(
            endpoint,
            auth=self.auth,
            json={'name': name}
        )
        
        if response.status_code == 201:
            return response.json()['id']
        elif response.status_code == 400:
            error_data = response.json()
            if error_data.get('code') == 'term_exists':
                # 如果標籤已存在，返回現有標籤的 ID
                return error_data['data']['term_id']
            else:
                raise Exception(f"創建標籤失敗: {response.status_code} - {response.text}")
        else:
            raise Exception(f"創建標籤失敗: {response.status_code} - {response.text}")
            
    def get_thumbnail_url(self, video_id: str) -> Optional[str]:
        """從 YouTube 影片 ID 獲取縮圖網址"""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
                if info and 'thumbnail' in info:
                    return info['thumbnail']
                return None
        except Exception as e:
            self.logger.error(f"獲取縮圖失敗：{str(e)}")
            return None
            
    def compress_image(self, image_data: bytes, max_size: int = 1024) -> bytes:
        """壓縮圖片到指定大小以下

        Args:
            image_data: 原始圖片數據
            max_size: 最大尺寸（寬或高）

        Returns:
            壓縮後的圖片數據
        """
        try:
            # 打開圖片
            img = Image.open(BytesIO(image_data))
            
            # 計算縮放比例
            ratio = min(max_size / img.width, max_size / img.height)
            if ratio < 1:
                new_size = (int(img.width * ratio), int(img.height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            # 儲存壓縮後的圖片
            output = BytesIO()
            img.save(output, format='JPEG', quality=85, optimize=True)
            return output.getvalue()
        except Exception as e:
            self.logger.error(f"壓縮圖片失敗：{str(e)}")
            return image_data

    def download_thumbnail(self, url: str) -> Optional[bytes]:
        """下載縮圖

        Args:
            url: 縮圖網址

        Returns:
            圖片數據或 None（如果下載失敗）
        """
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return response.content
            return None
        except Exception as e:
            self.logger.error(f"下載縮圖失敗：{str(e)}")
            return None