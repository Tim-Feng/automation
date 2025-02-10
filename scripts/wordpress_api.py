#!/usr/bin/env python3
# wordpress_api.py

import os
import re
import requests
from requests.auth import HTTPBasicAuth
from typing import Optional, List, Dict, Union
from pathlib import Path

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
            response = requests.post(endpoint, auth=self.auth, json=data)
            
            if response.status_code != 201:
                self.logger.error(f"建立草稿失敗 - Status: {response.status_code}, Response: {response.text}")
                return None
                
            return response.json()
            
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