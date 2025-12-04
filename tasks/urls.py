from django.urls import path
from .views import (
    ConvertView, MergeView, DeleteView, 
    DuplicateScanView, SearchView,
    TrainingView, FrameExtractionView,
    GifExtractionView, VideoExtractionView,
    CloudSyncView, ImageCrawlView,
    ReverseSearchView, WebRequestView,
    DatabaseConnectView, DatabaseAddGroupView,
    DatabaseAddSubgroupView, DatabaseAddTagView,
    DatabaseAutoPopulateView, DatabaseResetView
)

urlpatterns = [
    # Core Tasks
    path('convert/', ConvertView.as_view(), name='api_convert'),
    path('merge/', MergeView.as_view(), name='api_merge'),
    path('delete/', DeleteView.as_view(), name='api_delete'),
    path('scan-duplicates/', DuplicateScanView.as_view(), name='api_scan'),
    path('search/', SearchView.as_view(), name='api_search'),
    
    # AI & Video Tasks
    path('train-gan/', TrainingView.as_view(), name='api_train_gan'),
    path('extract-frames/', FrameExtractionView.as_view(), name='api_extract_frames'),
    path('extract-gif/', GifExtractionView.as_view(), name='api_extract_gif'),
    path('extract-video/', VideoExtractionView.as_view(), name='api_extract_video'),

    # Web Tasks
    path('cloud-sync/', CloudSyncView.as_view(), name='api_cloud_sync'),
    path('crawl-images/', ImageCrawlView.as_view(), name='api_crawl_images'),
    path('reverse-search/', ReverseSearchView.as_view(), name='api_reverse_search'),
    path('web-request/', WebRequestView.as_view(), name='api_web_request'),

    # Database Management (New)
    path('db/connect/', DatabaseConnectView.as_view(), name='api_db_connect'),
    path('db/add-group/', DatabaseAddGroupView.as_view(), name='api_db_add_group'),
    path('db/add-subgroup/', DatabaseAddSubgroupView.as_view(), name='api_db_add_subgroup'),
    path('db/add-tag/', DatabaseAddTagView.as_view(), name='api_db_add_tag'),
    path('db/auto-populate/', DatabaseAutoPopulateView.as_view(), name='api_db_auto_populate'),
    path('db/reset/', DatabaseResetView.as_view(), name='api_db_reset'),
]