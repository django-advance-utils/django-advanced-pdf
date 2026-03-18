# AGENTS.md

## Cursor Cloud specific instructions

### Overview

**django-advanced-pdf** is a Django reusable app for generating PDF documents from XML templates using ReportLab. The repository contains:
- `django_advanced_pdf/` — the library (published to PyPI)
- `django_examples/` — a demo Django project showcasing the library

### Running services

The project uses Docker Compose (`docker-compose.yaml`) to orchestrate all services. Before starting, ensure Docker is running (`sudo nohup dockerd > /tmp/dockerd.log 2>&1 &`).

```
docker compose up -d
```

This starts 4 containers:
| Service | Port | Purpose |
|---|---|---|
| `django_pdf` | 8012 | Django dev server (auto-runs migrations) |
| `db_pdf` | 5432 (internal) | PostgreSQL 13 |
| `redis` | 6380 | Redis (Celery broker + Django cache) |
| `celery` | N/A | Celery worker (optional — only for async PDF tasks) |

The Django app is accessible at `http://localhost:8012/`.

**Caveat:** The Celery container may fail with `ModuleNotFoundError: No module named 'pkg_resources'` due to Python 3.12 removing `setuptools` by default. This only affects the "Task Examples" async feature; all synchronous PDF generation works without Celery.

### Tests

Unit tests are pure `unittest` (no Django test runner needed). Run inside the Django container:

```
docker compose exec django_pdf python -m unittest django_advanced_pdf.tests -v
```

Tests compare rendered PDF pages as PNG images against reference images in `django_advanced_pdf/test_data/held/`.

### Lint

No dedicated linter config (flake8/ruff/pyproject.toml) exists in the repo. Use Django's system check as a basic lint:

```
docker compose exec django_pdf python manage.py check
```

### Django settings

The settings file (`django_examples/django_examples/settings.py`) hardcodes Docker service hostnames (`db_pdf`, `redis`) — these only resolve inside the Docker network. Do not attempt to run the Django server outside Docker without adjusting these.

### Docker-in-Docker notes (Cloud Agent VMs)

Cloud Agent VMs require special Docker setup: `fuse-overlayfs` storage driver, `iptables-legacy`, and socket permissions (`sudo chmod 666 /var/run/docker.sock`). The VM snapshot handles Docker installation; just start the daemon with `sudo nohup dockerd > /tmp/dockerd.log 2>&1 &` before running `docker compose` commands.
