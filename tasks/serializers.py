from rest_framework import serializers


class ConversionSerializer(serializers.Serializer):
    input_path = serializers.CharField(max_length=1024)
    output_path = serializers.CharField(
        max_length=1024, required=False, allow_blank=True
    )
    output_format = serializers.CharField(max_length=10, default="png")
    delete_original = serializers.BooleanField(default=False)
    input_formats = serializers.ListField(child=serializers.CharField(), required=False)


class MergeSerializer(serializers.Serializer):
    input_paths = serializers.ListField(child=serializers.CharField())
    output_path = serializers.CharField(max_length=1024)
    direction = serializers.ChoiceField(choices=["horizontal", "vertical", "grid"])
    spacing = serializers.IntegerField(default=0)
    align_mode = serializers.ChoiceField(
        choices=["top", "center", "bottom"], default="center"
    )
    grid_size = serializers.IntegerField(default=0)


class DeletionSerializer(serializers.Serializer):
    target_path = serializers.CharField(max_length=1024)
    mode = serializers.ChoiceField(choices=["files", "directory"], default="files")
    target_extensions = serializers.ListField(
        child=serializers.CharField(), required=False
    )
    # The API implies confirmation by the act of requesting, so 'require_confirm' is omitted


class DuplicateScanSerializer(serializers.Serializer):
    directory = serializers.CharField(max_length=1024)
    extensions = serializers.ListField(child=serializers.CharField())
    method = serializers.ChoiceField(
        choices=["exact", "phash", "orb", "sift", "ssim", "siamese"], default="exact"
    )


class SearchSerializer(serializers.Serializer):
    # Mapping params from SearchWorker
    query = serializers.CharField(required=False, allow_blank=True)
    tags = serializers.ListField(child=serializers.CharField(), required=False)
    # Add other filters specific to your DB implementation


class TrainingSerializer(serializers.Serializer):
    data_path = serializers.CharField(max_length=1024)
    save_path = serializers.CharField(max_length=1024)
    epochs = serializers.IntegerField(min_value=1, default=100)
    batch_size = serializers.IntegerField(min_value=1, default=32)
    lr = serializers.FloatField(default=0.0002)
    z_dim = serializers.IntegerField(default=100)
    device_name = serializers.CharField(default="cpu")  # 'cuda' or 'cpu'


class FrameExtractionSerializer(serializers.Serializer):
    video_path = serializers.CharField(max_length=1024)
    output_dir = serializers.CharField(max_length=1024)
    start_ms = serializers.IntegerField(min_value=0, default=0)
    end_ms = serializers.IntegerField(default=-1)
    is_range = serializers.BooleanField(default=False)
    target_width = serializers.IntegerField(required=False, allow_null=True)
    target_height = serializers.IntegerField(required=False, allow_null=True)


class GifExtractionSerializer(serializers.Serializer):
    video_path = serializers.CharField(max_length=1024)
    output_path = serializers.CharField(max_length=1024)
    start_ms = serializers.IntegerField(min_value=0)
    end_ms = serializers.IntegerField(min_value=0)
    target_width = serializers.IntegerField(required=False, allow_null=True)
    target_height = serializers.IntegerField(required=False, allow_null=True)
    fps = serializers.IntegerField(default=15)


class VideoExtractionSerializer(serializers.Serializer):
    video_path = serializers.CharField(max_length=1024)
    output_path = serializers.CharField(max_length=1024)
    start_ms = serializers.IntegerField(min_value=0)
    end_ms = serializers.IntegerField(min_value=0)
    target_width = serializers.IntegerField(required=False, allow_null=True)
    target_height = serializers.IntegerField(required=False, allow_null=True)
    mute_audio = serializers.BooleanField(default=False)


class CloudSyncSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=["google", "dropbox", "onedrive"])
    local_path = serializers.CharField(max_length=1024)
    remote_path = serializers.CharField(max_length=1024)
    dry_run = serializers.BooleanField(default=True)
    action_local = serializers.ChoiceField(
        choices=["upload", "delete_local", "ignore"], default="upload"
    )
    action_remote = serializers.ChoiceField(
        choices=["download", "delete_remote", "ignore"], default="download"
    )

    # Provider-specific fields
    auth_config = serializers.DictField(required=True)
    # google: { "mode": "service_account"|"personal_account", "service_account_data": {...}, "client_secrets_data": {...}, "token_file": "..." }
    # dropbox: { "access_token": "..." }
    # onedrive: { "client_id": "..." }

    share_email = serializers.EmailField(
        required=False, allow_null=True
    )  # For Google Drive Service Account


class ImageCrawlSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=["general", "board"], default="general")
    download_dir = serializers.CharField(max_length=1024)

    # General Crawler
    urls = serializers.ListField(child=serializers.CharField(), required=False)

    # Board Crawler
    board_type = serializers.ChoiceField(
        choices=["danbooru", "gelbooru", "sankaku"], required=False
    )
    tags = serializers.ListField(child=serializers.CharField(), required=False)
    limit = serializers.IntegerField(default=100)
    page = serializers.IntegerField(default=1)

    screenshot_dir = serializers.CharField(
        max_length=1024, required=False, allow_blank=True
    )


class ReverseSearchSerializer(serializers.Serializer):
    image_path = serializers.CharField(max_length=1024)
    min_width = serializers.IntegerField(default=0)
    min_height = serializers.IntegerField(default=0)
    browser = serializers.ChoiceField(choices=["chrome", "firefox"], default="chrome")
    search_mode = serializers.ChoiceField(
        choices=["All", "Google", "Bing", "Yandex", "SauceNAO"], default="All"
    )
    keep_open = serializers.BooleanField(default=False)


class WebRequestSerializer(serializers.Serializer):
    url = serializers.URLField()
    method = serializers.ChoiceField(
        choices=["GET", "POST", "PUT", "DELETE"], default="GET"
    )
    headers = serializers.DictField(required=False, default={})
    data = serializers.DictField(required=False, default={})
    # Add other config keys required by WebRequestsLogic if any


class DatabaseConfigSerializer(serializers.Serializer):
    db_host = serializers.CharField(default="localhost")
    db_port = serializers.CharField(default="5432")
    db_user = serializers.CharField(default="postgres")
    db_password = serializers.CharField(required=False, allow_blank=True)
    db_name = serializers.CharField(default="imagedb")


class DbAddGroupSerializer(DatabaseConfigSerializer):
    group_names = serializers.ListField(child=serializers.CharField())


class DbAddSubgroupSerializer(DatabaseConfigSerializer):
    parent_group = serializers.CharField()
    subgroup_names = serializers.ListField(child=serializers.CharField())


class DbAddTagSerializer(DatabaseConfigSerializer):
    tag_names = serializers.ListField(child=serializers.CharField())
    tag_type = serializers.CharField(required=False, allow_blank=True)


class DbAutoPopulateSerializer(DatabaseConfigSerializer):
    source_path = serializers.CharField(max_length=1024)
