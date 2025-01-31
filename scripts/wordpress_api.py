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
        
        formatted_content = f"""<!-- wp:paragraph -->
<p>{content}</p>
<!-- /wp:paragraph -->"""
        
        data = {
            "title": title,
            "content": formatted_content,
            "status": "draft",
            "comment_status": "closed",
            "ping_status": "closed",
            "meta": {
                "video_url": video_url,
                "length": video_length,
                "_length": video_length,
                "video_length": video_length
            }
        }
        
        if video_tag:
            data["video_tag"] = video_tag
            
        try:
            self.logger.info(f"開始建立草稿: {title}")
            response = requests.post(
                endpoint,
                auth=self.auth,
                json=data
            )
            
            if response.status_code != 201:
                raise Exception(f"建立草稿失敗: {response.text}")
            
            result = response.json()
            self.logger.info(f"WordPress 草稿建立成功: {result.get('link')}")
            return result
            
        except Exception as e:
            self.logger.error(f"WordPress API 錯誤: {str(e)}")
            raise

    def upload_vtt(self, post_id: int, vtt_path: Union[str, Path]) -> Dict:
        vtt_path = Path(vtt_path)
        if not vtt_path.exists():
            raise FileNotFoundError(f"找不到字幕檔: {vtt_path}")
            
        if vtt_path.suffix.lower() != '.vtt':
            raise ValueError(f"不支援的檔案格式: {vtt_path.suffix}")
            
        # 從檔名判斷語系
        lang_match = re.search(r'-([a-z]{2})(?:\.|$)', vtt_path.stem)
        if not lang_match:
            raise ValueError(f"無法從檔名判斷語系: {vtt_path.name}")
            
        language = lang_match.group(1)
        self.logger.info(f"從檔名判斷語系: {language}")

        self.logger.info(f"開始上傳字幕: {vtt_path.name}")
        
        # 1. 上傳字幕檔案
        endpoint = f"{self.api_base}/media"
        files = {
            'file': (
                vtt_path.name,
                open(vtt_path, 'rb'),
                'text/vtt'
            )
        }
        
        data = {
            'post': post_id,
            'title': vtt_path.stem
        }
        
        try:
            # 上傳檔案
            self.logger.info(f"開始上傳字幕檔案到 {endpoint}")
            response = requests.post(
                endpoint,
                auth=self.auth,
                files=files,
                data=data
            )
            
            # 日誌詳細資訊
            self.logger.debug(f"Request URL: {response.request.url}")
            self.logger.debug(f"Request Headers: {response.request.headers}")
            self.logger.debug(f"Response Status: {response.status_code}")
            self.logger.debug(f"Response Body: {response.text}")

            if response.status_code not in (201, 200):
                self.logger.error(f"上傳失敗 - Status: {response.status_code}, Response: {response.text}")
                raise Exception(f"上傳失敗: {response.text}")
            
            upload_result = response.json()
            self.logger.info(f"字幕上傳成功: {upload_result.get('source_url')}")
            
            # 2. 更新文章的字幕設定
            self.logger.info(f"更新文章 {post_id} 的字幕設定...")
            update_endpoint = f"{self.api_base}/video/{post_id}"
            
            # 構建 text_tracks 資料結構
            update_data = {
                "meta": {
                    "text_tracks": {
                        "languages": [language],
                        "sources": [upload_result.get('source_url')],
                        "action": ""  # 根據需要調整
                    }
                }
            }
            
            self.logger.info(f"發送字幕設定請求: {update_data}")
            update_response = requests.patch(
                update_endpoint,
                auth=self.auth,
                json=update_data
            )
            
            if update_response.status_code not in (200, 201):
                self.logger.error(f"設定字幕失敗 - Status: {update_response.status_code}, Response: {update_response.text}")
                raise Exception(f"設定字幕失敗: {update_response.text}")
                
            update_result = update_response.json()
            self.logger.info(f"字幕設定響應: {update_result}")
            self.logger.info("文章字幕設定成功")
            
            return upload_result
            
        except Exception as e:
            self.logger.error(f"上傳字幕時發生錯誤: {str(e)}")
            raise
            
        finally:
            files['file'][1].close()

    def get_post_id_by_title(self, title: str) -> Union[int, None]:
        """根據標題取得文章 ID"""
        endpoint = f"{self.api_base}/video"
        params = {
            'search': title,
            'per_page': 1
        }
        
        try:
            response = requests.get(
                endpoint,
                auth=self.auth,
                params=params
            )
            
            if response.status_code == 200:
                posts = response.json()
                if posts:
                    return posts[0]['id']
            return None
            
        except Exception as e:
            self.logger.error(f"查詢文章失敗: {str(e)}")
            return None