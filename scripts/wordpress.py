# wordpress.py
import os
import requests
from requests.auth import HTTPBasicAuth
from typing import Optional, List, Dict, Union
from pathlib import Path

class WordPressAPI:
    def __init__(self, logger):
        """初始化 WordPress API 客戶端"""
        self.logger = logger
        self.site_url = os.getenv("WP_SITE_URL", "").rstrip('/')
        if not self.site_url:
            raise ValueError("未設定 WP_SITE_URL 環境變數")
            
        self.api_base = f"{self.site_url}/wp-json/wp/v2"
        self.auth = HTTPBasicAuth(
            os.getenv("WP_USERNAME", ""),
            os.getenv("WP_APP_PASSWORD", "")
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
        """上傳 VTT 字幕檔案到指定文章"""
        vtt_path = Path(vtt_path)
        if not vtt_path.exists():
            raise FileNotFoundError(f"找不到字幕檔: {vtt_path}")
            
        if vtt_path.suffix.lower() != '.vtt':
            raise ValueError(f"不支援的檔案格式: {vtt_path.suffix}")

        self.logger.info(f"開始上傳字幕: {vtt_path.name}")
        
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
            response = requests.post(
                endpoint,
                auth=self.auth,
                files=files,
                data=data
            )
            
            if response.status_code not in (201, 200):
                raise Exception(f"上傳失敗: {response.text}")
                
            result = response.json()
            self.logger.info(f"字幕上傳成功: {result.get('source_url')}")
            return result
            
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
# 使用範例：
"""
from logger import setup_logger

# 初始化
logger = setup_logger('wordpress')
wp = WordPressAPI(logger)

# 建立草稿
draft = wp.create_draft(
    title="測試影片",
    content="這是測試內容",
    video_url="https://youtu.be/xxx",
    video_length="5:30",
    video_tag=[136]  # featured tag
)

# 上傳字幕
wp.upload_vtt(draft['id'], "path/to/subtitle.vtt")
"""