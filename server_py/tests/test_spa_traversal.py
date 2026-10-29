"""The SPA catch-all in main.py must never serve a file outside client/dist.

uvicorn percent-decodes the request path before routing, so `/%2e%2e/...`
reached `serve_frontend` as `../...` and `os.path.join` walked out of the
dist directory: `GET /%2e%2e/%2e%2e/VERSION` returned the repo-root VERSION
file unauthenticated (confirmed 2026-10-15). A backslash (`..%5c`) and an
absolute path (`/C:/...`, which makes `os.path.join` discard the dist
directory) escaped the same way. On the target that exposes `.env`, the TLS
key and the database dumps.

httpx keeps an encoded path exactly as sent and its ASGITransport decodes it
into `scope["path"]`, as uvicorn does, so each request below reaches the route
as it would in production. A hostile path gets index.html, the same answer as
any unknown SPA route, never the file and never a 500.
"""

import os
from pathlib import Path

import pytest
from httpx import AsyncClient

from src.main import frontend_dist

pytestmark = pytest.mark.skipif(
    not os.path.isfile(os.path.join(frontend_dist, "index.html")),
    reason="client/dist is not built",
)

_REPO_ROOT = Path(os.path.abspath(__file__)).parents[2]
_VERSION_FILE = _REPO_ROOT / "VERSION"


def _index_html() -> bytes:
    with open(os.path.join(frontend_dist, "index.html"), "rb") as f:
        return f.read()


def _absolute_url_paths(path: Path) -> list[str]:
    """`path` as a request path: `/C:/...` on Windows, `//home/...` elsewhere.

    Both the resolved and the unresolved form, since a checkout reached through
    a junction or symlink (as a git worktree here is) has two absolute paths,
    possibly on two drives."""
    forms = {os.path.realpath(path), os.path.abspath(path)}
    return sorted("/" + p.replace("\\", "/") for p in forms)


TRAVERSAL_PATHS = [
    "/%2e%2e/%2e%2e/VERSION",
    "/..%5c..%5cVERSION",
    "/%2e%2e%2f%2e%2e%2fVERSION",
    "/%2e%2e%5c%2e%2e%5cVERSION",
    *_absolute_url_paths(_VERSION_FILE),
]


@pytest.mark.parametrize("url_path", TRAVERSAL_PATHS)
async def test_traversal_serves_index_not_the_file(client: AsyncClient, url_path: str):
    response = await client.get(url_path)
    assert response.status_code == 200
    assert response.content == _index_html()
    assert response.content != _VERSION_FILE.read_bytes()


@pytest.mark.parametrize(
    "url_path", ["/assets/%2e%2e/%2e%2e/%2e%2e/VERSION", "/assets/..%5c..%5c..%5cVERSION"]
)
async def test_assets_mount_refuses_traversal(client: AsyncClient, url_path: str):
    # /assets is Starlette's StaticFiles, which has its own containment check.
    response = await client.get(url_path)
    assert response.status_code == 404
    assert response.content != _VERSION_FILE.read_bytes()


@pytest.mark.skipif(os.name != "nt", reason="drive letters are Windows only")
async def test_path_on_another_drive_is_not_a_500(client: AsyncClient):
    # os.path.commonpath raises ValueError for paths on two drives.
    dist_drive = os.path.splitdrive(os.path.realpath(frontend_dist))[0].upper()
    other = "Y:" if dist_drive == "Z:" else "Z:"
    response = await client.get(f"/{other}/nonexistent/VERSION")
    assert response.status_code == 200
    assert response.content == _index_html()


@pytest.mark.parametrize(
    "url_path",
    # A NUL byte; and a run of dots, which Windows resolves to a `\?\`
    # path that os.path.commonpath reads as another drive.
    ["/%00", "/favicon.svg%00", "/%00/%2e%2e/VERSION", "/..../VERSION", "/...%5cVERSION"],
)
async def test_unresolvable_path_is_not_a_500(client: AsyncClient, url_path: str):
    response = await client.get(url_path)
    assert response.status_code == 200
    assert response.content == _index_html()


async def test_real_dist_file_is_served(client: AsyncClient):
    response = await client.get("/favicon.svg")
    assert response.status_code == 200
    with open(os.path.join(frontend_dist, "favicon.svg"), "rb") as f:
        assert response.content == f.read()


@pytest.mark.parametrize("url_path", ["/", "/some/spa/route", "/index.html"])
async def test_spa_routes_serve_index(client: AsyncClient, url_path: str):
    response = await client.get(url_path)
    assert response.status_code == 200
    assert response.content == _index_html()


async def test_unknown_api_path_is_404(client: AsyncClient):
    response = await client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}
