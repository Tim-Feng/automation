#!/usr/bin/env python3
import os
import sys
import json
import requests
import logging
from typing import Dict, List, Set
import argparse
from urllib.parse import unquote
from dotenv import load_dotenv
from pathlib import Path
from logger import get_workflow_logger

logger = get_workflow_logger('1', 'taxonomy_manager')
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class WordPressTaxonomyManager:
    def __init__(self):
        """初始化 WordPress 分類管理工具"""
        base_dir = Path(__file__).resolve().parent.parent
        load_dotenv(base_dir / 'config' / '.env')
        
        self.site_url = os.getenv('WP_SITE_URL')
        self.username = os.getenv('WP_USERNAME')
        self.password = os.getenv('WP_APP_PASSWORD')
        
        if not self.username or not self.password:
            raise ValueError("請設定 WP_USERNAME 和 WP_APP_PASSWORD 環境變數")
            
        self.auth = (self.username, self.password)

    def _get_api_endpoint_for_taxonomy(self, taxonomy: str) -> str:
        """根據分類法名稱返回對應的 WordPress API 端點 slug。"""
        if taxonomy == 'categories' or taxonomy == 'video_category':
            return 'video_category'
        elif taxonomy == 'tags' or taxonomy == 'video_tag':
            return 'video_tag'
        else:
            # 呼叫者需要處理此 ValueError
            raise ValueError(f"_get_api_endpoint_for_taxonomy 中遇到未知的分類法: {taxonomy}")
        
    def delete_term(self, taxonomy: str, term_id: int) -> bool:
        """刪除分類或標籤
        
        Args:
            taxonomy: 分類法名稱（'categories' 或 'tags'）
            term_id: 要刪除的分類 ID
            
        Returns:
            bool: 刪除是否成功
        """
        # 使用輔助方法獲取 API 端點
        try:
            endpoint = self._get_api_endpoint_for_taxonomy(taxonomy)
        except ValueError as e:
            logger.error(f"在 delete_term 中獲取 API 端點時發生錯誤: {e}")
            raise
            
        url = f"{self.site_url}/wp-json/wp/v2/{endpoint}/{term_id}"
        
        logger.info(f"正在刪除 {taxonomy} ID {term_id}...")
        logger.info(f"API 端點: {url}")
        
        try:
            response = requests.delete(url, auth=self.auth, params={'force': True}, timeout=10)
            logger.info(f"API 回應狀態碼: {response.status_code}")
            logger.info(f"API 回應內容: {response.text}")
            
            if response.status_code != 200:
                logger.error(f"刪除 {taxonomy} 失敗: {response.status_code}")
                logger.error(f"錯誤訊息: {response.text}")
                raise Exception(f"刪除 {taxonomy} 失敗: {response.text}")
                
            return True
            
        except requests.exceptions.Timeout:
            logger.error("API 請求超時")
            raise Exception("API 請求超時，請稍後再試")
        except requests.exceptions.RequestException as e:
            logger.error(f"API 請求失敗: {str(e)}")
            raise Exception(f"API 請求失敗: {str(e)}")
    
    def update_term(self, taxonomy: str, term_id: int, name: str) -> Dict:
        """更新分類或標籤
        
        Args:
            taxonomy: 分類法名稱（'categories' 或 'tags'）
            term_id: 要更新的分類 ID
            name: 新的名稱
            
        Returns:
            Dict: 更新後的分類或標籤資訊
        """
        # 使用輔助方法獲取 API 端點
        try:
            endpoint = self._get_api_endpoint_for_taxonomy(taxonomy)
        except ValueError as e:
            logger.error(f"在 update_term 中獲取 API 端點時發生錯誤: {e}")
            raise
            
        url = f"{self.site_url}/wp-json/wp/v2/{endpoint}/{term_id}"
        data = {
            'name': name
        }
        
        logger.info(f"正在更新 {taxonomy} ID {term_id}...")
        logger.info(f"API 端點: {url}")
        logger.info(f"請求資料: {data}")
        
        try:
            response = requests.put(url, auth=self.auth, json=data, timeout=10)
            logger.info(f"API 回應狀態碼: {response.status_code}")
            logger.info(f"API 回應內容: {response.text}")
            
            if response.status_code != 200:
                logger.error(f"更新 {taxonomy} 失敗: {response.status_code}")
                logger.error(f"錯誤訊息: {response.text}")
                raise Exception(f"更新 {taxonomy} 失敗: {response.text}")
                
            return response.json()
            
        except requests.exceptions.Timeout:
            logger.error("API 請求超時")
            raise Exception("API 請求超時，請稍後再試")
        except requests.exceptions.RequestException as e:
            logger.error(f"API 請求失敗: {str(e)}")
            raise Exception(f"API 請求失敗: {str(e)}")
    
    def create_term(self, taxonomy: str, name: str) -> Dict:
        """創建新的分類或標籤
        
        Args:
            taxonomy: 分類法名稱（'categories' 或 'tags'）
            name: 分類或標籤的名稱
            
        Returns:
            Dict: 新創建的分類或標籤資訊
        """
        # 使用輔助方法獲取 API 端點
        try:
            endpoint = self._get_api_endpoint_for_taxonomy(taxonomy)
        except ValueError as e:
            # 可以選擇重新拋出錯誤，或者記錄並處理
            logger.error(f"在 create_term 中獲取 API 端點時發生錯誤: {e}")
            raise  # 重新拋出原始錯誤，讓呼叫者知道
            
        url = f"{self.site_url}/wp-json/wp/v2/{endpoint}"
        data = {
            'name': name,
            'description': ''
        }
        
        logger.info(f"正在創建新的 {taxonomy}...")
        logger.info(f"API 端點: {url}")
        logger.info(f"請求資料: {data}")
        
        try:
            response = requests.post(url, auth=self.auth, json=data, timeout=10)
            logger.info(f"API 回應狀態碼: {response.status_code}")
            logger.info(f"API 回應內容: {response.text}")
            
            if response.status_code != 201:
                logger.error(f"創建 {taxonomy} 失敗: {response.status_code}")
                logger.error(f"錯誤訊息: {response.text}")
                raise Exception(f"創建 {taxonomy} 失敗: {response.text}")
                
            return response.json()
            
        except requests.exceptions.Timeout:
            logger.error("API 請求超時")
            raise Exception("API 請求超時，請稍後再試")
        except requests.exceptions.RequestException as e:
            logger.error(f"API 請求失敗: {str(e)}")
            raise Exception(f"API 請求失敗: {str(e)}")
        
    def get_all_terms(self, taxonomy: str) -> List[Dict]:
        """取得指定分類法的所有項目
        
        Args:
            taxonomy: 分類法名稱（'categories' 或 'tags'）
            
        Returns:
            List[Dict]: 分類項目列表
        """
        items = []
        page = 1
        per_page = 100
        
        # 使用輔助方法獲取 API 端點
        try:
            endpoint = self._get_api_endpoint_for_taxonomy(taxonomy)
        except ValueError as e:
            logger.error(f"在 get_all_terms 中獲取 API 端點時發生錯誤: {e}")
            # 根據方法設計，這裡可能適合返回空列表或重新拋出錯誤
            # 鑑於原始碼中若 API 請求失敗會 break，這裡也選擇重新拋出
            raise
        
        while True:
            url = f"{self.site_url}/wp-json/wp/v2/{endpoint}?page={page}&per_page={per_page}"
            response = requests.get(url, auth=self.auth)
            
            if response.status_code == 400:  # 沒有更多頁面
                break
                
            if response.status_code != 200:
                logger.error(f"取得 {taxonomy} 失敗: {response.status_code}")
                logger.error(f"錯誤訊息: {response.text}")
                break
                
            current_items = response.json()
            if not current_items:
                break
                
            items.extend(current_items)
            page += 1
            
            # 記錄一些有用的信息
            if page == 1:
                total = response.headers.get('X-WP-Total')
                if total:
                    logger.info(f"總計找到 {total} 個{taxonomy}")
            
        return items
        
    def load_json_categories(self, json_files: List[str]) -> tuple[set[str], dict[str, set[str]]]:
        """讀取 JSON 檔案中的分類
        
        Args:
            json_files: JSON 檔案列表
            
        Returns:
            tuple: (分類名稱集合, 別名對應字典)
        """
        categories = set()
        aliases_map = {}
        
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for item in data:
                        # 將主要分類名稱加入集合
                        name_val = item['name']  # Updated to use 'name' instead of 'tag'
                        categories.add(name_val)
                        
                        # 建立別名對應關係
                        if 'aliases' in item:
                            for alias in item['aliases']:
                                if alias != name_val:  # 不要把主分類當作別名
                                    if alias not in aliases_map:
                                        aliases_map[alias] = set()
                                    aliases_map[alias].add(tag)
            except Exception as e:
                logger.error(f"讀取 JSON 檔案 {json_file} 失敗: {e}")
        
        return categories, aliases_map
    
    def get_existing_categories(self) -> Dict[str, int]:
        """取得網站上現有的分類和其 ID
        
        Returns:
            Dict[str, int]: 分類名稱對應的 ID
        """
        terms = self.get_all_terms('categories')
        return {unquote(term['name']): term['id'] for term in terms}
    
    def sync_categories(self, json_files: List[str], dry_run: bool = True) -> None:
        """同步分類
        
        Args:
            json_files: JSON 檔案列表
            dry_run: 是否為預演模式，預設為 True
        """
        # 從 JSON 檔案讀取分類和別名對應
        json_categories, aliases_map = self.load_json_categories(json_files)
        
        # 從 WordPress 獲取現有分類
        wp_categories = self.get_all_terms('categories')
        wp_category_names = {unquote(cat.get('name', '')) for cat in wp_categories}
        
        # 特殊處理：保留有對應別名的分類
        preserved_categories = {'8 bit pixel art'}  # 特殊視覺風格，需要保留
        
        # 檢查每個現有分類是否有對應的新分類
        for wp_category in wp_category_names:
            # 如果這個分類名稱在別名對應表中
            if wp_category in aliases_map:
                preserved_categories.add(wp_category)
        
        # 找出需要新增和刪除的分類
        categories_to_add = json_categories - wp_category_names
        categories_to_delete = wp_category_names - json_categories - preserved_categories
        
        # 顯示差異
        print("\n=== 分類比對結果 ===")
        print(f"JSON 檔案中的分類數量: {len(json_categories)}")
        print(f"網站上的分類數量: {len(wp_categories)}")
        print(f"需要新增的分類數量: {len(categories_to_add)}")
        print(f"可能需要刪除的分類數量: {len(categories_to_delete)}")
        
        if categories_to_add:
            print("\n需要新增的分類:")
            for category in sorted(categories_to_add):
                print(f"- {category}")
        
        if categories_to_delete:
            print("\n可能需要刪除的分類:")
            for category in sorted(categories_to_delete):
                for cat in wp_categories:
                    category_name = unquote(cat.get('name', ''))
                    category_id = cat.get('id')
                    if category_name == category:
                        print(f"- {category} (ID: {category_id})")
        
        if not dry_run:
            # 1. 刪除不需要的分類
            if categories_to_delete:
                print("\n=== 開始刪除分類 ===")
                for category in categories_to_delete:
                    for cat in wp_categories:
                        if unquote(cat.get('name', '')) == category:
                            try:
                                response = requests.delete(
                                    f"{self.site_url}/wp-json/wp/v2/categories/{cat['id']}",
                                    auth=(self.username, self.password)
                                )
                                if response.status_code == 200:
                                    print(f"刪除分類 '{category}' (ID: {cat['id']}) 成功")
                                else:
                                    logger.error(f"刪除分類 '{category}' 失敗: {response.text}")
                            except Exception as e:
                                logger.error(f"刪除分類 '{category}' 失敗: {e}")
            
            # 2. 更新保留的分類
            if preserved_categories:
                print("\n=== 開始更新保留的分類 ===")
                for category in preserved_categories:
                    # 如果這個分類有對應的新分類
                    if category in aliases_map:
                        new_categories = aliases_map[category]
                        for new_category in new_categories:
                            print(f"將保留 '{category}' 對應到新分類 '{new_category}'")
            
            # 3. 新增缺少的分類
            if categories_to_add:
                print("\n=== 開始新增分類 ===")
                for category in categories_to_add:
                    try:
                        term = self.create_term('categories', category)
                        print(f"創建分類 '{category}' 成功，ID: {term.get('id')}")
                    except Exception as e:
                        logger.error(f"創建分類 '{category}' 失敗: {e}")
    
    def display_terms(self, items: List[Dict], taxonomy: str):
        """顯示分類項目資訊
        
        Args:
            items: 分類項目列表
            taxonomy: 分類法名稱（用於顯示）
        """
        print(f"\n=== WordPress {taxonomy} 列表 ===")
        print(f"總計: {len(items)} 個項目\n")
        
        for item in items:
            print(f"ID: {item.get('id')}")
            # 如果是分類，則從 title 取得名稱，否則從 name 取得
            name = None
            if taxonomy == 'categories':
                title = item.get('title', {})
                if isinstance(title, dict):
                    name = title.get('rendered')
                else:
                    name = title
            else:
                name = item.get('name')
                
            # URL 解碼名稱和代稱
            display_name = unquote(name if name else item.get('slug'))
            display_slug = unquote(item.get('slug'))
            print(f"名稱: {display_name}")
            print(f"代稱: {display_slug}")
            
            # 如果有 count 欄位才顯示
            count = item.get('count')
            if count is not None:
                print(f"文章數: {count}")
                
            # 如果有描述且不是空的才顯示
            content = None
            if taxonomy == 'categories':
                content_obj = item.get('content', {})
                if isinstance(content_obj, dict):
                    content = content_obj.get('rendered')
                else:
                    content = content_obj
            else:
                content = item.get('description')
                
            if content and str(content).strip():
                print(f"描述: {content}")
                
            print("-" * 30)
            
    def add_and_update_new_terms_from_json(self, json_file_paths: List[str], taxonomy_arg: str) -> None:
        """
        從 JSON 檔案讀取詞彙，為 ID 為 null 的詞彙在 WordPress 中創建新分類或標籤，
        並用新的 ID 更新 JSON 檔案。

        Args:
            json_file_paths: 包含詞彙資訊的 JSON 檔案路徑列表。
            taxonomy_arg: 要操作的分類法 ('categories' 或 'tags')。
        """
        for file_path_str in json_file_paths:
            file_path = Path(file_path_str)
            logger.info(f"正在處理 JSON 檔案: {file_path}")
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    terms_data = json.load(f)
                
                if not isinstance(terms_data, list):
                    logger.warning(f"JSON 檔案 {file_path} 的頂層不是列表，跳過。")
                    continue

                updated_in_file = False
                for term_item in terms_data:
                    if isinstance(term_item, dict) and term_item.get('id') is None:
                        term_name = term_item.get('name')
                        if term_name:
                            wp_taxonomy_slug = 'video_tag' if taxonomy_arg == 'tags' else taxonomy_arg
                            logger.info(f"在 {file_path} 中找到 ID 為 null 的詞彙: '{term_name}'。嘗試在 '{wp_taxonomy_slug}' 中創建...")
                            try:
                                new_term_info = self.create_term(taxonomy=wp_taxonomy_slug, name=term_name)
                                new_id = new_term_info.get('id')
                                if new_id:
                                    term_item['id'] = new_id
                                    updated_in_file = True
                            except Exception as e:
                                logger.error(f"為 '{term_name}' 在 '{wp_taxonomy_slug}' 中創建項目時發生錯誤: {e}")
                        else:
                            logger.warning(f"在 {file_path} 中找到 ID 為 null 但缺少 'name' 欄位的項目，跳過: {term_item}")
                
                if updated_in_file:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(terms_data, f, ensure_ascii=False, indent=4)
                    logger.info(f"JSON 檔案 {file_path} 已成功更新並儲存。")
                else:
                    logger.info(f"JSON 檔案 {file_path} 無需更新。")

            except FileNotFoundError:
                logger.error(f"JSON 檔案未找到: {file_path}")
            except json.JSONDecodeError:
                logger.error(f"解析 JSON 檔案失敗: {file_path}")
            except Exception as e:
                logger.error(f"處理 JSON 檔案 {file_path} 時發生未預期錯誤: {e}")


