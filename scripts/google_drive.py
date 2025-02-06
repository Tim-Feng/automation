#!/usr/bin/env python3
import os
import json
import argparse
from typing import Optional, Dict, List
from pathlib import Path
import requests
from logger import setup_logger
from dotenv import load_dotenv
import sys

logger = setup_logger('google_drive')

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
            
            # 獲取父資料夾的 driveId
            drive_id = self.get_drive_id(parent_id, access_token)
            
            # 準備資料夾元數據
            metadata = {
                "name": folder_name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [parent_id]
            }
            
            if drive_id:
                metadata["driveId"] = drive_id
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            params = {
                "supportsAllDrives": True,
                "includeItemsFromAllDrives": True
            }
            
            response = requests.post(
                f"{self.base_url}/files",
                params=params,
                headers=headers,
                json=metadata
            )
            response.raise_for_status()
            
            folder_id = response.json()["id"]
            logger.info(f"Created folder: {folder_name} with ID: {folder_id}")
            return folder_id
            
        except Exception as e:
            logger.error(f"Failed to create folder: {str(e)}")
            raise

    def get_drive_id(self, file_id: str, access_token: str) -> Optional[str]:
        """獲取檔案所在的 Drive ID"""
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            params = {"supportsAllDrives": True, "fields": "driveId"}
            
            response = requests.get(
                f"{self.base_url}/files/{file_id}",
                headers=headers,
                params=params
            )
            response.raise_for_status()
            
            return response.json().get("driveId")
            
        except Exception as e:
            logger.error(f"Failed to get drive ID: {str(e)}")
            return None

    def find_folder(self, folder_name: str, parent_id: str) -> Optional[str]:
        """搜尋資料夾
        
        Args:
            folder_name: 資料夾名稱
            parent_id: 父資料夾 ID
            
        Returns:
            Optional[str]: 資料夾 ID，如果找不到則返回空字串
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
            
            response = requests.get(
                f"{self.base_url}/files",
                headers=headers,
                params=params
            )
            response.raise_for_status()
            
            files = response.json().get("files", [])
            if files:
                folder_id = files[0]["id"]
                logger.info(f"Found folder: {folder_name} with ID: {folder_id}")
                return folder_id
            
            logger.warning(f"Folder not found: {folder_name}")
            return ""
            
        except Exception as e:
            logger.error(f"Failed to find folder: {str(e)}")
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
        try:
            access_token = self.get_access_token()
            
            # 獲取 driveId
            drive_id = self.get_drive_id(folder_id, access_token)
            
            # 準備檔案元數據
            metadata = {
                "name": file_name,
                "parents": [folder_id]
            }
            
            if drive_id:
                metadata["driveId"] = drive_id
            
            # 創建上傳 session
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            params = {
                "uploadType": "resumable",
                "supportsAllDrives": True,
                "includeItemsFromAllDrives": True
            }
            
            response = requests.post(
                f"{self.upload_url}/files",
                params=params,
                headers=headers,
                json=metadata
            )
            response.raise_for_status()
            
            # 獲取上傳 URL
            upload_url = response.headers["Location"]
            
            # 獲取檔案 MIME type
            file_extension = Path(file_path).suffix.lower()
            content_type = "video/mp4" if file_extension == ".mp4" else "image/jpeg"
            
            # 上傳檔案內容
            with open(file_path, "rb") as f:
                upload_headers = {
                    "Content-Type": content_type
                }
                upload_response = requests.put(
                    upload_url,
                    data=f,
                    headers=upload_headers
                )
                upload_response.raise_for_status()
            
            file_id = upload_response.json()["id"]
            logger.info(f"Uploaded file: {file_name} with ID: {file_id}")
            return file_id
            
        except Exception as e:
            logger.error(f"Failed to upload file: {str(e)}")
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
            
    except Exception as e:
        logger.error(f"Operation failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()