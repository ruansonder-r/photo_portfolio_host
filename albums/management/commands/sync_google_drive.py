import os
import requests
from django.core.management.base import BaseCommand
from django.conf import settings
from albums.models import Image
from core.services import GoogleDriveService


class Command(BaseCommand):
    help = 'Sync Google Drive folders and download images'

    def add_arguments(self, parser):
        parser.add_argument(
            '--download-public',
            action='store_true',
            help='Download public folder images on deployment',
        )
        parser.add_argument(
            '--download-galleries',
            action='store_true',
            help='Download public gallery images on deployment',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force re-download of existing images',
        )

    def handle(self, *args, **options):
        self.stdout.write('Starting Google Drive sync...')
        
        # Create media directory if it doesn't exist
        media_dir = os.path.join(settings.MEDIA_ROOT, 'images')
        os.makedirs(media_dir, exist_ok=True)
        
        drive_service = GoogleDriveService()
        
        # Sync public folder on deployment
        if options['download_public']:
            self.stdout.write('Downloading public folder images...')
            self._download_public_images(drive_service, media_dir, options['force'])
        
        # Sync public galleries on deployment
        if options['download_galleries']:
            self.stdout.write('Downloading public gallery images...')
            self._download_public_galleries(drive_service, media_dir, options['force'])
        
        # Check for deleted folders and clean up
        self.stdout.write('Checking for deleted folders...')
        self._cleanup_deleted_folders(drive_service)
        
        self.stdout.write(self.style.SUCCESS('Google Drive sync completed!'))

    def _download_public_images(self, drive_service, media_dir, force=False):
        """Download images from the public folder"""
        try:
            # Get Public_Portfolio folder ID
            portfolio_folder_id = drive_service.get_folder_id('Public_Portfolio')
            if not portfolio_folder_id:
                self.stdout.write(self.style.WARNING('Public_Portfolio folder not found'))
                return
            
            # Get 'public' folder ID
            public_folder_id = drive_service.get_folder_id('public', 'Public_Portfolio')
            if not public_folder_id:
                self.stdout.write(self.style.WARNING('public folder not found'))
                return
            
            # Get files from public folder
            results = drive_service.service.files().list(
                q=f"'{public_folder_id}' in parents and trashed=false",
                spaces='drive',
                fields='files(id, name, mimeType, size, imageMediaMetadata)',
                orderBy='name'
            ).execute()
            
            files = results.get('files', [])
            downloaded_count = 0
            
            for file in files:
                if file['mimeType'].startswith('image/'):
                    # Check if image already exists
                    existing_image = Image.objects.filter(google_drive_id=file['id']).first()
                    
                    if existing_image and not force:
                        self.stdout.write(f'Image {file["name"]} already exists, skipping...')
                        continue
                    
                    # Download the image
                    success = self._download_image(
                        drive_service, file, media_dir, 'public', 'Public_Portfolio'
                    )
                    if success:
                        downloaded_count += 1
            
            self.stdout.write(f'Downloaded {downloaded_count} images from public folder')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error downloading public images: {e}'))

    def _download_public_galleries(self, drive_service, media_dir, force=False):
        """Download images from all public galleries"""
        try:
            # Get Public_Portfolio folder ID
            portfolio_folder_id = drive_service.get_folder_id('Public_Portfolio')
            if not portfolio_folder_id:
                self.stdout.write(self.style.WARNING('Public_Portfolio folder not found'))
                return
            
            # Get all subfolders in Public_Portfolio (excluding 'public' folder)
            results = drive_service.service.files().list(
                q=f"'{portfolio_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and name!='public' and trashed=false",
                spaces='drive',
                fields='files(id, name)',
                orderBy='name'
            ).execute()
            
            subfolders = results.get('files', [])
            total_downloaded = 0
            
            for subfolder in subfolders:
                gallery_name = subfolder['name']
                self.stdout.write(f'Processing gallery: {gallery_name}')
                
                # Get files from this gallery
                gallery_results = drive_service.service.files().list(
                    q=f"'{subfolder['id']}' in parents and trashed=false",
                    spaces='drive',
                    fields='files(id, name, mimeType, size, imageMediaMetadata)',
                    orderBy='name'
                ).execute()
                
                gallery_files = gallery_results.get('files', [])
                gallery_downloaded = 0
                
                for file in gallery_files:
                    if file['mimeType'].startswith('image/'):
                        # Check if image already exists
                        existing_image = Image.objects.filter(google_drive_id=file['id']).first()
                        
                        if existing_image and not force:
                            self.stdout.write(f'  Image {file["name"]} already exists, skipping...')
                            continue
                        
                        # Download the image
                        success = self._download_image(
                            drive_service, file, media_dir, gallery_name, 'Public_Portfolio'
                        )
                        if success:
                            gallery_downloaded += 1
                
                self.stdout.write(f'  Downloaded {gallery_downloaded} images from {gallery_name}')
                total_downloaded += gallery_downloaded
            
            self.stdout.write(f'Total downloaded: {total_downloaded} images from {len(subfolders)} galleries')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error downloading public galleries: {e}'))

    def _download_image(self, drive_service, file_data, media_dir, folder_name, parent_folder_name=None):
        """Download a single image from Google Drive"""
        try:
            # Generate local file path
            file_extension = os.path.splitext(file_data['name'])[1]
            local_filename = f"{file_data['id']}{file_extension}"
            local_path = os.path.join(media_dir, local_filename)
            
            # Download file from Google Drive
            request = drive_service.service.files().get_media(fileId=file_data['id'])
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
            
            action = 'Downloaded' if created else 'Updated'
            self.stdout.write(f'{action} image: {file_data["name"]}')
            return True
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error downloading {file_data["name"]}: {e}'))
            return False

    def _cleanup_deleted_folders(self, drive_service):
        """Remove local images for folders that no longer exist on Google Drive"""
        try:
            # Get all unique folder names from local database
            local_folders = Image.objects.values_list('folder_name', flat=True).distinct()
            
            for folder_name in local_folders:
                # Check if folder still exists on Google Drive
                folder_id = drive_service.get_folder_id(folder_name)
                if not folder_id:
                    self.stdout.write(f'Folder {folder_name} no longer exists, cleaning up...')
                    
                    # Delete local images for this folder
                    images_to_delete = Image.objects.filter(folder_name=folder_name)
                    deleted_count = 0
                    
                    for image in images_to_delete:
                        if image.delete_local_file():
                            deleted_count += 1
                        image.delete()
                    
                    self.stdout.write(f'Deleted {deleted_count} images for folder {folder_name}')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error cleaning up deleted folders: {e}')) 
