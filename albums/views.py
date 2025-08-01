from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.cache import cache_page
from django.contrib.auth.decorators import login_required
from .models import ClientAlbum
from core.services import GoogleDriveService
import zipfile
import io


@cache_page(60 * 15)  # Cache for 15 minutes
def album_detail(request, album_id):
    """Display a private client album"""
    album = get_object_or_404(ClientAlbum, id=album_id)
    
    try:
        drive_service = GoogleDriveService()
        images = drive_service.get_private_album_files(album.folder_name)
        
        context = {
            'album': album,
            'images': images,
        }
        return render(request, 'albums/album_detail.html', context)
    except Exception as e:
        context = {
            'album': album,
            'images': [],
            'error': str(e) if request.user.is_staff else None,
        }
        return render(request, 'albums/album_detail.html', context)


def download_image(request, album_id, image_id):
    """Download a single image from an album"""
    album = get_object_or_404(ClientAlbum, id=album_id)
    
    try:
        drive_service = GoogleDriveService()
        images = drive_service.get_private_album_files(album.folder_name)
        
        # Find the specific image
        image = next((img for img in images if img['id'] == image_id), None)
        
        if image:
            # Redirect to Google Drive download URL
            return HttpResponse(
                f'<script>window.location.href="{image["download_url"]}";</script>',
                content_type='text/html'
            )
        else:
            return HttpResponse("Image not found", status=404)
    except Exception as e:
        return HttpResponse(f"Error downloading image: {str(e)}", status=500)


def download_album_zip(request, album_id):
    """Download entire album as ZIP file"""
    album = get_object_or_404(ClientAlbum, id=album_id)
    
    try:
        drive_service = GoogleDriveService()
        images = drive_service.get_private_album_files(album.folder_name)
        
        if not images:
            return HttpResponse("No images found in album", status=404)
        
        # Create ZIP file in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for image in images:
                # Add image to ZIP with original filename
                zip_file.writestr(image['name'], '')  # Placeholder - in real implementation, you'd download the actual file
        
        # Prepare response
        response = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="{album.title}.zip"'
        return response
        
    except Exception as e:
        return HttpResponse(f"Error creating ZIP: {str(e)}", status=500)


@login_required
def admin_album_list(request):
    """Admin view to list all albums"""
    albums = ClientAlbum.objects.all()
    return render(request, 'albums/admin_list.html', {'albums': albums})
