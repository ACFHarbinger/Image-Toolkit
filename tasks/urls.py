from django.urls import path
from .views import (
    ConvertView, MergeView, DeleteView, 
    DuplicateScanView, SearchView, WallpaperView
)

# Define the app name for URL reversing
app_name = 'core_tasks'

urlpatterns = [
    # Image Processing
    path('convert/', ConvertView.as_view(), name='convert'),
    path('merge/', MergeView.as_view(), name='merge'),
    path('delete/', DeleteView.as_view(), name='delete'),
    
    # Scanning and Database
    path('scan-duplicates/', DuplicateScanView.as_view(), name='scan_duplicates'),
    path('search/', SearchView.as_view(), name='search'),
    
    # Utility
    path('set-wallpaper/', WallpaperView.as_view(), name='set_wallpaper'),
]