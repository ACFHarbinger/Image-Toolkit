from django.urls import path

from .views import (
    CvBgRemoveView,
    CvJobStatusView,
    CvUpscaleView,
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
    # §7.14A/B — App-powered CV operations
    path("cv/bg-remove/", CvBgRemoveView.as_view(), name="ext_cv_bg_remove"),
    path("cv/upscale/", CvUpscaleView.as_view(), name="ext_cv_upscale"),
    path(
        "cv/status/<str:job_id>/",
        CvJobStatusView.as_view(),
        name="ext_cv_job_status",
    ),
]
