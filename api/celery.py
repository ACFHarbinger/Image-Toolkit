import os

from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'api.settings')

# Create Celery application instance
app = Celery('api')

# Load configuration from Django settings, including CELERY namespace prefix (e.g., CELERY_BROKER_URL)
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps (like tasks)
app.autodiscover_tasks()