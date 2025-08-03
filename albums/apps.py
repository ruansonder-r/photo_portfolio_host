from django.apps import AppConfig


class AlbumsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'albums'
    
    def ready(self):
        """Run when Django starts"""
        import os
        from django.conf import settings
        
        # Only run sync in production or when explicitly requested
        if not settings.DEBUG or os.environ.get('SYNC_GOOGLE_DRIVE', '').lower() == 'true':
            try:
                from django.core.management import call_command
                call_command('sync_google_drive')
            except Exception as e:
                print(f"Warning: Google Drive sync failed on startup: {e}")
