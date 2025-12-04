from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import (
    ConversionSerializer, MergeSerializer, 
    DeletionSerializer, DuplicateScanSerializer,
    WallpaperSerializer, SearchSerializer
)
from .tasks import (
    task_convert_images, task_merge_images, 
    task_delete_files, task_scan_duplicates
)
from backend.src.core import WallpaperManager

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

class WallpaperView(APIView):
    def post(self, request):
        serializer = WallpaperSerializer(data=request.data)
        if serializer.is_valid():
            try:
                # Running directly as it interacts with OS display settings
                # WARNING: This sets the wallpaper on the SERVER hosting Django
                d = serializer.validated_data
                WallpaperManager.apply_wallpaper(
                    d['path_map'], 
                    [], # Monitor detection might fail on server, provide defaults if needed
                    d['style'], 
                    "qdbus_placeholder" 
                )
                return Response({"status": "success"})
            except Exception as e:
                return Response({"status": "error", "message": str(e)}, status=500)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)