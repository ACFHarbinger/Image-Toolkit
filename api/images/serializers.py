from rest_framework import serializers
from .models import ImageRecord


class ImageRecordSerializer(serializers.ModelSerializer):
    """
    Converts ImageRecord model instances to JSON (serialization) 
    and validates incoming data (deserialization).
    """
    class Meta:
        model = ImageRecord
        # Fields to be included in the API response (GET) and allowed in the request (POST/PUT)
        fields = ['id', 'file_path', 'file_hash', 'series_name', 'characters', 'tags', 'date_added']
        # Set 'id' and 'date_added' as read-only fields
        read_only_fields = ['id', 'date_added', 'file_hash']
