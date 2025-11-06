from rest_framework import viewsets
from .models import ImageRecord
from .serializers import ImageRecordSerializer
from django.shortcuts import render


class ImageRecordViewSet(viewsets.ModelViewSet):
    """
    A viewset that automatically provides 'list', 'create', 'retrieve', 
    'update', 'partial_update', and 'destroy' actions for ImageRecord model.

    The primary methods supported are:
    - GET /api/images/ (list all records)
    - POST /api/images/ (create a new record)
    - GET /api/images/{id}/ (retrieve a specific record)
    - PUT/PATCH /api/images/{id}/ (update a specific record)
    - DELETE /api/images/{id}/ (delete a specific record)
    """
    # The queryset defines which records this ViewSet will operate on
    queryset = ImageRecord.objects.all().order_by('series_name', 'file_path')
    
    # The serializer class determines how the data is converted to and from JSON
    serializer_class = ImageRecordSerializer
    
    # Optional: You can customize permissions here if needed
    # permission_classes = [permissions.IsAuthenticated] 
