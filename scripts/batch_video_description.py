#!/usr/bin/env python3
# batch_video_description.py

import os
import time
import random
import argparse
import requests
from dotenv import load_dotenv
from typing import Dict, List, Optional, Tuple
import gspread
from google.oauth2.service_account import Credentials
import re

# 引用現有程式碼庫的模組
from logger import get_workflow_logger
from wordpress_api import WordPressAPI
from gemini_video_analyzer import GeminiVideoAnalyzer
from tag_suggestion import TagSuggester
from update_video_description import VideoDescriptionUpdater

# 設定日誌
logger = get_workflow_logger('1', 'batch_processor')

class BatchProcessor:
    def __init__(self):
        """初始化批次處理器"""
        # 載入環境變數
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        load_dotenv(os.path.join(base_dir, 'config', '.env'))
        
        # 初始化 API 客戶端
        self.wp_api = WordPressAPI(logger)
        self.gemini_analyzer = GeminiVideoAnalyzer()
        self.tag_suggester = TagSuggester()
        self.video_updater = VideoDescriptionUpdater()
        
        # 連接 Google Sheets
        self.sheet = self._setup_google_sheets()
        
        # 設定限流參數
        self.gemini_calls_per_minute = 10
        self.last_gemini_call = time.time() - 60
        self.gemini_call_count = 0
        
        # 欄位對應
        self.column_mapping = {
            'youtube_link': 'D',  # YouTube 連結
            'wp_link': 'H',       # WP 文章連結
            'wp_id': 'I',         # WP 文章 ID
            'video_description_status': 'L',
            'tags_from_description_status': 'M'
        }
        
    def _setup_google_sheets(self):
        """設定並連接 Google Sheets"""
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            service_account_path = os.path.join(base_dir, creds_path.lstrip('./'))
            
            if not os.path.exists(service_account_path):
                raise FileNotFoundError(f"找不到憑證檔案：{service_account_path}")
                
            scope = [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive.file",
                "https://www.googleapis.com/auth/drive"
            ]
            
            creds = Credentials.from_service_account_file(service_account_path, scopes=scope)
            client = gspread.authorize(creds)
            
            spreadsheet = client.open("影片廣告資料庫清單")
            return spreadsheet.worksheet("廣告清單")
            
        except Exception as e:
            logger.error(f"Google Sheets 連接失敗: {str(e)}")
            raise
            
    def _respect_rate_limit(self):
        """尊重 API 限流"""
        now = time.time()
        elapsed = now - self.last_gemini_call
        
        # 如果在一分鐘內已經呼叫超過限制次數，則等待
        if elapsed < 60 and self.gemini_call_count >= self.gemini_calls_per_minute:
            wait_time = 60 - elapsed + random.uniform(1, 5)  # 加入隨機等待時間
            logger.info(f"達到限流上限，等待 {wait_time:.2f} 秒")
            time.sleep(wait_time)
            self.gemini_call_count = 0
            self.last_gemini_call = time.time()
        
        # 如果已經過了一分鐘，重置計數器
        if elapsed >= 60:
            self.gemini_call_count = 0
            self.last_gemini_call = now
            
        # 每次呼叫之間加入短暫延遲，避免過於頻繁的請求
        time.sleep(random.uniform(0.5, 2))
        
    def _get_pending_rows(self, batch_size: int = 5, row_range: tuple = None) -> List[Dict]:
        """獲取待處理的資料列，可指定 row 範圍"""
        try:
            # 獲取所有資料
            all_values = self.sheet.get_all_values()
            headers = all_values[0]  # 第一列為標題
            
            # 篩選出待處理的資料列
            pending_rows = []
            for i, row in enumerate(all_values[1:], start=2):  # 從第 2 列開始（標題列為第 1 列）
                if row_range:
                    if i < row_range[0] or i > row_range[1]:
                        continue
                # 使用欄位對應取得資料
                youtube_url = row[ord(self.column_mapping['youtube_link']) - ord('A')]
                wp_link = row[ord(self.column_mapping['wp_link']) - ord('A')]
                wp_id = row[ord(self.column_mapping['wp_id']) - ord('A')]
                video_description_status = row[ord(self.column_mapping['video_description_status']) - ord('A')]
                
                # 檢查是否符合處理條件
                if (wp_id and youtube_url and wp_link and
                    (not video_description_status or 
                     video_description_status == 'pending' or 
                     video_description_status == 'failed')):
                    pending_rows.append({
                        'index': i,
                        'wp_id': wp_id,
                        'youtube_url': youtube_url,
                        'status': video_description_status
                    })
                    
                    if len(pending_rows) >= batch_size:
                        break
                        
            return pending_rows
            
        except Exception as e:
            logger.error(f"獲取待處理資料列時發生錯誤: {str(e)}")
            return []
    
    def process_specific_row(self, row_number: int):
        """處理指定行數的資料"""
        try:
            # 獲取該行資料
            row_data = self.sheet.row_values(row_number)
            logger.debug(f"第 {row_number} 列原始資料: {row_data}")
            
            # 直接讀取特定欄位的資料，而不依賴列表長度
            try:
                # 嘗試直接讀取特定欄位的資料
                youtube_url = self.sheet.cell(row_number, ord(self.column_mapping['youtube_link']) - ord('A') + 1).value
                wp_id = self.sheet.cell(row_number, ord(self.column_mapping['wp_id']) - ord('A') + 1).value
                video_description_status = self.sheet.cell(row_number, ord(self.column_mapping['video_description_status']) - ord('A') + 1).value
                tags_from_description_status = self.sheet.cell(row_number, ord(self.column_mapping['tags_from_description_status']) - ord('A') + 1).value
                
                logger.debug(f"直接讀取欄位資料: youtube_url={youtube_url}, wp_id={wp_id}, video_status={video_description_status}, tags_status={tags_from_description_status}")
            except Exception as cell_error:
                logger.warning(f"直接讀取欄位失敗，切換到備用方法: {str(cell_error)}")
                
                # 如果直接讀取失敗，則使用備用方法
                # 使用欄位對應取得資料，但先檢查索引是否有效
                youtube_link_idx = ord(self.column_mapping['youtube_link']) - ord('A')
                wp_id_idx = ord(self.column_mapping['wp_id']) - ord('A')
                video_status_idx = ord(self.column_mapping['video_description_status']) - ord('A')
                tags_status_idx = ord(self.column_mapping['tags_from_description_status']) - ord('A')
                
                # 安全地存取欄位資料
                youtube_url = row_data[youtube_link_idx] if youtube_link_idx < len(row_data) else ''
                wp_id = row_data[wp_id_idx] if wp_id_idx < len(row_data) else ''
                video_description_status = row_data[video_status_idx] if video_status_idx < len(row_data) else ''
                tags_from_description_status = row_data[tags_status_idx] if tags_status_idx < len(row_data) else ''
                
                # 如果仍然缺少 tags_from_description_status，嘗試再次直接讀取該欄位
                if not tags_from_description_status:
                    try:
                        tags_from_description_status = self.sheet.cell(row_number, ord(self.column_mapping['tags_from_description_status']) - ord('A') + 1).value or ''
                        logger.debug(f"再次直接讀取 tags_status={tags_from_description_status}")
                    except Exception as e:
                        logger.warning(f"再次直接讀取 tags_from_description_status 失敗: {str(e)}")
            
            if not wp_id or not youtube_url:
                logger.error(f"第 {row_number} 列缺少必要資料：WP ID: {wp_id}, YouTube URL: {youtube_url}")
                # 更新狀態為失敗
                self._update_row_status(row_number, 'video_description_status', 'failed')
                return False
                
            logger.info(f"處理第 {row_number} 列，WP ID: {wp_id}, YouTube URL: {youtube_url}")
            
            # 檢查是否需要處理影片描述
            need_process_description = (not video_description_status or 
                                        video_description_status == 'pending' or 
                                        video_description_status == 'failed')
            
            # 檢查是否需要處理標籤
            need_process_tags = (not tags_from_description_status or 
                                tags_from_description_status == 'pending' or 
                                tags_from_description_status == 'failed')
            
            # 如果影片描述需要處理
            if need_process_description:
                # 更新狀態為處理中
                self._update_row_status(row_number, 'video_description_status', 'processing')
                
                # 檢查 WP 文章是否存在 video_description 欄位
                has_description = self._check_video_description(wp_id)
                
                if has_description:
                    logger.info(f"WP ID {wp_id} 已有 video_description 欄位，跳過處理")
                    self._update_row_status(row_number, 'video_description_status', 'completed')
                else:
                    # 尊重限流
                    self._respect_rate_limit()
                    
                    # 使用 VideoDescriptionUpdater 處理
                    success = self.video_updater.process_post(wp_id)
                    self.gemini_call_count += 1
                    
                    if success:
                        logger.info(f"WP ID {wp_id} 的 video_description 欄位更新成功")
                        self._update_row_status(row_number, 'video_description_status', 'completed')
                    else:
                        logger.error(f"WP ID {wp_id} 的 video_description 欄位更新失敗")
                        self._update_row_status(row_number, 'video_description_status', 'failed')
                        return False
            
            # 如果影片描述已完成或剛剛處理完成，且需要處理標籤
            if (video_description_status == 'completed' or 
                self.sheet.cell(row_number, ord(self.column_mapping['video_description_status']) - ord('A') + 1).value == 'completed') and need_process_tags:
                # 檢查 WP 文章是否存在 video_description 欄位（再次確認）
                has_description = self._check_video_description(wp_id)
                
                if has_description:
                    # 處理標籤
                    logger.info(f"WP ID {wp_id} 的影片描述已完成，開始處理標籤")
                    self._process_tags(row_number, wp_id)
                else:
                    logger.error(f"WP ID {wp_id} 沒有 video_description 欄位，無法處理標籤")
                    self._update_row_status(row_number, 'tags_from_description_status', 'failed')
            
            return True
                
        except Exception as e:
            logger.exception(f"處理第 {row_number} 列時發生錯誤: {str(e)}")
            try:
                self._update_row_status(row_number, 'video_description_status', 'failed')
            except:
                pass
            return False
            
    def _update_row_status(self, row_index: int, status_field: str, status: str):
        """更新資料列狀態"""
        try:
            # 檢查狀態欄位是否存在於欄位對應中
            if status_field not in self.column_mapping:
                logger.error(f"狀態欄位 '{status_field}' 不存在於欄位對應中")
                return
                
            # 使用欄位對應取得欄位位置
            column = self.column_mapping[status_field]
            column_index = ord(column) - ord('A') + 1
            
            # 直接嘗試更新特定欄位
            try:
                # 使用 cell 方法直接更新特定欄位
                self.sheet.update_cell(row_index, column_index, status)
                logger.debug(f"已直接更新第 {row_index} 列的 {status_field} ({column}欄) 為 {status}")
                return
            except Exception as direct_update_error:
                logger.warning(f"直接更新第 {row_index} 列的 {status_field} 欄位失敗，切換到備用方法: {str(direct_update_error)}")
            
            # 如果直接更新失敗，嘗試備用方法
            # 確保資料列存在且有足夠的欄位
            try:
                # 先檢查該列是否存在
                current_row = self.sheet.row_values(row_index)
                logger.debug(f"第 {row_index} 列的目前資料: {current_row}")
                
                # 如果列不存在或太短，則先擴展它
                if len(current_row) < column_index:
                    logger.debug(f"第 {row_index} 列的欄位數不足 (目前 {len(current_row)}，需要 {column_index})，嘗試擴展")
                    
                    # 嘗試使用 Google Sheets API 的批量更新功能
                    try:
                        # 建立一個足夠長的列表，但保留原始資料
                        new_row = current_row + [''] * (column_index - len(current_row))
                        # 設定狀態值
                        new_row[column_index - 1] = status
                        # 更新整列
                        self.sheet.update_row(row_index, new_row)
                        logger.debug(f"已擴展並更新第 {row_index} 列的 {status_field} 為 {status}")
                        return
                    except Exception as expand_error:
                        logger.error(f"擴展第 {row_index} 列時發生錯誤: {str(expand_error)}")
                
                # 如果列已存在且足夠長，則直接更新特定欄位
                try:
                    # 再次嘗試直接更新特定欄位
                    self.sheet.update_cell(row_index, column_index, status)
                    logger.debug(f"已更新第 {row_index} 列的 {status_field} 為 {status}")
                    return
                except Exception as update_error:
                    logger.error(f"更新第 {row_index} 列的 {status_field} 欄位時發生錯誤: {str(update_error)}")
                    
            except Exception as row_error:
                logger.error(f"檢查第 {row_index} 列時發生錯誤: {str(row_error)}")
            
            # 嘗試最後的方法 - 使用工作表的特定欄位更新方法
            try:
                # 使用 update_acell 方法使用欄位座標更新
                cell_addr = f"{column}{row_index}"
                self.sheet.update_acell(cell_addr, status)
                logger.debug(f"已使用座標 {cell_addr} 更新第 {row_index} 列的 {status_field} 為 {status}")
            except Exception as acell_error:
                logger.error(f"使用座標更新第 {row_index} 列的 {status_field} 欄位時發生錯誤: {str(acell_error)}")
                
        except Exception as e:
            logger.error(f"更新資料列狀態時發生錯誤: {str(e)}")
            
    def _check_video_description(self, wp_id: int) -> bool:
        """檢查 WP 文章是否已有 video_description 欄位"""
        try:
            endpoint = f"{self.wp_api.api_base}/video/{wp_id}"
            response = requests.get(endpoint, auth=self.wp_api.auth, headers=self.wp_api.headers)
            
            if response.status_code != 200:
                logger.error(f"獲取文章失敗: {response.status_code}")
                return False
                
            data = response.json()
            video_description = data.get('meta', {}).get('video_description', '')
            
            return bool(video_description)
            
        except Exception as e:
            logger.error(f"檢查 video_description 欄位時發生錯誤: {str(e)}")
            return False
            
    def _process_tags(self, row_index: int, wp_id: int):
        """處理標籤生成"""
        try:
            # 檢查是否需要處理標籤
            tags_status = self.sheet.cell(row_index, ord(self.column_mapping['tags_from_description_status']) - ord('A') + 1).value
            
            if tags_status == 'completed':
                logger.info(f"WP ID {wp_id} 的標籤已處理完成，跳過")
                return
                
            # 更新狀態為處理中
            self._update_row_status(row_index, 'tags_from_description_status', 'processing')
            
            # 獲取文章內容和影片描述
            endpoint = f"{self.wp_api.api_base}/video/{wp_id}"
            response = requests.get(endpoint, auth=self.wp_api.auth, headers=self.wp_api.headers)
            
            if response.status_code != 200:
                error_msg = f"獲取文章失敗: {response.status_code}"
                logger.error(error_msg)
                self._update_row_status(row_index, 'tags_from_description_status', 'failed')
                return
                
            data = response.json()
            title = data.get('title', {}).get('rendered', '')
            content = data.get('content', {}).get('rendered', '')
            video_description = data.get('meta', {}).get('video_description', '')
            
            if not video_description:
                error_msg = f"WP ID {wp_id} 沒有 video_description 欄位"
                logger.error(error_msg)
                self._update_row_status(row_index, 'tags_from_description_status', 'failed')
                return
            
            # 移除 HTML 標籤
            content = re.sub(r'<[^>]+>', '', content)
            content = content.strip()
            
            # 確保 video_description 是乾淨的文字
            video_description = video_description.strip()
            
            # 結合內容和影片描述
            combined_content = f"{content}\n\n影片描述：\n{video_description}"
            
            logger.debug(f"WP ID {wp_id} 的文章標題: {title}")
            logger.debug(f"WP ID {wp_id} 的影片描述長度: {len(video_description)} 字元")
            
            # 使用 TagSuggester 生成標籤
            try:
                tags = self.tag_suggester.suggest_tags(title, combined_content)
                logger.debug(f"TagSuggester 返回結果: {tags}")
            except Exception as tag_error:
                error_msg = f"TagSuggester 發生錯誤: {str(tag_error)}"
                logger.error(error_msg)
                self._update_row_status(row_index, 'tags_from_description_status', 'failed')
                return
            
            if not tags:
                error_msg = f"WP ID {wp_id} 無法生成標籤，TagSuggester 返回空結果"
                logger.error(error_msg)
                self._update_row_status(row_index, 'tags_from_description_status', 'failed')
                return
            
            if "existing_tags" not in tags:
                error_msg = f"WP ID {wp_id} 無法生成標籤，缺少 'existing_tags' 鍵"
                logger.error(error_msg)
                self._update_row_status(row_index, 'tags_from_description_status', 'failed')
                return
            
            # 檢查是否只有預設標籤
            has_only_default_tags = False
            if "tags" in tags["existing_tags"]:
                tag_list = tags["existing_tags"]["tags"]
                if isinstance(tag_list, list) and len(tag_list) == 1 and "feature" in tag_list:
                    has_only_default_tags = True
            
            if has_only_default_tags:
                error_msg = f"WP ID {wp_id} 只生成了預設標籤，標記為失敗"
                logger.warning(error_msg)
                self._update_row_status(row_index, 'tags_from_description_status', 'failed')
                return
            
            # 更新 WordPress 標籤
            try:
                # 確保標籤結果的格式正確
                if 'existing_tags' in tags and 'new_tag_suggestions' in tags:
                    tag_ids = self.wp_api.convert_tags_to_ids(tags)
                    logger.debug(f"WP ID {wp_id} 的標籤 ID: {tag_ids}")
                else:
                    error_msg = f"WP ID {wp_id} 的標籤結果格式不正確: {tags}"
                    logger.error(error_msg)
                    self._update_row_status(row_index, 'tags_from_description_status', 'failed')
                    return
            except Exception as convert_error:
                error_msg = f"WP ID {wp_id} 轉換標籤 ID 失敗: {str(convert_error)}"
                logger.error(error_msg)
                self._update_row_status(row_index, 'tags_from_description_status', 'failed')
                return
            
            if not tag_ids:
                error_msg = f"WP ID {wp_id} 生成的標籤無效，無法轉換為 ID"
                logger.warning(error_msg)
                self._update_row_status(row_index, 'tags_from_description_status', 'failed')
                return
            
            try:
                # 使用更新後的 update_post_tags 方法，它會使用 video_tag 分類法
                update_result = self.wp_api.update_post_tags(wp_id, tag_ids)
                logger.debug(f"WP ID {wp_id} 更新標籤結果: {update_result}")
                
                # 驗證標籤是否已關聯到文章
                verify_response = requests.get(
                    f"{self.wp_api.api_base}/video/{wp_id}?_fields=video_tag", 
                    auth=self.wp_api.auth, 
                    headers=self.wp_api.headers
                )
                
                if verify_response.status_code == 200:
                    data = verify_response.json()
                    if "video_tag" in data and data["video_tag"]:
                        logger.debug(f"WP ID {wp_id} 的標籤已成功關聯: {data['video_tag']}")
                        self._update_row_status(row_index, 'tags_from_description_status', 'completed')
                    else:
                        error_msg = f"WP ID {wp_id} 的標籤更新成功，但驗證時找不到標籤: {data}"
                        logger.warning(error_msg)
                        self._update_row_status(row_index, 'tags_from_description_status', 'failed')
                else:
                    error_msg = f"WP ID {wp_id} 驗證標籤關聯失敗: {verify_response.status_code}"
                    logger.error(error_msg)
                    self._update_row_status(row_index, 'tags_from_description_status', 'failed')
            except Exception as update_error:
                error_msg = f"WP ID {wp_id} 更新標籤時發生錯誤: {str(update_error)}"
                logger.error(error_msg)
                self._update_row_status(row_index, 'tags_from_description_status', 'failed')
                
        except Exception as e:
            error_msg = f"處理標籤時發生錯誤: {str(e)}"
            logger.exception(error_msg)
            try:
                self._update_row_status(row_index, 'tags_from_description_status', 'failed')
            except:
                pass
                
    def process_batch(self, batch_size: int = 5, row_range: tuple = None):
        """處理一批影片，可指定 row 範圍"""
        pending_rows = self._get_pending_rows(batch_size, row_range=row_range)
        
        for row in pending_rows:
            row_index = row['index']
            wp_id = row['wp_id']
            youtube_url = row['youtube_url']
            
            logger.info(f"處理第 {row_index} 列，WP ID: {wp_id}, YouTube URL: {youtube_url}")
            
            try:
                # 更新狀態為處理中
                self._update_row_status(row_index, 'video_description_status', 'processing')
                
                # 檢查 WP 文章是否存在 video_description 欄位
                has_description = self._check_video_description(wp_id)
                
                if has_description:
                    logger.info(f"WP ID {wp_id} 已有 video_description 欄位，跳過處理")
                    self._update_row_status(row_index, 'video_description_status', 'completed')
                    continue
                    
                # 尊重限流
                self._respect_rate_limit()
                
                # 使用 VideoDescriptionUpdater 處理
                success = self.video_updater.process_post(wp_id)
                self.gemini_call_count += 1
                
                if success:
                    logger.info(f"WP ID {wp_id} 的 video_description 欄位更新成功")
                    self._update_row_status(row_index, 'video_description_status', 'completed')
                    
                    # 處理標籤（如果需要）
                    self._process_tags(row_index, wp_id)
                else:
                    logger.error(f"WP ID {wp_id} 的 video_description 欄位更新失敗")
                    self._update_row_status(row_index, 'video_description_status', 'failed')
                    
            except Exception as e:
                logger.exception(f"處理第 {row_index} 列時發生錯誤: {str(e)}")
                self._update_row_status(row_index, 'video_description_status', 'failed')
                
    def run(self, total_batches: int = 10, batch_size: int = 5, row_range: tuple = None):
        """執行批次處理，可指定 row 範圍"""
        logger.info(f"開始批次處理，總批次: {total_batches}, 每批次大小: {batch_size}, row_range: {row_range}")
        
        for batch in range(total_batches):
            logger.info(f"處理批次 {batch + 1}/{total_batches}")
            self.process_batch(batch_size, row_range=row_range)
            
            # 批次之間加入延遲
            time.sleep(random.uniform(5, 10))
            
        logger.info("批次處理完成")

def main():
    parser = argparse.ArgumentParser(description='批次處理影片描述與標籤')
    parser.add_argument('--batches', type=int, default=10, help='處理批次數')
    parser.add_argument('--batch-size', type=int, default=5, help='每批次處理數量')
    parser.add_argument('--row', type=int, help='指定處理的 Google Sheets 行數')
    parser.add_argument('--row-range', type=str, help='指定處理的 Google Sheets 行數區間，例如 5000-5100')
    args = parser.parse_args()
    
    processor = BatchProcessor()
    
    row_range = None
    if args.row_range:
        try:
            start, end = [int(x) for x in args.row_range.split('-')]
            row_range = (start, end)
        except Exception:
            logger.error('row-range 格式錯誤，應為 5000-5100')
            return
    
    if args.row:
        # 處理指定行數
        logger.info(f"處理指定行數: {args.row}")
        processor.process_specific_row(args.row)
    else:
        # 批次處理
        processor.run(args.batches, args.batch_size, row_range=row_range)
    
if __name__ == "__main__":
    main()
