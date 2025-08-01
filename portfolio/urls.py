from django.urls import path
from . import views

app_name = 'portfolio'

urlpatterns = [
    path('', views.portfolio_home, name='home'),
    path('debug/', views.portfolio_home_debug, name='home_debug'),
    path('contact/', views.contact, name='contact'),
    path('gallery/<path:gallery_name>/', views.gallery_detail, name='gallery_detail'),
] 
