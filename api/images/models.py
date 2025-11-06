from django.db import models


class ImageRecord(models.Model):
    """
    Represents an entry in the image database, similar to your PySide6 data model.
    """
    # File & Path Information
    file_path = models.CharField(max_length=512, unique=True, help_text="The absolute path to the image file.")
    file_hash = models.CharField(max_length=64, unique=True, null=True, blank=True, help_text="SHA-256 hash of the file content.")
    
    # Metadata Fields
    series_name = models.CharField(max_length=100, null=True, blank=True)
    characters = models.JSONField(default=list, blank=True, help_text="List of character names (JSON array).")
    tags = models.JSONField(default=list, blank=True, help_text="List of descriptive tags (JSON array).")
    
    # Timestamps
    date_added = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.series_name or 'Untitled'} - {self.file_path[-30:]}"

    class Meta:
        verbose_name = "Image Record"
        verbose_name_plural = "Image Records"
