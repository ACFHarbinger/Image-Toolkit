from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import (
    FrameExtractionSerializer, DbAutoPopulateSerializer,
    DatabaseConfigSerializer, DbAddGroupSerializer,
    DbAddSubgroupSerializer, DbAddTagSerializer,
    SearchSerializer, TrainingSerializer, 
    ConversionSerializer, MergeSerializer, 
    CloudSyncSerializer, ImageCrawlSerializer,
    DeletionSerializer, DuplicateScanSerializer,
    ReverseSearchSerializer, WebRequestSerializer,
    GifExtractionSerializer, VideoExtractionSerializer,
)
from .tasks import (
    task_convert_images, task_merge_images, 
    task_delete_files, task_scan_duplicates,
    task_train_gan, task_extract_frames,
    task_create_gif, task_extract_video_clip,
    task_cloud_sync, task_crawl_images,
    task_reverse_search, task_web_request,
    task_db_test_connection, task_db_add_group,
    task_db_add_subgroup, task_db_add_tag,
    task_db_auto_populate, task_db_reset
)


class CoreTaskView(APIView):
    """
    Generic view helper to validate serializer and launch task.
    """
    def launch_task(self, serializer_cls, task_func, data):
        serializer = serializer_cls(data=data)
        if serializer.is_valid():
            # .delay() sends the task to Celery
            task = task_func.delay(serializer.validated_data)
            return Response({
                "task_id": task.id,
                "status": "processing"
            }, status=status.HTTP_202_ACCEPTED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ConvertView(CoreTaskView):
    def post(self, request):
        return self.launch_task(ConversionSerializer, task_convert_images, request.data)

class MergeView(CoreTaskView):
    def post(self, request):
        return self.launch_task(MergeSerializer, task_merge_images, request.data)

class DeleteView(CoreTaskView):
    def post(self, request):
        return self.launch_task(DeletionSerializer, task_delete_files, request.data)

class DuplicateScanView(APIView):
    def post(self, request):
        serializer = DuplicateScanSerializer(data=request.data)
        if serializer.is_valid():
            # Pass args explicitly because task signature is (dir, ext, method)
            d = serializer.validated_data
            task = task_scan_duplicates.delay(d['directory'], d['extensions'], d['method'])
            return Response({"task_id": task.id}, status=status.HTTP_202_ACCEPTED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class SearchView(APIView):
    """
    Search is typically synchronous for APIs.
    """
    def get(self, request):
        # We use the serializer to validate query params
        serializer = SearchSerializer(data=request.query_params)
        if serializer.is_valid():
            # Instantiate your DB wrapper here
            # db = ImageDatabase() 
            # results = db.search_images(**serializer.validated_data)
            results = [] # Mock
            return Response({"results": results})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class TrainingView(CoreTaskView):
    def post(self, request):
        return self.launch_task(TrainingSerializer, task_train_gan, request.data)

class FrameExtractionView(CoreTaskView):
    def post(self, request):
        return self.launch_task(FrameExtractionSerializer, task_extract_frames, request.data)

class GifExtractionView(CoreTaskView):
    def post(self, request):
        return self.launch_task(GifExtractionSerializer, task_create_gif, request.data)

class VideoExtractionView(CoreTaskView):
    def post(self, request):
        return self.launch_task(VideoExtractionSerializer, task_extract_video_clip, request.data)

class CloudSyncView(CoreTaskView):
    def post(self, request):
        return self.launch_task(CloudSyncSerializer, task_cloud_sync, request.data)

class ImageCrawlView(CoreTaskView):
    def post(self, request):
        return self.launch_task(ImageCrawlSerializer, task_crawl_images, request.data)

class ReverseSearchView(CoreTaskView):
    def post(self, request):
        return self.launch_task(ReverseSearchSerializer, task_reverse_search, request.data)

class WebRequestView(CoreTaskView):
    def post(self, request):
        return self.launch_task(WebRequestSerializer, task_web_request, request.data)
    
class DatabaseConnectView(CoreTaskView):
    """Test connection and get stats"""
    def post(self, request):
        return self.launch_task(DatabaseConfigSerializer, task_db_test_connection, request.data)

class DatabaseAddGroupView(CoreTaskView):
    def post(self, request):
        return self.launch_task(DbAddGroupSerializer, task_db_add_group, request.data)

class DatabaseAddSubgroupView(CoreTaskView):
    def post(self, request):
        return self.launch_task(DbAddSubgroupSerializer, task_db_add_subgroup, request.data)

class DatabaseAddTagView(CoreTaskView):
    def post(self, request):
        return self.launch_task(DbAddTagSerializer, task_db_add_tag, request.data)

class DatabaseAutoPopulateView(CoreTaskView):
    def post(self, request):
        return self.launch_task(DbAutoPopulateSerializer, task_db_auto_populate, request.data)

class DatabaseResetView(CoreTaskView):
    def post(self, request):
        return self.launch_task(DatabaseConfigSerializer, task_db_reset, request.data)