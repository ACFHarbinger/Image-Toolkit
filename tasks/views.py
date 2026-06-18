from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiResponse, inline_serializer
from rest_framework import serializers as drf_serializers
from .serializers import (
    FrameExtractionSerializer,
    DbAutoPopulateSerializer,
    DatabaseConfigSerializer,
    DbAddGroupSerializer,
    DbAddSubgroupSerializer,
    DbAddTagSerializer,
    SearchSerializer,
    TrainingSerializer,
    ConversionSerializer,
    MergeSerializer,
    CloudSyncSerializer,
    ImageCrawlSerializer,
    DeletionSerializer,
    DuplicateScanSerializer,
    ReverseSearchSerializer,
    WebRequestSerializer,
    GifExtractionSerializer,
    VideoExtractionSerializer,
)
from .tasks import (
    task_convert_images,
    task_merge_images,
    task_delete_files,
    task_scan_duplicates,
    task_train_gan,
    task_extract_frames,
    task_create_gif,
    task_extract_video_clip,
    task_cloud_sync,
    task_crawl_images,
    task_reverse_search,
    task_web_request,
    task_db_test_connection,
    task_db_add_group,
    task_db_add_subgroup,
    task_db_add_tag,
    task_db_auto_populate,
    task_db_reset,
)

# Shared response schemas used by all async task endpoints.
_TASK_QUEUED = OpenApiResponse(
    response=inline_serializer(
        name="TaskQueuedResponse",
        fields={
            "task_id": drf_serializers.UUIDField(),
            "status": drf_serializers.CharField(),
        },
    ),
    description="Task accepted and queued for background processing.",
)
_VALIDATION_ERROR = OpenApiResponse(description="Request body failed validation.")


class CoreTaskView(APIView):
    """
    Generic view helper to validate serializer and launch task.
    """

    def launch_task(self, serializer_cls, task_func, data):
        serializer = serializer_cls(data=data)
        if serializer.is_valid():
            # .delay() sends the task to Celery
            task = task_func.delay(serializer.validated_data)
            return Response(
                {"task_id": task.id, "status": "processing"},
                status=status.HTTP_202_ACCEPTED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    tags=["Core"],
    summary="Convert images to another format",
    request=ConversionSerializer,
    responses={202: _TASK_QUEUED, 400: _VALIDATION_ERROR},
)
class ConvertView(CoreTaskView):
    def post(self, request):
        return self.launch_task(ConversionSerializer, task_convert_images, request.data)


@extend_schema(
    tags=["Core"],
    summary="Merge multiple images into a single composite",
    request=MergeSerializer,
    responses={202: _TASK_QUEUED, 400: _VALIDATION_ERROR},
)
class MergeView(CoreTaskView):
    def post(self, request):
        return self.launch_task(MergeSerializer, task_merge_images, request.data)


@extend_schema(
    tags=["Core"],
    summary="Delete files or a directory",
    request=DeletionSerializer,
    responses={202: _TASK_QUEUED, 400: _VALIDATION_ERROR},
)
class DeleteView(CoreTaskView):
    def post(self, request):
        return self.launch_task(DeletionSerializer, task_delete_files, request.data)


@extend_schema(
    tags=["Core"],
    summary="Scan a directory for duplicate images",
    request=DuplicateScanSerializer,
    responses={202: _TASK_QUEUED, 400: _VALIDATION_ERROR},
)
class DuplicateScanView(APIView):
    def post(self, request):
        serializer = DuplicateScanSerializer(data=request.data)
        if serializer.is_valid():
            # Pass args explicitly because task signature is (dir, ext, method)
            d = serializer.validated_data
            task = task_scan_duplicates.delay(
                d["directory"], d["extensions"], d["method"]
            )
            return Response({"task_id": task.id}, status=status.HTTP_202_ACCEPTED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    tags=["Core"],
    summary="Search images by filename or tags",
    parameters=[SearchSerializer],
    responses={
        200: OpenApiResponse(
            response=inline_serializer(
                name="SearchResponse",
                fields={"results": drf_serializers.ListField(child=drf_serializers.DictField())},
            ),
            description="List of matching image records.",
        ),
        400: _VALIDATION_ERROR,
    },
)
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
            results = []  # Mock
            return Response({"results": results})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    tags=["AI & Video"],
    summary="Train a GAN model on a local image dataset",
    request=TrainingSerializer,
    responses={202: _TASK_QUEUED, 400: _VALIDATION_ERROR},
)
class TrainingView(CoreTaskView):
    def post(self, request):
        return self.launch_task(TrainingSerializer, task_train_gan, request.data)


@extend_schema(
    tags=["AI & Video"],
    summary="Extract frames from a video file",
    request=FrameExtractionSerializer,
    responses={202: _TASK_QUEUED, 400: _VALIDATION_ERROR},
)
class FrameExtractionView(CoreTaskView):
    def post(self, request):
        return self.launch_task(
            FrameExtractionSerializer, task_extract_frames, request.data
        )


