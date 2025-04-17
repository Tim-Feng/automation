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

    def delete_post(self, post_id: int) -> bool:
        """刪除指定 ID 的影片文章（自訂型別 video）
        Args:
            post_id: 文章 ID
        Returns:
            bool: 刪除是否成功
        """
        endpoint = f"{self.api_base}/video/{post_id}"
        try:
            response = requests.delete(endpoint, auth=self.auth, headers=self.headers)
            if response.status_code in [200, 204]:
                self.logger.info(f"已成功刪除文章 {post_id}")
                return True
            else:
                self.logger.error(f"刪除文章 {post_id} 失敗: {response.status_code}, {response.text}")
                return False
        except Exception as e:
            self.logger.error(f"刪除文章 {post_id} 時發生錯誤: {str(e)}")
            return False

    def __init__(self, logger):
        """初始化 WordPress API 客戶端"""
        self.logger = logger
        self.site_url = os.getenv("WP_SITE_URL").rstrip('/')
        self.api_base = f"{self.site_url}/wp-json/wp/v2"
        self.auth = HTTPBasicAuth(
            os.getenv("WP_USERNAME"),
            os.getenv("WP_APP_PASSWORD")
        )
        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

    def create_draft(
        self,
        title: str,
        content: str,
        video_url: str,
        video_length: str = "",
        video_tag: Optional[List[int]] = None,
        video_id: str = None,
        meta_data: Optional[Dict] = None,
    ) -> Dict:
        """建立影片草稿"""
        endpoint = f"{self.api_base}/video"
        
        # 準備基本的 meta 資料
        meta = {
            'video_url': video_url,
            'length': video_length
        }
        
        # 如果提供了額外的 meta 資料，將其合併到 meta 中
        if meta_data:
            # 先將 video_description 分離出來，稍後單獨處理
            video_description = None
            if 'video_description' in meta_data:
                video_description = meta_data.pop('video_description')
                self.logger.info("將在創建文章後單獨設置 video_description 欄位")
            
            # 合併其他 meta 資料
            meta.update(meta_data)
        
        data = {
            'title': title,
            'content': content,
            'status': 'draft',
            'comment_status': 'closed',  # 關閉評論
            'ping_status': 'closed',     # 關閉 pingbacks
            'meta': meta
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
            
            # 如果成功創建文章並有 video_description，則單獨設置該欄位
            if result and video_description and 'id' in result:
                post_id = result['id']
                self.logger.info(f"文章創建成功，ID: {post_id}，現在設置 video_description 欄位")
                
                try:
                    # 使用 WordPress REST API 的 update 端點設置 video_description
                    update_endpoint = f"{self.api_base}/video/{post_id}"
                    update_data = {
                        'meta': {
                            'video_description': video_description
                        }
                    }
                    
                    headers = {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    }
                    
                    update_response = requests.post(
                        update_endpoint,
                        json=update_data,
                        auth=self.auth,
                        headers=headers
                    )
                    
                    if update_response.status_code in [200, 201]:
                        self.logger.info("設置 video_description 欄位成功")
                    else:
                        self.logger.warning(f"設置 video_description 欄位失敗: {update_response.status_code}")
                        self.logger.warning(f"錯誤訊息: {update_response.text}")
                except Exception as e:
                    self.logger.error(f"設置 video_description 欄位時發生錯誤: {str(e)}")
            
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
            
    def update_post_tags(self, post_id: int, tag_ids: List[int]) -> bool:
        """更新文章的標籤
        
        Args:
            post_id: 文章 ID
            tag_ids: 標籤 ID 列表
            
        Returns:
            bool: 更新是否成功
        """
        self.logger.debug(f"正在更新文章 {post_id} 的標籤: {tag_ids}")
        endpoint = f"{self.api_base}/video/{post_id}"
        
        # 使用正確的分類法 video_tag
        payload = {
            "video_tag": tag_ids
        }
        
        response = requests.post(
            endpoint,
            auth=self.auth,
            headers=self.headers,
            json=payload
        )
        
        if response.status_code == 200:
            # 確認標籤是否已關聯到文章
            verify_response = requests.get(f"{endpoint}?_fields=video_tag", auth=self.auth, headers=self.headers)
            if verify_response.status_code == 200:
                data = verify_response.json()
                if "video_tag" in data and data["video_tag"]:
                    self.logger.debug(f"文章 {post_id} 的標籤已成功關聯: {data['video_tag']}")
                else:
                    self.logger.warning(f"文章 {post_id} 的標籤更新成功，但驗證時找不到標籤: {data}")
            
            return True
        else:
            self.logger.error(f"文章 {post_id} 的標籤更新失敗: {response.status_code}, {response.text}")
            return False
            
    def convert_tags_to_ids(self, tags_data: Dict) -> List[int]:
        """將標籤資料轉換為標籤 ID 列表
        
        Args:
            tags_data: 標籤資料字典
            
        Returns:
            List[int]: 標籤 ID 列表
        """
        tag_ids = []
        
        try:
            # 取得所有標籤，使用 video_tag 分類法
            all_tags_endpoint = f"{self.api_base}/video_tag?per_page=100"
            response = requests.get(all_tags_endpoint, auth=self.auth, headers=self.headers)
            
            if response.status_code != 200:
                self.logger.error(f"獲取標籤列表失敗: {response.status_code}")
                return []
                
            all_tags = response.json()
            tags_map = {tag['name'].lower(): tag['id'] for tag in all_tags}
            
            # 從 tags_data 中提取標籤
            if "existing_tags" in tags_data and "tags" in tags_data["existing_tags"]:
                # 處理已存在的標籤 - 多層結構
                existing_tags = tags_data["existing_tags"]["tags"]
                
                # 處理主分類（人、事、時、地、物）
                for main_category, subcategories in existing_tags.items():
                    self.logger.debug(f"處理主分類: {main_category}")
                    
                    # 處理子分類
                    if isinstance(subcategories, dict):
                        for subcategory, tags in subcategories.items():
                            self.logger.debug(f"處理子分類: {subcategory}, 標籤: {tags}")
                            
                            # 處理標籤列表
                            if isinstance(tags, list):
                                for tag in tags:
                                    if not tag:  # 跳過空標籤
                                        continue
                                        
                                    self.logger.debug(f"處理標籤: {tag}")
                                    tag_name = tag.lower()
                                    
                                    if tag_name in tags_map:
                                        self.logger.debug(f"標籤 '{tag}' 已存在，ID: {tags_map[tag_name]}")
                                        tag_ids.append(tags_map[tag_name])
                                    else:
                                        # 如果標籤不存在，則建立新標籤
                                        new_tag_id = self._create_tag(tag)
                                        if new_tag_id:
                                            tag_ids.append(new_tag_id)
                                    
            # 處理分類標籤
            if "existing_tags" in tags_data and "categories" in tags_data["existing_tags"]:
                for category, tags in tags_data["existing_tags"]["categories"].items():
                    for tag in tags:
                        tag_name = tag.lower()
                        if tag_name in tags_map:
                            tag_ids.append(tags_map[tag_name])
                        else:
                            # 如果標籤不存在，則建立新標籤
                            new_tag_id = self._create_tag(tag)
                            if new_tag_id:
                                tag_ids.append(new_tag_id)
                                
            # 處理新建議的標籤
            if "new_tag_suggestions" in tags_data and "tags" in tags_data["new_tag_suggestions"]:
                # 處理新建議的標籤 - 多層結構
                new_tags = tags_data["new_tag_suggestions"]["tags"]
                
                # 處理主分類（人、事、時、地、物）
                for main_category, subcategories in new_tags.items():
                    self.logger.debug(f"處理新標籤主分類: {main_category}")
                    
                    # 跳過空子分類
                    if not subcategories:
                        continue
                        
                    # 處理子分類
                    if isinstance(subcategories, dict):
                        for subcategory, tags in subcategories.items():
                            self.logger.debug(f"處理新標籤子分類: {subcategory}, 標籤: {tags}")
                            
                            # 處理標籤列表
                            if isinstance(tags, list):
                                for tag in tags:
                                    if not tag:  # 跳過空標籤
                                        continue
                                        
                                    self.logger.debug(f"處理新標籤: {tag}")
                                    tag_name = tag.lower()
                                    
                                    if tag_name in tags_map:
                                        self.logger.debug(f"新標籤 '{tag}' 已存在，ID: {tags_map[tag_name]}")
                                        tag_ids.append(tags_map[tag_name])
                                    else:
                                        # 如果標籤不存在，則建立新標籤
                                        new_tag_id = self._create_tag(tag)
                                        if new_tag_id:
                                            tag_ids.append(new_tag_id)
                    # 處理直接的標籤列表
                    elif isinstance(subcategories, list):
                        for tag in subcategories:
                            if not tag:  # 跳過空標籤
                                continue
                                
                            self.logger.debug(f"處理新標籤: {tag}")
                            tag_name = tag.lower()
                            
                            if tag_name in tags_map:
                                self.logger.debug(f"新標籤 '{tag}' 已存在，ID: {tags_map[tag_name]}")
                                tag_ids.append(tags_map[tag_name])
                            else:
                                # 如果標籤不存在，則建立新標籤
                                new_tag_id = self._create_tag(tag)
                                if new_tag_id:
                                    tag_ids.append(new_tag_id)
            
            # 確保標籤 ID 不重複
            tag_ids = list(set(tag_ids))
            self.logger.info(f"標籤處理完成，共 {len(tag_ids)} 個標籤")
            return tag_ids
            
        except Exception as e:
            self.logger.error(f"轉換標籤時發生錯誤: {str(e)}")
            return []
            
    def _create_tag(self, tag_name: str) -> Optional[int]:
        """建立新標籤
        
        Args:
            tag_name: 標籤名稱
            
        Returns:
            Optional[int]: 標籤 ID，如果建立失敗則返回 None
        """
        try:
            self.logger.debug(f"正在建立新標籤: {tag_name}")
            # 使用 video_tag 分類法 API 端點
            endpoint = f"{self.api_base}/video_tag"
            payload = {
                "name": tag_name
            }
            
            response = requests.post(
                endpoint,
                auth=self.auth,
                headers=self.headers,
                json=payload
            )
            
            if response.status_code in [200, 201]:
                tag_id = response.json().get('id')
                self.logger.debug(f"標籤 '{tag_name}' 建立成功，ID: {tag_id}")
                return tag_id
            else:
                # 檢查是否為「標籤已存在」的錯誤
                try:
                    error_data = response.json()
                    if error_data.get('code') == 'term_exists' and 'data' in error_data and 'term_id' in error_data['data']:
                        existing_tag_id = error_data['data']['term_id']
                        self.logger.debug(f"標籤 '{tag_name}' 已存在，使用現有 ID: {existing_tag_id}")
                        return existing_tag_id
                except Exception as json_error:
                    self.logger.error(f"解析標籤建立錯誤回應時發生錯誤: {str(json_error)}")
                
                self.logger.error(f"標籤 '{tag_name}' 建立失敗: {response.status_code}, {response.text}")
                return None
                    
        except Exception as e:
            self.logger.error(f"建立標籤 {tag_name} 時發生錯誤: {str(e)}")
            return None