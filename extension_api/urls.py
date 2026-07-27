from django.urls import path

from .views import (
    DupCheckView,
    IngestView,
    PhashSnapshotView,
    PingView,
    SimilarView,
)

urlpatterns = [
    path("ping/", PingView.as_view(), name="ext_ping"),
    path("dup-check/", DupCheckView.as_view(), name="ext_dup_check"),
    path("ingest/", IngestView.as_view(), name="ext_ingest"),
    path("similar/", SimilarView.as_view(), name="ext_similar"),
    path("phash-snapshot/", PhashSnapshotView.as_view(), name="ext_phash_snapshot"),
]
