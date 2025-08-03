# Local Image Storage System

## Overview

This system downloads and stores Google Drive images locally to improve performance and reliability. Images are stored in the database with metadata and served from the local filesystem.

## Features

- **Public Images**: Downloaded on deployment via management command
- **Private Album Images**: Downloaded on first access (lazy loading)
- **Automatic Cleanup**: Removes local images when Google Drive folders are deleted
- **Startup Sync**: Checks for deleted folders on app startup

## Database Models

### Image Model
- `google_drive_id`: Unique Google Drive file ID
- `name`: Original filename
- `mime_type`: File MIME type
- `local_file_path`: Path to local file
- `folder_name`: Google Drive folder name
- `parent_folder_name`: Parent folder (for nested folders)
- `size`: File size in bytes
- `width/height`: Image dimensions
- `downloaded_at`: When image was downloaded
- `last_accessed`: Last access timestamp

## Management Commands

### sync_google_drive
```bash
# Download public images on deployment
python manage.py sync_google_drive --download-public

# Force re-download existing images
python manage.py sync_google_drive --download-public --force

# Just check for deleted folders
python manage.py sync_google_drive
```

## Deployment

### Manual Deployment
```bash
# Run the deployment script
./deploy.sh
```

### Manual Steps
1. Install dependencies: `pip install -r requirements.txt`
2. Run migrations: `python manage.py migrate`
3. Download public images: `python manage.py sync_google_drive --download-public`
4. Collect static files: `python manage.py collectstatic --noinput`

## File Structure

```
media/
└── images/
    ├── 1ZbiTc3i_REJjOBkK5y5IjYrlLeXaStGN.jpg
    ├── 1Zajj7XUk9YMabkV6zmFDoWzk69eN4hRA.jpg
    └── ...
```

## URL Structure

Local images are served at: `/media/images/{google_drive_id}.{extension}`

## Configuration

### Environment Variables
- `GOOGLE_DRIVE_CREDENTIALS_FILE`: Path to service account credentials
- `SYNC_GOOGLE_DRIVE`: Set to 'true' to enable startup sync

### Settings
- `MEDIA_URL = '/media/'`
- `MEDIA_ROOT = BASE_DIR / 'media'`

## How It Works

1. **Public Images**: Downloaded during deployment via `sync_google_drive --download-public`
2. **Private Albums**: Images downloaded on first access when `get_files_in_folder()` is called
3. **Startup Check**: App checks for deleted folders on startup and removes local images
4. **Local Serving**: Images served from local filesystem instead of Google Drive URLs

## Benefits

- **Faster Loading**: No Google Drive API calls for image display
- **Better Reliability**: No dependency on Google Drive availability
- **Higher Quality**: Full resolution images stored locally
- **Reduced Bandwidth**: Images served from local server
- **Automatic Cleanup**: Removes orphaned images when folders are deleted

## Monitoring

### Check Downloaded Images
```python
from albums.models import Image
print(f"Total images: {Image.objects.count()}")
print(f"Public images: {Image.objects.filter(folder_name='public').count()}")
```

### Check File System
```bash
ls -la media/images/
du -sh media/images/
```

## Troubleshooting

### Images Not Loading
1. Check if files exist: `ls -la media/images/`
2. Check database records: `python manage.py shell -c "from albums.models import Image; print(Image.objects.count())"`
3. Re-download: `python manage.py sync_google_drive --download-public --force`

### Missing Images
1. Check Google Drive folder structure
2. Verify service account permissions
3. Check logs for download errors

### Performance Issues
1. Monitor disk space usage
2. Consider image optimization
3. Check file permissions 
