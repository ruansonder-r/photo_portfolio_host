from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.cache import cache_page
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.urls import reverse
from django.conf import settings
from .models import ClientAlbum, Image
from core.services import GoogleDriveService
import zipfile
import io
import os


def is_admin_user(user):
    """Check if user is admin/staff"""
    return user.is_authenticated and user.is_staff


@cache_page(60 * 15)  # Cache for 15 minutes
def album_detail(request, album_id):
    """Display a private client album"""
    album = get_object_or_404(ClientAlbum, id=album_id)
    
    try:
        drive_service = GoogleDriveService()
        images = drive_service.get_private_album_files(album.folder_name)  # Use folder_name for Google Drive mapping
        
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
        # Try to get the image from local storage first
        image = Image.objects.filter(google_drive_id=image_id).first()
        
        if image and os.path.exists(image.local_file_path):
            # Serve local file
            with open(image.local_file_path, 'rb') as f:
                response = HttpResponse(f.read(), content_type=image.mime_type)
                response['Content-Disposition'] = f'attachment; filename="{image.name}"'
                return response
        else:
            # Fallback to Google Drive service
            drive_service = GoogleDriveService()
            images = drive_service.get_private_album_files(album.folder_name)  # Use folder_name for Google Drive mapping
            
            # Find the specific image
            image_data = next((img for img in images if img['id'] == image_id), None)
            
            if image_data:
                # Redirect to local URL if available, otherwise Google Drive
                return HttpResponse(
                    f'<script>window.location.href="{image_data["download_url"]}";</script>',
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
        images = drive_service.get_private_album_files(album.folder_name)  # Use folder_name for Google Drive mapping
        
        if not images:
            return HttpResponse("No images found in album", status=404)
        
        # Create ZIP file in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for image_data in images:
                # Try to get local file first
                image = Image.objects.filter(google_drive_id=image_data['id']).first()
                
                if image and os.path.exists(image.local_file_path):
                    # Add local file to ZIP
                    with open(image.local_file_path, 'rb') as f:
                        zip_file.writestr(image.name, f.read())
                else:
                    # Fallback: add placeholder (could implement Google Drive download here)
                    zip_file.writestr(image_data['name'], '')
        
        # Prepare response
        response = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="{album.name}.zip"'  # Use name for filename
        return response
        
    except Exception as e:
        return HttpResponse(f"Error creating ZIP: {str(e)}", status=500)


@login_required
@user_passes_test(is_admin_user)
def admin_album_list(request):
    """Admin view to list all albums with link generation"""
    albums = ClientAlbum.objects.all().order_by('-date')
    
    # Generate full URLs for each album
    for album in albums:
        album.full_url = request.build_absolute_uri(reverse('albums:album_detail', kwargs={'album_id': album.id}))
    
    context = {
        'albums': albums,
        'site_domain': request.get_host(),
    }
    return render(request, 'albums/admin_list.html', context)


@login_required
@user_passes_test(is_admin_user)
def generate_album_link(request, album_id):
    """Generate and display album link for sharing"""
    album = get_object_or_404(ClientAlbum, id=album_id)
    
    # Generate the full URL
    album_url = request.build_absolute_uri(reverse('albums:album_detail', kwargs={'album_id': album.id}))
    
    context = {
        'album': album,
        'album_url': album_url,
        'site_domain': request.get_host(),
    }
    return render(request, 'albums/generate_link.html', context)
