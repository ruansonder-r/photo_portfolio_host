from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.cache import cache_page
from core.services import GoogleDriveService
from urllib.parse import unquote


@cache_page(60 * 15)  # Cache for 15 minutes
def portfolio_home(request):
    """Display the main portfolio page with public galleries and carousel"""
    try:
        drive_service = GoogleDriveService()
        galleries = drive_service.get_public_portfolio_galleries()
        carousel_images = drive_service.get_public_carousel_images()
        
        context = {
            'galleries': galleries,
            'carousel_images': carousel_images,
        }
        return render(request, 'portfolio/home.html', context)
    except Exception as e:
        # Fallback to empty galleries if Google Drive is not available
        context = {
            'galleries': {},
            'carousel_images': [],
            'error': str(e) if request.user.is_staff else None,
        }
        return render(request, 'portfolio/home.html', context)


def portfolio_home_debug(request):
    """Debug version without caching"""
    try:
        drive_service = GoogleDriveService()
        galleries = drive_service.get_public_portfolio_galleries()
        carousel_images = drive_service.get_public_carousel_images()
        
        context = {
            'galleries': galleries,
            'carousel_images': carousel_images,
            'debug': True,
        }
        return render(request, 'portfolio/home.html', context)
    except Exception as e:
        context = {
            'galleries': {},
            'carousel_images': [],
            'error': str(e),
            'debug': True,
        }
        return render(request, 'portfolio/home.html', context)


def contact(request):
    """Contact page with mailto link"""
    return render(request, 'portfolio/contact.html')


def gallery_detail(request, gallery_name):
    """Display a specific gallery"""
    try:
        # Decode the gallery name from URL encoding
        decoded_gallery_name = unquote(gallery_name)
        
        drive_service = GoogleDriveService()
        galleries = drive_service.get_public_portfolio_galleries()
        
        gallery_images = galleries.get(decoded_gallery_name, [])
        
        context = {
            'gallery_name': decoded_gallery_name,
            'images': gallery_images,
        }
        return render(request, 'portfolio/gallery_detail.html', context)
    except Exception as e:
        context = {
            'gallery_name': gallery_name,
            'images': [],
            'error': str(e) if request.user.is_staff else None,
        }
        return render(request, 'portfolio/gallery_detail.html', context)
