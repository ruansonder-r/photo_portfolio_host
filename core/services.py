import os
import json
from typing import List, Dict, Optional
from datetime import timedelta
from urllib.parse import quote
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from django.conf import settings
from albums.models import Image
from django.utils.functional import cached_property

try:
    # Optional: only required when using GCS for URLs
    from google.cloud import storage  # type: ignore
except Exception:
    storage = None


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
            print("Starting Google Drive authentication...")
            
            # Check if credentials file exists
            if not self.credentials_file or not os.path.exists(self.credentials_file):
                print(f"ERROR: Google Drive credentials file not found: {self.credentials_file}")
                print(f"Available environment variables: {[k for k in os.environ.keys() if 'GOOGLE' in k]}")
                raise FileNotFoundError(
                    f"Google Drive credentials file not found: {self.credentials_file}"
                )
            
            print(f"Using credentials file: {self.credentials_file}")
            
            # Use service account credentials
            creds = service_account.Credentials.from_service_account_file(
                self.credentials_file, scopes=self.SCOPES
            )
            
            print("Building Google Drive service...")
            self.service = build('drive', 'v3', credentials=creds)
            print("Google Drive authentication successful")
            return self.service
            
        except Exception as e:
            print(f"ERROR in Google Drive authentication: {e}")
            import traceback
            traceback.print_exc()
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
    
    def _is_production(self):
        """Check if we're in production (Vercel) environment"""
        # Check for Vercel-specific environment variables
        vercel_env = os.environ.get('VERCEL', '')
        vercel_url = os.environ.get('VERCEL_URL', '')
        vercel_environment = os.environ.get('VERCEL_ENV', '')
        
        # Also check if DEBUG is explicitly False
        debug_setting = getattr(settings, 'DEBUG', True)
        
        is_prod = (
            vercel_env == '1' or 
            vercel_url or 
            vercel_environment in ['production', 'preview'] or
            not debug_setting
        )
        
        print(f"Production detection: VERCEL={vercel_env}, VERCEL_URL={vercel_url}, VERCEL_ENV={vercel_environment}, DEBUG={debug_setting}, Is Production={is_prod}")
        
        return is_prod

    # -------- GCS helpers --------
    @cached_property
    def _gcs_enabled_public(self) -> bool:
        return bool(getattr(settings, 'GCS_PUBLIC_BASE_URL', ''))

    @cached_property
    def _gcs_enabled_private(self) -> bool:
        return bool(getattr(settings, 'GCS_PRIVATE_BUCKET', '') and getattr(settings, 'GCP_SERVICE_ACCOUNT_JSON', ''))

    @cached_property
    def _gcs_client(self):
        if not self._gcs_enabled_private:
            return None
        if storage is None:
            return None
        try:
            return storage.Client.from_service_account_info(json.loads(settings.GCP_SERVICE_ACCOUNT_JSON))
        except Exception as e:
            print(f"Failed to init GCS client: {e}")
            return None

    def _build_gcs_public_url(self, folder_name: str, file_name: str) -> Optional[str]:
        if not self._gcs_enabled_public:
            return None
        base = settings.GCS_PUBLIC_BASE_URL.rstrip('/')
        prefix = getattr(settings, 'GCS_PUBLIC_PREFIX', 'Public_Portfolio').strip('/')
        # URL-encode path segments to be safe
        path = f"{quote(prefix)}/{quote(folder_name)}/{quote(file_name)}"
        return f"{base}/{path}"

    def _build_gcs_private_signed_url(self, folder_name: str, file_name: str) -> Optional[str]:
        if not self._gcs_client:
            return None
        try:
            bucket_name = settings.GCS_PRIVATE_BUCKET
            prefix = getattr(settings, 'GCS_PRIVATE_PREFIX', 'Private_Albums').strip('/')
            blob_path = f"{prefix}/{folder_name}/{file_name}"
            bucket = self._gcs_client.bucket(bucket_name)
            blob = bucket.blob(blob_path)
            url = blob.generate_signed_url(
                version='v4',
                expiration=timedelta(hours=int(getattr(settings, 'GCS_SIGNED_URL_HOURS', 6))),
                method='GET',
            )
            return url
        except Exception as e:
            print(f"Failed to sign GCS URL: {e}")
            return None
    
    def _get_high_quality_image_url(self, file_id: str) -> str:
        """Get high-quality image URL from Google Drive"""
        try:
            # Try to get the original image URL
            original_url = f"https://drive.google.com/uc?id={file_id}&export=download"
            
            # Test if the URL is accessible
            import requests
            response = requests.head(original_url, timeout=5)
            if response.status_code == 200:
                return original_url
            
            # Fallback to webContentLink if available
            if not self.service:
                self.authenticate()
            
            file_info = self.service.files().get(fileId=file_id, fields='webContentLink').execute()
            if file_info.get('webContentLink'):
                return file_info['webContentLink']
            
            # Final fallback to thumbnailLink but with larger size
            file_info = self.service.files().get(fileId=file_id, fields='thumbnailLink').execute()
            if file_info.get('thumbnailLink'):
                # Replace s220 with s1200 for higher quality
                return file_info['thumbnailLink'].replace('=s220', '=s1200')
            
            return original_url
            
        except Exception as e:
            print(f"Error getting high-quality URL for {file_id}: {e}")
            return f"https://drive.google.com/uc?id={file_id}&export=download"
    
    def get_public_carousel_images(self) -> List[Dict]:
        """Get images from the 'public' folder for carousel display"""
        if self._is_production():
            # In production, prefer GCS URLs if configured; fallback to Drive
            return self._get_public_carousel_images_from_drive()
        else:
            # In development, use local images
            return self._get_public_carousel_images_local()
    
    def _get_public_carousel_images_local(self) -> List[Dict]:
        """Get local images from database"""
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
    
    def _get_public_carousel_images_from_drive(self) -> List[Dict]:
        """Get images via Drive listing; prefer GCS URLs when available"""
        try:
            if not self.service:
                print("Authenticating with Google Drive...")
                self.authenticate()
            
            # Get Public_Portfolio folder ID
            portfolio_folder_id = self.get_folder_id('Public_Portfolio')
            if not portfolio_folder_id:
                print("ERROR: Public_Portfolio folder not found")
                return []
            
            # Get 'public' folder ID
            public_folder_id = self.get_folder_id('public', 'Public_Portfolio')
            if not public_folder_id:
                print("ERROR: public folder not found")
                return []
            
            print(f"Found folders: Public_Portfolio={portfolio_folder_id}, public={public_folder_id}")
            
            results = self.service.files().list(
                q=f"'{public_folder_id}' in parents and trashed=false",
                spaces='drive',
                fields='files(id, name, mimeType, webViewLink, webContentLink, thumbnailLink, size, imageMediaMetadata)',
                orderBy='name'
            ).execute()
            
            files = results.get('files', [])
            print(f"Found {len(files)} files in public folder")
            
            image_files = []
            for file in files:
                if file['mimeType'].startswith('image/'):
                    # Prefer GCS public URL if configured; else Drive HQ URL
                    gcs_url = self._build_gcs_public_url('public', file['name'])
                    image_url = gcs_url or self._get_high_quality_image_url(file['id'])
                    
                    print(f"Image {file['name']}: {image_url}")
                    
                    image_files.append({
                        'id': file['id'],
                        'name': file['name'],
                        'mime_type': file['mimeType'],
                        'download_url': image_url,
                        'size': file.get('size', ''),
                        'dimensions': file.get('imageMediaMetadata', {}).get('width', 0) if file.get('imageMediaMetadata') else 0
                    })
            
            print(f"Returning {len(image_files)} image files")
            return image_files
        except Exception as e:
            print(f'ERROR in _get_public_carousel_images_from_drive: {e}')
            import traceback
            traceback.print_exc()
            return []
    
    def get_files_in_folder(self, folder_name: str, parent_folder_name: str = None) -> List[Dict]:
        """Get all files in a folder"""
        if self._is_production():
            # In production, use Google Drive URLs directly
            return self._get_files_in_folder_from_drive(folder_name, parent_folder_name)
        else:
            # In development, use local images if available
            return self._get_files_in_folder_local(folder_name, parent_folder_name)
    
    def _get_files_in_folder_local(self, folder_name: str, parent_folder_name: str = None) -> List[Dict]:
        """Get local images from database"""
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
    
    def _get_files_in_folder_from_drive(self, folder_name: str, parent_folder_name: str = None) -> List[Dict]:
        """Get images via Drive listing; prefer GCS URLs"""
        if not self.service:
            self.authenticate()
        
        folder_id = self.get_folder_id(folder_name, parent_folder_name)
        if not folder_id:
            return []
        
        try:
            results = self.service.files().list(
                q=f"'{folder_id}' in parents and trashed=false",
                spaces='drive',
                fields='files(id, name, mimeType, webViewLink, webContentLink, thumbnailLink)',
                orderBy='name'
            ).execute()
            
            files = results.get('files', [])
            image_files = []
            for file in files:
                if file['mimeType'].startswith('image/'):
                    # Public portfolio uses public bucket; private albums use signed URLs
                    if parent_folder_name == 'Public_Portfolio':
                        gcs_url = self._build_gcs_public_url(folder_name, file['name'])
                        image_url = gcs_url or self._get_high_quality_image_url(file['id'])
                    else:
                        signed = self._build_gcs_private_signed_url(folder_name, file['name'])
                        image_url = signed or self._get_high_quality_image_url(file['id'])
                    
                    image_files.append({
                        'id': file['id'],
                        'name': file['name'],
                        'mime_type': file['mimeType'],
                        'download_url': image_url
                    })
            
            return image_files
        except HttpError as error:
            print(f'An error occurred: {error}')
            return []
    
    def _download_folder_images(self, folder_name: str, parent_folder_name: str = None) -> List[Dict]:
        """Download images from a folder and store them locally (development only)"""
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
        """Download a single image and store it locally (development only)"""
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
        """Get all galleries from Public_Portfolio folder"""
        if self._is_production():
            # In production, get galleries directly from Google Drive
            return self._get_public_portfolio_galleries_from_drive()
        else:
            # In development, use local images
            return self._get_public_portfolio_galleries_local()
    
    def _get_public_portfolio_galleries_local(self) -> Dict[str, List[Dict]]:
        """Get local galleries from database"""
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
    
    def _get_public_portfolio_galleries_from_drive(self) -> Dict[str, List[Dict]]:
        """Get galleries directly from Google Drive"""
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
                gallery_files = self._get_files_in_folder_from_drive(gallery_name, 'Public_Portfolio')
                if gallery_files:
                    galleries[gallery_name] = gallery_files
            
            return galleries
        except HttpError as error:
            print(f'An error occurred: {error}')
            return galleries
    
    def get_files_in_folder_by_id(self, folder_id: str) -> List[Dict]:
        """Get all files in a folder by ID"""
        if self._is_production():
            # In production, get files directly from Google Drive
            return self._get_files_in_folder_by_id_from_drive(folder_id)
        else:
            # In development, use folder-based approach
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
    
    def _get_files_in_folder_by_id_from_drive(self, folder_id: str) -> List[Dict]:
        """Get files directly from Google Drive by folder ID"""
        try:
            results = self.service.files().list(
                q=f"'{folder_id}' in parents and trashed=false",
                spaces='drive',
                fields='files(id, name, mimeType, webViewLink, webContentLink, thumbnailLink)',
                orderBy='name'
            ).execute()
            
            files = results.get('files', [])
            image_files = []
            for file in files:
                if file['mimeType'].startswith('image/'):
                    # Use high-quality image URL instead of thumbnail
                    image_url = self._get_high_quality_image_url(file['id'])
                    
                    image_files.append({
                        'id': file['id'],
                        'name': file['name'],
                        'mime_type': file['mimeType'],
                        'download_url': image_url
                    })
            
            return image_files
        except HttpError as error:
            print(f'An error occurred: {error}')
            return []
    
    def get_private_album_files(self, folder_name: str) -> List[Dict]:
        """Get all files from a private album folder"""
        return self.get_files_in_folder(folder_name, 'Private_Albums') 