@extend_schema(
    tags=["AI & Video"],
    summary="Create an animated GIF from a video clip",
    request=GifExtractionSerializer,
    responses={202: _TASK_QUEUED, 400: _VALIDATION_ERROR},
)
class GifExtractionView(CoreTaskView):
    def post(self, request):
        return self.launch_task(GifExtractionSerializer, task_create_gif, request.data)


@extend_schema(
    tags=["AI & Video"],
    summary="Extract a video clip between two timestamps",
    request=VideoExtractionSerializer,
    responses={202: _TASK_QUEUED, 400: _VALIDATION_ERROR},
)
class VideoExtractionView(CoreTaskView):
    def post(self, request):
        return self.launch_task(
            VideoExtractionSerializer, task_extract_video_clip, request.data
        )


@extend_schema(
    tags=["Web"],
    summary="Sync a local directory with a cloud provider",
    request=CloudSyncSerializer,
    responses={202: _TASK_QUEUED, 400: _VALIDATION_ERROR},
)
class CloudSyncView(CoreTaskView):
    def post(self, request):
        return self.launch_task(CloudSyncSerializer, task_cloud_sync, request.data)


@extend_schema(
    tags=["Web"],
    summary="Crawl image boards or arbitrary URLs for images",
    request=ImageCrawlSerializer,
    responses={202: _TASK_QUEUED, 400: _VALIDATION_ERROR},
)
class ImageCrawlView(CoreTaskView):
    def post(self, request):
        return self.launch_task(ImageCrawlSerializer, task_crawl_images, request.data)


@extend_schema(
    tags=["Web"],
    summary="Perform a reverse image search across configured engines",
    request=ReverseSearchSerializer,
    responses={202: _TASK_QUEUED, 400: _VALIDATION_ERROR},
)
class ReverseSearchView(CoreTaskView):
    def post(self, request):
        return self.launch_task(
            ReverseSearchSerializer, task_reverse_search, request.data
        )


@extend_schema(
    tags=["Web"],
    summary="Execute an arbitrary HTTP request via the backend",
    request=WebRequestSerializer,
    responses={202: _TASK_QUEUED, 400: _VALIDATION_ERROR},
)
class WebRequestView(CoreTaskView):
    def post(self, request):
        return self.launch_task(WebRequestSerializer, task_web_request, request.data)


@extend_schema(
    tags=["Database"],
    summary="Test the PostgreSQL connection and return server stats",
    request=DatabaseConfigSerializer,
    responses={202: _TASK_QUEUED, 400: _VALIDATION_ERROR},
)
class DatabaseConnectView(CoreTaskView):
    """Test connection and get stats"""

    def post(self, request):
        return self.launch_task(
            DatabaseConfigSerializer, task_db_test_connection, request.data
        )


@extend_schema(
    tags=["Database"],
    summary="Create one or more image groups",
    request=DbAddGroupSerializer,
    responses={202: _TASK_QUEUED, 400: _VALIDATION_ERROR},
)
class DatabaseAddGroupView(CoreTaskView):
    def post(self, request):
        return self.launch_task(DbAddGroupSerializer, task_db_add_group, request.data)


@extend_schema(
    tags=["Database"],
    summary="Create one or more subgroups under a parent group",
    request=DbAddSubgroupSerializer,
    responses={202: _TASK_QUEUED, 400: _VALIDATION_ERROR},
)
class DatabaseAddSubgroupView(CoreTaskView):
    def post(self, request):
        return self.launch_task(
            DbAddSubgroupSerializer, task_db_add_subgroup, request.data
        )


@extend_schema(
    tags=["Database"],
    summary="Create one or more image tags",
    request=DbAddTagSerializer,
    responses={202: _TASK_QUEUED, 400: _VALIDATION_ERROR},
)
class DatabaseAddTagView(CoreTaskView):
    def post(self, request):
        return self.launch_task(DbAddTagSerializer, task_db_add_tag, request.data)


@extend_schema(
    tags=["Database"],
    summary="Auto-populate the database from a source directory",
    request=DbAutoPopulateSerializer,
    responses={202: _TASK_QUEUED, 400: _VALIDATION_ERROR},
)
class DatabaseAutoPopulateView(CoreTaskView):
    def post(self, request):
        return self.launch_task(
            DbAutoPopulateSerializer, task_db_auto_populate, request.data
        )


@extend_schema(
    tags=["Database"],
    summary="Reset the database (drop and recreate schema)",
    request=DatabaseConfigSerializer,
    responses={202: _TASK_QUEUED, 400: _VALIDATION_ERROR},
)
class DatabaseResetView(CoreTaskView):
    def post(self, request):
        return self.launch_task(DatabaseConfigSerializer, task_db_reset, request.data)
