"""Test-only URLConf: mounts just ``extension_api.urls`` under its real
production prefix (``/api/extension/…``), without pulling in the project's
full ``api.urls`` (which also includes ``tasks.urls`` — broken independently
of this app, at ``tasks/tasks.py``'s `from backend.src.database import
PgvectorImageDatabase`, an archived DB.6 symbol pre-existing this change and
out of this bridge work's scope to fix).

Django's system checks / URL resolution import the *entire* ``ROOT_URLCONF``
graph, so any request made through ``django.test.Client`` under the default
``api.urls`` fails at import time regardless of which app the request is
actually for. ``extension_api``'s test cases point ``ROOT_URLCONF`` at this
module instead (``@override_settings(ROOT_URLCONF="extension_api.test_urls")``
on the shared ``BridgeTestCase``) so the bridge endpoints stay testable in
isolation from that unrelated breakage.
"""

from django.urls import include, path

urlpatterns = [
    path("api/extension/", include("extension_api.urls")),
]
