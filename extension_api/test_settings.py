"""Test-run settings shim for ``extension_api`` in isolation.

``manage.py test`` runs Django's system checks against the *whole* project
``ROOT_URLCONF`` (``api.urls``) before executing a single test — that graph
also pulls in ``tasks.urls`` -> ``tasks.views`` -> ``tasks.tasks``, which
fails to import (``from backend.src.database import PgvectorImageDatabase``,
an archived DB.6 symbol; see ``tasks/tasks.py`` line ~15). This is
pre-existing and unrelated to the extension bridge — but it means even
``BridgeTestCase``'s own ``@override_settings(ROOT_URLCONF=...)`` (applied
per test case, too late for the command-level check pass) can't unblock a
plain ``manage.py test extension_api`` run.

Run the bridge's test suite in isolation from that breakage with::

    python manage.py test extension_api --settings=extension_api.test_settings

which points ``ROOT_URLCONF`` at ``extension_api/test_urls.py`` (this
app's URLs only) from the very start, so the check phase never touches
``tasks.urls`` at all.
"""

from api.settings import *  # noqa: F401,F403

ROOT_URLCONF = "extension_api.test_urls"
