#!/usr/bin/env python3
import os
import json
import argparse
from typing import Optional, Dict, List
from pathlib import Path
import requests
from logger import get_workflow_logger
from dotenv import load_dotenv
import sys
import time
from requests.exceptions import RequestException, ConnectionError

logger = get_workflow_logger('4', 'google_drive')  # Stage-4 因為這是最後的範本處理階段，主要用於上傳成品

# 重試相關常量
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 1  # 初始重試延遲（秒）

class GoogleDriveAPI:
    def __init__(self):
        """初始化 Google Drive API 客戶端"""
        self.load_credentials()
        self.base_url = "https://www.googleapis.com/drive/v3"
        self.upload_url = "https://www.googleapis.com/upload/drive/v3"

    def load_credentials(self):
        """載入憑證"""
        try:
            self.refresh_token = os.getenv("REFRESH_TOKEN")
            self.client_id = os.getenv("CLIENT_ID")
            self.client_secret = os.getenv("CLIENT_SECRET")
            
            if not all([self.refresh_token, self.client_id, self.client_secret]):
                raise ValueError("Missing required environment variables")
                
        except Exception as e:
            logger.error(f"Failed to load credentials: {str(e)}")
            raise

    def get_access_token(self) -> str:
        """獲取新的 access token"""
        try:
            token_url = "https://oauth2.googleapis.com/token"
            data = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token"
            }
            
            response = requests.post(token_url, data=data)
            response.raise_for_status()
            
            return response.json()["access_token"]
            
        except Exception as e:
            logger.error(f"Failed to get access token: {str(e)}")
            raise

    def create_folder(self, folder_name: str, parent_id: str) -> str:
        """創建資料夾
        
        Args:
            folder_name: 資料夾名稱
            parent_id: 父資料夾 ID
            
        Returns:
            str: 新建資料夾的 ID
        """
        try:
            access_token = self.get_access_token()
            drive_id = self.get_drive_id(parent_id, access_token)
            
            metadata = {
                "name": folder_name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [parent_id],
                "driveId": drive_id
            }
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            params = {
                "supportsAllDrives": True,
                "includeItemsFromAllDrives": True
            }
            
            for attempt in range(MAX_RETRIES):
                try:
                    response = requests.post(
                        f"{self.base_url}/files",
                        params=params,
                        headers=headers,
                        json=metadata
                    )
                    response.raise_for_status()
                    
                    folder_id = response.json()["id"]
                    return folder_id
                    
                except ConnectionError as e:
                    if attempt == MAX_RETRIES - 1:
                        logger.error(f"創建資料夾失敗: {str(e)}")
                        raise
                    time.sleep(INITIAL_RETRY_DELAY * (2 ** attempt))
                    
                except Exception as e:
                    logger.error(f"創建資料夾失敗: {str(e)}")
                    raise
            
        except Exception as e:
            logger.error(f"創建資料夾失敗: {str(e)}")
            raise

    def create_google_docs(self, name: str, parent_id: str) -> str:
        """創建 Google Docs
        
        Args:
            name: 文件名稱
            parent_id: 父資料夾 ID
            
        Returns:
            str: 新建文件的 ID
        """
        try:
            access_token = self.get_access_token()
            drive_id = self.get_drive_id(parent_id, access_token)
            
            metadata = {
                "name": name,
                "mimeType": "application/vnd.google-apps.document",
                "parents": [parent_id],
                "driveId": drive_id
            }
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            params = {
                "supportsAllDrives": True,
                "includeItemsFromAllDrives": True
            }
            
            for attempt in range(MAX_RETRIES):
                try:
                    response = requests.post(
                        f"{self.base_url}/files",
                        params=params,
                        headers=headers,
                        json=metadata
                    )
                    response.raise_for_status()
                    
                    docs_id = response.json()["id"]
                    return docs_id
                    
                except ConnectionError as e:
                    if attempt == MAX_RETRIES - 1:
                        logger.error(f"創建 Google Docs 失敗: {str(e)}")
                        raise
                    time.sleep(INITIAL_RETRY_DELAY * (2 ** attempt))
                    
                except Exception as e:
                    logger.error(f"創建 Google Docs 失敗: {str(e)}")
                    raise
            
        except Exception as e:
            logger.error(f"創建 Google Docs 失敗: {str(e)}")
            raise

    def get_drive_id(self, file_id: str, access_token: str) -> str:
        """獲取檔案所在的 Drive ID"""
        for attempt in range(MAX_RETRIES):
            try:
                headers = {"Authorization": f"Bearer {access_token}"}
                params = {"supportsAllDrives": True, "fields": "driveId"}
                
                response = requests.get(
                    f"{self.base_url}/files/{file_id}",
                    headers=headers,
                    params=params
                )
                response.raise_for_status()
                
                drive_id = response.json().get("driveId")
                if not drive_id:
                    raise ValueError(f"無法獲取檔案 {file_id} 的 Drive ID")
                return drive_id
                
            except ConnectionError as e:
                if attempt == MAX_RETRIES - 1:
                    logger.error(f"獲取 Drive ID 失敗: {str(e)}")
                    raise
                time.sleep(INITIAL_RETRY_DELAY * (2 ** attempt))
                
            except Exception as e:
                logger.error(f"獲取 Drive ID 失敗: {str(e)}")
                raise

    def find_folder(self, folder_name: str, parent_id: str) -> Optional[str]:
        """搜尋資料夾
        
        Args:
            folder_name: 資料夾名稱
            parent_id: 父資料夾 ID
            
        Returns:
            Optional[str]: 資料夾 ID，如果找不到則返回 None
        """
        try:
            access_token = self.get_access_token()
            
            query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and '{parent_id}' in parents and trashed=false"
            
            headers = {"Authorization": f"Bearer {access_token}"}
            params = {
                "q": query,
                "supportsAllDrives": True,
                "includeItemsFromAllDrives": True,
                "corpora": "allDrives"
            }
            
            for attempt in range(MAX_RETRIES):
                try:
                    response = requests.get(
                        f"{self.base_url}/files",
                        headers=headers,
                        params=params
                    )
                    response.raise_for_status()
                    
                    files = response.json().get("files", [])
                    return files[0]["id"] if files else None
                    
                except ConnectionError as e:
                    if attempt == MAX_RETRIES - 1:
                        logger.error(f"搜尋資料夾失敗: {str(e)}")
                        raise
                    time.sleep(INITIAL_RETRY_DELAY * (2 ** attempt))
                    
                except Exception as e:
                    logger.error(f"搜尋資料夾失敗: {str(e)}")
                    raise
            
        except Exception as e:
            logger.error(f"搜尋資料夾失敗: {str(e)}")
            raise

    def upload_file(self, file_path: str, file_name: str, folder_id: str) -> str:
        """上傳檔案
        
        Args:
            file_path: 檔案路徑
            file_name: 檔案名稱
            folder_id: 目標資料夾 ID
            
        Returns:
            str: 上傳檔案的 ID
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"檔案不存在: {file_path}")
            
        try:
            access_token = self.get_access_token()
            drive_id = self.get_drive_id(folder_id, access_token)
            
            metadata = {
                "name": file_name,
                "parents": [folder_id],
                "driveId": drive_id
            }
            
            with open(file_path, 'rb') as file_content:
                # 第一步：獲取上傳 URL
                for attempt in range(MAX_RETRIES):
                    try:
                        headers = {
                            "Authorization": f"Bearer {access_token}",
                            "Content-Type": "application/json"
                        }
                        params = {
                            "uploadType": "resumable",
                            "supportsAllDrives": True
                        }
                        
                        response = requests.post(
                            f"{self.upload_url}/files",
                            params=params,
                            headers=headers,
                            json=metadata
                        )
                        response.raise_for_status()
                        
                        upload_url = response.headers.get('Location')
                        if not upload_url:
                            raise ValueError("無法獲取上傳 URL")
                        break
                        
                    except ConnectionError as e:
                        if attempt == MAX_RETRIES - 1:
                            logger.error(f"獲取上傳 URL 失敗: {str(e)}")
                            raise
                        time.sleep(INITIAL_RETRY_DELAY * (2 ** attempt))
                
                # 第二步：上傳檔案內容
                file_size = os.path.getsize(file_path)
                headers = {
                    "Content-Length": str(file_size),
                    "Content-Type": "application/octet-stream"
                }
                
                for attempt in range(MAX_RETRIES):
                    try:
                        response = requests.put(
                            upload_url,
                            data=file_content,
                            headers=headers
                        )
                        response.raise_for_status()
                        
                        file_id = response.json()["id"]
                        return file_id
                        
                    except ConnectionError as e:
                        if attempt == MAX_RETRIES - 1:
                            logger.error(f"上傳檔案失敗: {str(e)}")
                            raise
                        time.sleep(INITIAL_RETRY_DELAY * (2 ** attempt))
                        file_content.seek(0)
                    
                    except Exception as e:
                        logger.error(f"上傳檔案失敗: {str(e)}")
                        raise
        
        except Exception as e:
            logger.error(f"上傳檔案失敗: {str(e)}")
            raise

def main():
    parser = argparse.ArgumentParser(description="Google Drive Operations")
    parser.add_argument("--create-folder", nargs=2, metavar=("NAME", "PARENT_ID"),
                      help="Create a new folder")
    parser.add_argument("--find-folder", nargs=2, metavar=("NAME", "PARENT_ID"),
                      help="Find a folder")
    parser.add_argument("--upload-file", nargs=3, 
                      metavar=("FILE_PATH", "FILE_NAME", "FOLDER_ID"),
                      help="Upload a file")
    parser.add_argument("--create-docs", nargs=2,
                      metavar=("NAME", "PARENT_ID"),
                      help="Create a Google Docs in the specified folder")
    
    args = parser.parse_args()
    
    # 載入環境變數
    dotenv_path = Path(__file__).parent.parent / "config" / ".env"
    load_dotenv(str(dotenv_path))
    
    drive = GoogleDriveAPI()
    
    try:
        if args.create_folder:
            folder_id = drive.create_folder(args.create_folder[0], args.create_folder[1])
            print(folder_id)
            
        elif args.find_folder:
            folder_id = drive.find_folder(args.find_folder[0], args.find_folder[1])
            print(folder_id)
            
        elif args.upload_file:
            file_id = drive.upload_file(args.upload_file[0], 
                                      args.upload_file[1], 
                                      args.upload_file[2])
            print(file_id)
            
        elif args.create_docs:
            docs_id = drive.create_google_docs(args.create_docs[0], args.create_docs[1])
            print(docs_id)
            
    except Exception as e:
        logger.error(f"Operation failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()