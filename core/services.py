import os
import json
from typing import List, Dict, Optional
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from django.conf import settings


class GoogleDriveService:
    """Service for interacting with Google Drive API"""
    
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
    
    def __init__(self):
        self.credentials_file = settings.GOOGLE_DRIVE_CREDENTIALS_FILE
        self.token_file = settings.GOOGLE_DRIVE_TOKEN_FILE
        self.service = None
    
    def authenticate(self):
        """Authenticate with Google Drive API using service account"""
        try:
            # Check if credentials file exists
            if not self.credentials_file or not os.path.exists(self.credentials_file):
                raise FileNotFoundError(
                    f"Google Drive credentials file not found: {self.credentials_file}"
                )
            
            # Use service account credentials
            creds = service_account.Credentials.from_service_account_file(
                self.credentials_file, scopes=self.SCOPES
            )
            
            self.service = build('drive', 'v3', credentials=creds)
            return self.service
            
        except Exception as e:
            print(f"Authentication error: {e}")
            raise
    
    def get_folder_id(self, folder_name: str, parent_folder_name: str = None) -> Optional[str]:
        """Get folder ID by name"""
        if not self.service:
            self.authenticate()
        
        query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder'"
        if parent_folder_name:
            parent_id = self.get_folder_id(parent_folder_name)
            if parent_id:
                query += f" and '{parent_id}' in parents"
        
        try:
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)'
            ).execute()
            
            files = results.get('files', [])
            return files[0]['id'] if files else None
        except HttpError as error:
            print(f'An error occurred: {error}')
            return None
    
    def get_public_carousel_images(self) -> List[Dict]:
        """Get images from the 'public' folder for carousel display"""
        if not self.service:
            self.authenticate()
        
        # Get Public_Portfolio folder ID
        portfolio_folder_id = self.get_folder_id('Public_Portfolio')
        if not portfolio_folder_id:
            return []
        
        # Get 'public' folder ID
        public_folder_id = self.get_folder_id('public', 'Public_Portfolio')
        if not public_folder_id:
            return []
        
        try:
            results = self.service.files().list(
                q=f"'{public_folder_id}' in parents and trashed=false",
                spaces='drive',
                fields='files(id, name, mimeType, webViewLink, thumbnailLink, size, imageMediaMetadata)',
                orderBy='name'
            ).execute()
            
            files = results.get('files', [])
            # Filter for image files
            image_files = []
            for file in files:
                if file['mimeType'].startswith('image/'):
                    # Use the original thumbnailLink which works
                    image_url = file.get('thumbnailLink', '')
                    if not image_url:
                        # Fallback to direct view URL
                        image_url = f"https://drive.google.com/uc?export=view&id={file['id']}"
                    
                    image_files.append({
                        'id': file['id'],
                        'name': file['name'],
                        'mime_type': file['mimeType'],
                        'web_view_link': file.get('webViewLink', ''),
                        'thumbnail_link': file.get('thumbnailLink', ''),
                        'download_url': image_url,
                        'size': file.get('size', ''),
                        'dimensions': file.get('imageMediaMetadata', {}).get('width', 0) if file.get('imageMediaMetadata') else 0
                    })
            
            return image_files
        except HttpError as error:
            print(f'An error occurred: {error}')
            return []
    
    def get_files_in_folder(self, folder_name: str, parent_folder_name: str = None) -> List[Dict]:
        """Get all files in a folder"""
        if not self.service:
            self.authenticate()
        
        folder_id = self.get_folder_id(folder_name, parent_folder_name)
        if not folder_id:
            return []
        
        try:
            results = self.service.files().list(
                q=f"'{folder_id}' in parents and trashed=false",
                spaces='drive',
                fields='files(id, name, mimeType, webViewLink, thumbnailLink)',
                orderBy='name'
            ).execute()
            
            files = results.get('files', [])
            # Filter for image files
            image_files = []
            for file in files:
                if file['mimeType'].startswith('image/'):
                    # Use the original thumbnailLink which works
                    image_url = file.get('thumbnailLink', '')
                    if not image_url:
                        # Fallback to direct download URL
                        image_url = f"https://drive.google.com/uc?export=view&id={file['id']}"
                    
                    image_files.append({
                        'id': file['id'],
                        'name': file['name'],
                        'mime_type': file['mimeType'],
                        'web_view_link': file.get('webViewLink', ''),
                        'thumbnail_link': file.get('thumbnailLink', ''),
                        'download_url': image_url
                    })
            
            return image_files
        except HttpError as error:
            print(f'An error occurred: {error}')
            return []
    
    def get_public_portfolio_galleries(self) -> Dict[str, List[Dict]]:
        """Get all galleries from Public_Portfolio folder"""
        galleries = {}
        
        # Get Public_Portfolio folder ID
        portfolio_folder_id = self.get_folder_id('Public_Portfolio')
        if not portfolio_folder_id:
            return galleries
        
        try:
            # Get all subfolders in Public_Portfolio (excluding 'public' folder)
            results = self.service.files().list(
                q=f"'{portfolio_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and name!='public' and trashed=false",
                spaces='drive',
                fields='files(id, name)',
                orderBy='name'
            ).execute()
            
            subfolders = results.get('files', [])
            
            for subfolder in subfolders:
                gallery_name = subfolder['name']
                gallery_files = self.get_files_in_folder_by_id(subfolder['id'])
                if gallery_files:
                    galleries[gallery_name] = gallery_files
            
            return galleries
        except HttpError as error:
            print(f'An error occurred: {error}')
            return galleries
    
    def get_files_in_folder_by_id(self, folder_id: str) -> List[Dict]:
        """Get all files in a folder by ID"""
        try:
            results = self.service.files().list(
                q=f"'{folder_id}' in parents and trashed=false",
                spaces='drive',
                fields='files(id, name, mimeType, webViewLink, thumbnailLink)',
                orderBy='name'
            ).execute()
            
            files = results.get('files', [])
            # Filter for image files
            image_files = []
            for file in files:
                if file['mimeType'].startswith('image/'):
                    # Use the original thumbnailLink which works
                    image_url = file.get('thumbnailLink', '')
                    if not image_url:
                        # Fallback to direct download URL
                        image_url = f"https://drive.google.com/uc?export=view&id={file['id']}"
                    
                    image_files.append({
                        'id': file['id'],
                        'name': file['name'],
                        'mime_type': file['mimeType'],
                        'web_view_link': file.get('webViewLink', ''),
                        'thumbnail_link': file.get('thumbnailLink', ''),
                        'download_url': image_url
                    })
            
            return image_files
        except HttpError as error:
            print(f'An error occurred: {error}')
            return []
    
    def get_private_album_files(self, folder_name: str) -> List[Dict]:
        """Get all files from a private album folder"""
        return self.get_files_in_folder(folder_name, 'Private_Albums') 
