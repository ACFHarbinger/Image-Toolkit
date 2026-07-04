from django.urls import path

from .views import PingView, DupCheckView

urlpatterns = [
    path("ping/", PingView.as_view(), name="ext_ping"),
    path("dup-check/", DupCheckView.as_view(), name="ext_dup_check"),
]
