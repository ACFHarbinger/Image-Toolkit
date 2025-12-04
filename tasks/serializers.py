from rest_framework import serializers

class ConversionSerializer(serializers.Serializer):
    input_path = serializers.CharField(max_length=1024)
    output_path = serializers.CharField(max_length=1024, required=False, allow_blank=True)
    output_format = serializers.CharField(max_length=10, default="png")
    delete_original = serializers.BooleanField(default=False)
    input_formats = serializers.ListField(child=serializers.CharField(), required=False)

class MergeSerializer(serializers.Serializer):
    input_paths = serializers.ListField(child=serializers.CharField())
    output_path = serializers.CharField(max_length=1024)
    direction = serializers.ChoiceField(choices=['horizontal', 'vertical', 'grid'])
    spacing = serializers.IntegerField(default=0)
    align_mode = serializers.ChoiceField(choices=['top', 'center', 'bottom'], default='center')
    grid_size = serializers.IntegerField(default=0)

class DeletionSerializer(serializers.Serializer):
    target_path = serializers.CharField(max_length=1024)
    mode = serializers.ChoiceField(choices=['files', 'directory'], default='files')
    target_extensions = serializers.ListField(child=serializers.CharField(), required=False)
    # The API implies confirmation by the act of requesting, so 'require_confirm' is omitted

class DuplicateScanSerializer(serializers.Serializer):
    directory = serializers.CharField(max_length=1024)
    extensions = serializers.ListField(child=serializers.CharField())
    method = serializers.ChoiceField(choices=['exact', 'phash', 'orb', 'sift', 'ssim', 'siamese'], default='exact')

class SearchSerializer(serializers.Serializer):
    # Mapping params from SearchWorker
    query = serializers.CharField(required=False, allow_blank=True)
    tags = serializers.ListField(child=serializers.CharField(), required=False)
    # Add other filters specific to your DB implementation

class WallpaperSerializer(serializers.Serializer):
    # Note: Sets wallpaper on the SERVER, not the web client
    path_map = serializers.DictField(child=serializers.CharField())
    style = serializers.CharField(default="Fill")