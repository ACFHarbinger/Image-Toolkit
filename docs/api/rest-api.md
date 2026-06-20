# REST API Reference

Image Toolkit exposes an async REST API built with [Django REST Framework](https://www.django-rest-framework.org/)
and documented with [drf-spectacular](https://drf-spectacular.readthedocs.io/), which auto-generates an
OpenAPI 3.1 schema from the view and serializer definitions.

## Interactive playgrounds (local server)

When running the local Django server (`uv run python manage.py runserver`), three
interactive API explorers are available:

| URL | Tool | Notes |
|-----|------|-------|
| `/api/schema/` | Raw OpenAPI 3.1 YAML | Download or pipe to `yq` / `jq` |
| `/api/docs/` | Swagger UI | Try-it-out for every endpoint |
| `/api/redoc/` | Redoc | Read-only reference; best for long-form docs |

The schema is generated live from the DRF router — no static file needs updating
when endpoints change.

## Generating a static OpenAPI spec

```bash
# Activate venv first
source .venv/bin/activate

# Write the spec to a file
python manage.py spectacular --file openapi.yaml

# Or validate the spec in one step
python manage.py spectacular --validate --fail-on-warn
```

## Response format

All endpoints that dispatch a Celery task return:

```json
{
  "task_id": "<celery-task-uuid>",
  "status": "processing"
}
```

with HTTP **202 Accepted**. Poll or subscribe to task status via Celery's result
backend. Validation errors return HTTP **400** with a `detail` object.

---

## Endpoints

### Core

| Method | Path | Summary | Key inputs |
|--------|------|---------|-----------|
| `POST` | `/api/convert/` | Convert images to a target format | `input_path`, `output_format`, `output_path`, `input_formats[]` |
| `POST` | `/api/merge/` | Merge two images (overlay / stitch) | `base_path`, `overlay_path`, `output_path`, `mode` |
| `POST` | `/api/delete/` | Delete files matching a pattern | `target_path`, `pattern` |
| `POST` | `/api/scan-duplicates/` | Scan directory for duplicate images | `directory`, `threshold`, `hash_method` |
| `GET`  | `/api/search/` | Semantic vector search via pgvector | `query` (text), `top_k`, `group_id` |

### AI & Video

| Method | Path | Summary | Key inputs |
|--------|------|---------|-----------|
| `POST` | `/api/train-gan/` | Start GAN training run | `dataset_path`, `epochs`, `batch_size`, `model_tag` |
| `POST` | `/api/extract-frames/` | Extract frames from a video file | `video_path`, `output_dir`, `fps`, `start_time`, `end_time` |
| `POST` | `/api/extract-gif/` | Create an animated GIF from frames | `frames_dir`, `output_path`, `fps`, `resize` |
| `POST` | `/api/extract-video/` | Extract a clip from a video | `video_path`, `output_path`, `start_time`, `end_time`, `codec` |

### Web & Crawlers

| Method | Path | Summary | Key inputs |
|--------|------|---------|-----------|
| `POST` | `/api/cloud-sync/` | Sync a local folder to cloud storage | `provider` (`google`/`dropbox`/`onedrive`), `local_path`, `remote_path` |
| `POST` | `/api/crawl-images/` | Crawl an image board or generic URL | `type` (`general`/`board`), `url`, `output_dir`, `max_pages`, `tags[]` |
| `POST` | `/api/reverse-search/` | Reverse-image search via CLIP embedding | `image_path`, `top_k`, `threshold` |
| `POST` | `/api/web-request/` | Execute an arbitrary authenticated web request | `url`, `method`, `headers`, `body` |

### Database

| Method | Path | Summary | Key inputs |
|--------|------|---------|-----------|
| `POST` | `/api/db/connect/` | Test the PostgreSQL connection | `host`, `port`, `dbname`, `user` |
| `POST` | `/api/db/add-group/` | Create one or more image groups | `name`, `description`, `tags[]` |
| `POST` | `/api/db/add-subgroup/` | Create subgroups within a group | `group_id`, `name`, `description` |
| `POST` | `/api/db/add-tag/` | Create tags for classification | `name`, `category`, `color` |
| `POST` | `/api/db/auto-populate/` | Auto-populate DB from a directory scan | `directory`, `group_name`, `recurse`, `embed_clip` |
| `POST` | `/api/db/reset/` | Reset the database (destroys all data) | `confirm` (must be `true`) |

### OpenAPI meta-endpoints

| Method | Path | Tool |
|--------|------|------|
| `GET` | `/api/schema/` | drf-spectacular (OpenAPI 3.1 YAML) |
| `GET` | `/api/docs/` | Swagger UI |
| `GET` | `/api/redoc/` | Redoc |

---

## Authentication

The API does not enforce authentication in development (`DEBUG=True`). In
production deployments, add DRF authentication classes (`TokenAuthentication` or
`SessionAuthentication`) to `DEFAULT_AUTHENTICATION_CLASSES` in `api/settings.py`.
The `drf-spectacular` schema will automatically document the security schemes once
they are wired.

## Adding a new endpoint

1. Add the serializer to `tasks/serializers.py` (DRF `Serializer`).
2. Add the view to `tasks/views.py` — annotate with `@extend_schema(tags=[...], summary=..., request=..., responses={202: _TASK_QUEUED, 400: _VALIDATION_ERROR})`.
3. Wire the URL in `tasks/urls.py`.
4. Add the Celery task body to `tasks/tasks.py`.
5. Run `python manage.py spectacular --validate` to verify the schema is valid.

!!! tip "Schema drift detection"
    Add `python manage.py spectacular --validate --fail-on-warn` as a CI step in
    `.github/workflows/docs.yml` to catch any undocumented endpoints or missing
    `@extend_schema` decorators automatically.
