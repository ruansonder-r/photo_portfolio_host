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
from albums.models import Image


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
        """Get images from the 'public' folder for carousel display - use local images"""
        # Get local images from database
        local_images = Image.objects.filter(folder_name='public', parent_folder_name='Public_Portfolio')
        
        image_files = []
        for image in local_images:
            if image.local_url and os.path.exists(image.local_file_path):
                image_files.append({
                    'id': image.google_drive_id,
                    'name': image.name,
                    'mime_type': image.mime_type,
                    'download_url': image.local_url,
                    'size': image.size,
                    'dimensions': image.width
                })
        
        return image_files
    
    def get_files_in_folder(self, folder_name: str, parent_folder_name: str = None) -> List[Dict]:
        """Get all files in a folder - use local images if available"""
        # Check if images exist locally
        local_images = Image.objects.filter(folder_name=folder_name, parent_folder_name=parent_folder_name)
        
        if local_images.exists():
            # Use local images
            image_files = []
            for image in local_images:
                if image.local_url and os.path.exists(image.local_file_path):
                    image_files.append({
                        'id': image.google_drive_id,
                        'name': image.name,
                        'mime_type': image.mime_type,
                        'download_url': image.local_url
                    })
            return image_files
        else:
            # Download images on first access (for private albums)
            return self._download_folder_images(folder_name, parent_folder_name)
    
    def _download_folder_images(self, folder_name: str, parent_folder_name: str = None) -> List[Dict]:
        """Download images from a folder and store them locally"""
        if not self.service:
            self.authenticate()
        
        folder_id = self.get_folder_id(folder_name, parent_folder_name)
        if not folder_id:
            return []
        
        try:
            # Create media directory
            media_dir = os.path.join(settings.MEDIA_ROOT, 'images')
            os.makedirs(media_dir, exist_ok=True)
            
            results = self.service.files().list(
                q=f"'{folder_id}' in parents and trashed=false",
                spaces='drive',
                fields='files(id, name, mimeType, size, imageMediaMetadata)',
                orderBy='name'
            ).execute()
            
            files = results.get('files', [])
            image_files = []
            
            for file in files:
                if file['mimeType'].startswith('image/'):
                    # Download and store the image
                    success = self._download_and_store_image(file, media_dir, folder_name, parent_folder_name)
                    if success:
                        # Get the stored image
                        stored_image = Image.objects.get(google_drive_id=file['id'])
                        image_files.append({
                            'id': stored_image.google_drive_id,
                            'name': stored_image.name,
                            'mime_type': stored_image.mime_type,
                            'download_url': stored_image.local_url
                        })
            
            return image_files
            
        except HttpError as error:
            print(f'An error occurred: {error}')
            return []
    
    def _download_and_store_image(self, file_data, media_dir, folder_name, parent_folder_name=None):
        """Download a single image and store it locally"""
        try:
            # Generate local file path
            file_extension = os.path.splitext(file_data['name'])[1]
            local_filename = f"{file_data['id']}{file_extension}"
            local_path = os.path.join(media_dir, local_filename)
            
            # Download file from Google Drive
            request = self.service.files().get_media(fileId=file_data['id'])
            with open(local_path, 'wb') as f:
                f.write(request.execute())
            
            # Get image dimensions
            width = 0
            height = 0
            if file_data.get('imageMediaMetadata'):
                metadata = file_data['imageMediaMetadata']
                width = metadata.get('width', 0)
                height = metadata.get('height', 0)
            
            # Create or update Image record
            image, created = Image.objects.update_or_create(
                google_drive_id=file_data['id'],
                defaults={
                    'name': file_data['name'],
                    'mime_type': file_data['mimeType'],
                    'local_file_path': local_path,
                    'folder_name': folder_name,
                    'parent_folder_name': parent_folder_name,
                    'size': int(file_data.get('size', 0)),
                    'width': width,
                    'height': height,
                }
            )
            
            print(f'Downloaded image: {file_data["name"]}')
            return True
            
        except Exception as e:
            print(f'Error downloading {file_data["name"]}: {e}')
            return False
    
    def get_public_portfolio_galleries(self) -> Dict[str, List[Dict]]:
        """Get all galleries from Public_Portfolio folder - use local images"""
        galleries = {}
        
        # Get all unique gallery names from local database
        gallery_names = Image.objects.filter(
            parent_folder_name='Public_Portfolio'
        ).exclude(
            folder_name='public'
        ).values_list('folder_name', flat=True).distinct()
        
        for gallery_name in gallery_names:
            local_images = Image.objects.filter(folder_name=gallery_name, parent_folder_name='Public_Portfolio')
            gallery_files = []
            
            for image in local_images:
                if image.local_url and os.path.exists(image.local_file_path):
                    gallery_files.append({
                        'id': image.google_drive_id,
                        'name': image.name,
                        'mime_type': image.mime_type,
                        'download_url': image.local_url
                    })
            
            if gallery_files:
                galleries[gallery_name] = gallery_files
        
        return galleries
    
    def get_files_in_folder_by_id(self, folder_id: str) -> List[Dict]:
        """Get all files in a folder by ID - use local images if available"""
        # This method is used for public galleries, so we'll use the folder-based approach
        # We need to get the folder name first
        if not self.service:
            self.authenticate()
        
        try:
            folder_info = self.service.files().get(fileId=folder_id).execute()
            folder_name = folder_info['name']
            
            # Use the folder-based method
            return self.get_files_in_folder(folder_name, 'Public_Portfolio')
            
        except HttpError as error:
            print(f'An error occurred: {error}')
            return []
    
    def get_private_album_files(self, folder_name: str) -> List[Dict]:
        """Get all files from a private album folder"""
        return self.get_files_in_folder(folder_name, 'Private_Albums') 