def main():
    try:
        parser = argparse.ArgumentParser(description='WordPress 分類管理工具')
        parser.add_argument('action', choices=['list', 'create', 'update', 'delete', 'sync', 'add_and_update'], 
                          help='要執行的操作（list、create、update、delete、sync 或 add_and_update）')
        parser.add_argument('taxonomy', choices=['categories', 'tags'], 
                          help='要管理的分類法（categories 或 tags）')
        parser.add_argument('--name', help='分類或標籤的名稱（create 或 update 時需要）')
        parser.add_argument('--id', type=int, nargs='+', help='分類 ID（update 或 delete 時需要，可指定多個 ID）')
        parser.add_argument('--force', action='store_true', help='強制刪除，不需要確認 (用於指定 ID 刪除)')
        parser.add_argument('--delete-all', action='store_true', help='刪除指定分類法下的所有項目（僅限 delete 操作）')
        parser.add_argument('--json-files', nargs='+', help='JSON 檔案路徑（sync 時需要）')
        parser.add_argument('--dry-run', action='store_true', help='模擬執行，不實際執行操作')
        parser.add_argument('--output-json', help='將 list 操作的原始輸出結果儲存到指定的 JSON 檔案路徑 (僅限 list 操作)')
        args = parser.parse_args()
        
        wp = WordPressTaxonomyManager()
        
        if args.action == 'sync':
            if args.taxonomy != 'categories':
                logger.error('目前只支援同步分類，不支援標籤')
                sys.exit(1)
            if not args.json_files:
                logger.error('同步時必須提供 --json-files 參數')
                sys.exit(1)
                
            wp.sync_categories(args.json_files, args.dry_run)
            
        elif args.action == 'add_and_update':
            if not args.json_files:
                logger.error('執行 add_and_update 操作時必須提供 --json-files 參數')
                sys.exit(1)
            # 注意：add_and_update_new_terms_from_json 目前預設處理 'categories'
            # taxonomy 參數在此操作中會被忽略
            logger.info(f"準備從 JSON 檔案新增分類並更新 ID: {args.json_files}")
            wp.add_and_update_new_terms_from_json(args.json_files, args.taxonomy)
            logger.info("JSON 檔案處理完成。")

        elif args.action == 'list':
            terms = wp.get_all_terms(args.taxonomy)
            if not terms:
                print(f"找不到任何 {args.taxonomy}")
                sys.exit(0)

            if args.output_json:
                try:
                    with open(args.output_json, 'w', encoding='utf-8') as f:
                        json.dump(terms, f, ensure_ascii=False, indent=4)
                    print(f"已成功將 {len(terms)} 個 {args.taxonomy} 備份到檔案: {args.output_json}")
                except IOError as e:
                    logger.error(f"寫入 JSON 檔案 {args.output_json} 時發生錯誤: {e}")
                    sys.exit(1)
            else:
                # 維持原有的控制台輸出邏輯，與 display_terms 方法一致
                print(f"\n=== 所有 {args.taxonomy} ===")
                for term in terms:
                    print(f"ID: {term.get('id')}")
                    print(f"名稱: {unquote(term.get('name', ''))}")
                    print(f"代稱: {unquote(term.get('slug', ''))}")
                    print(f"文章數: {term.get('count', 0)}")
                    print(f"連結: {term.get('link', '')}")
                    print("-" * 30)
            
        elif args.action == 'create':
            if not args.name:
                logger.error('創建新分類或標籤時必須提供 --name 參數')
                sys.exit(1)
            term = wp.create_term(args.taxonomy, args.name)
            print(f"\n=== 創建新的 {args.taxonomy} ===")
            print(f"ID: {term.get('id')}")
            print(f"名稱: {unquote(term.get('name', ''))}")
            print(f"代稱: {unquote(term.get('slug', ''))}")
            print("-" * 30)
            
        elif args.action == 'update':
            if not args.id:
                logger.error('更新分類或標籤時必須提供 --id 參數')
                sys.exit(1)
            if not args.name:
                logger.error('更新分類或標籤時必須提供 --name 參數')
                sys.exit(1)
            updated_count = 0
            for term_id_to_update in args.id: # 遍歷 ID 列表
                try:
                    term = wp.update_term(args.taxonomy, term_id_to_update, args.name) # 使用單一 ID
                    print(f"\n=== 更新後的 {args.taxonomy} (ID: {term_id_to_update}) ===")
                    print(f"ID: {term.get('id')}")
                    print(f"名稱: {unquote(term.get('name', ''))}")
                    print(f"代稱: {unquote(term.get('slug', ''))}")
                    print("-" * 30)
                    updated_count += 1
                except Exception as e:
                    print(f"更新 ID {term_id_to_update} 時發生錯誤: {e}")
            
            if updated_count > 0:
                print(f"\n批次更新完成，共更新 {updated_count} 個項目。")
            else:
                print(f"\n沒有項目被更新。")
            
        elif args.action == 'delete':
            if args.delete_all:
                if args.id:
                    logger.error("使用 --delete-all 時，不應同時指定 --id。請擇一使用。")
                    sys.exit(1)
                
                logger.info(f"準備刪除所有 '{args.taxonomy}' 分類法下的項目...")
                all_terms = wp.get_all_terms(args.taxonomy)

                if not all_terms:
                    print(f"在 '{args.taxonomy}' 分類法下找不到任何項目可供刪除。")
                    sys.exit(0)

                print(f"\n警告：即將刪除 '{args.taxonomy}' 分類法下的所有 {len(all_terms)} 個項目。")
                print("此操作無法復原！")
                
                print("\n部分即將刪除的項目預覽：")
                for i, term_preview in enumerate(all_terms[:5]):
                     print(f"  ID: {term_preview.get('id')}, 名稱: {unquote(term_preview.get('name', ''))}")
                if len(all_terms) > 5:
                    print(f"  ...以及其他 {len(all_terms) - 5} 個項目。")

                confirm_delete_all = input(f"\n您確定要刪除所有 '{args.taxonomy}' 項目嗎？此操作無法復原！\n請輸入 'YES' (全大寫) 確認：")
                
                if confirm_delete_all == 'YES':
                    deleted_count = 0
                    failed_count = 0
                    print(f"\n開始刪除所有 '{args.taxonomy}' 項目...")
                    for term_to_delete in all_terms:
                        term_id = term_to_delete.get('id')
                        term_name = unquote(term_to_delete.get('name', ''))
                        try:
                            wp.delete_term(args.taxonomy, term_id)
                            print(f"  已成功刪除 ID {term_id} (名稱: {term_name}) 的 {args.taxonomy}")
                            deleted_count += 1
                        except Exception as e:
                            print(f"  刪除 ID {term_id} (名稱: {term_name}) 時發生錯誤: {e}")
                            failed_count += 1
                    
                    print(f"\n全部刪除操作完成。成功刪除 {deleted_count} 個項目，失敗 {failed_count} 個項目。")
                else:
                    print("取消全部刪除操作。")
                    sys.exit(0)

            elif args.id:
                # 原本處理指定 ID 刪除的邏輯
                if not args.force:
                    terms_data = wp.get_all_terms(args.taxonomy) # 重新命名變數以避免與外層衝突
                    terms_to_delete_specific = []
                    
                    print(f"\n要刪除的 {args.taxonomy}:")
                    for term_id_specific in args.id:
                        term_found = next((t for t in terms_data if t.get('id') == term_id_specific), None)
                        if term_found:
                            terms_to_delete_specific.append(term_found)
                            print(f"\nID: {term_found.get('id')}")
                            print(f"名稱: {unquote(term_found.get('name', ''))}")
                            print(f"代稱: {unquote(term_found.get('slug', ''))}")
                            print(f"文章數: {term_found.get('count', 0)}")
                            print("-" * 30)
                        else:
                            print(f"找不到 ID 為 {term_id_specific} 的 {args.taxonomy}")
                    
                    if terms_to_delete_specific:
                        confirm = input(f'確定要刪除這 {len(terms_to_delete_specific)} 個項目嗎？[是/否] ')
                        if confirm.lower() not in ['是', 'y', 'yes']:
                            print('取消刪除操作')
                            sys.exit(0)
                    else:
                        print(f"沒有找到任何要刪除的 {args.taxonomy}")
                        sys.exit(1)
                
                deleted_count_specific = 0
                for term_id_to_delete in args.id:
                    try:
                        wp.delete_term(args.taxonomy, term_id_to_delete)
                        print(f"=== 已成功刪除 ID {term_id_to_delete} 的 {args.taxonomy} ===")
                        deleted_count_specific += 1
                    except Exception as e:
                        print(f"刪除 ID {term_id_to_delete} 時發生錯誤: {e}")
                
                if deleted_count_specific > 0:
                    print(f"\n批次刪除完成，共刪除 {deleted_count_specific} 個指定項目。")
                else:
                    print(f"\n指定的項目均未被刪除或未找到。")
            else:
                 logger.error('刪除操作必須提供 --id 參數或使用 --delete-all 選項。')
                 sys.exit(1)
        
    except Exception as e:
        logger.error(f"執行時發生錯誤: {e}")
        sys.exit(1)
        
if __name__ == '__main__':
    main()
