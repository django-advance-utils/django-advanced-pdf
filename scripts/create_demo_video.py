#!/usr/bin/env python3
"""Record a short browser demo of django-advanced-pdf examples."""

from __future__ import annotations

import argparse
import base64
import html
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIR = ROOT / "django_examples"
MANAGE_PY = PROJECT_DIR / "manage.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create demo video")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "demo" / "django-advanced-pdf-demo.mp4",
        help="Output MP4 path.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8012,
        help="Django development server port.",
    )
    parser.add_argument(
        "--skip-setup",
        action="store_true",
        help="Skip migrate/import setup and use existing demo database.",
    )
    return parser.parse_args()


def base_env() -> dict[str, str]:
    env = os.environ.copy()
    env["DJANGO_SETTINGS_MODULE"] = "django_examples.settings_demo"
    py_path = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{ROOT}:{py_path}" if py_path else str(ROOT)
    return env


def run_manage(*args: str) -> None:
    command = [sys.executable, str(MANAGE_PY), *args]
    print(f"$ {' '.join(command)}")
    subprocess.run(command, cwd=PROJECT_DIR, env=base_env(), check=True)


def wait_for_server(url: str, timeout_seconds: int = 60) -> None:
    start = time.monotonic()
    while time.monotonic() - start < timeout_seconds:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                if response.status < 500:
                    return
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.5)
    raise TimeoutError(f"Server did not become ready in {timeout_seconds}s: {url}")


def start_dev_server(port: int) -> subprocess.Popen:
    command = [
        sys.executable,
        str(MANAGE_PY),
        "runserver",
        f"127.0.0.1:{port}",
        "--noreload",
    ]
    print(f"$ {' '.join(command)}")
    process = subprocess.Popen(
        command,
        cwd=PROJECT_DIR,
        env=base_env(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    wait_for_server(f"http://127.0.0.1:{port}/")
    return process


def stop_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def record_webm(base_url: str, temp_video_dir: Path) -> Path:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is required. Install with `pip3 install playwright` and "
            "`python3 -m playwright install chromium`."
        ) from exc

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage"],
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            record_video_dir=str(temp_video_dir),
            record_video_size={"width": 1280, "height": 720},
        )
        page = context.new_page()

        steps: list[dict[str, str | int]] = [
            {"type": "page", "path": "/", "pause_ms": 3500},
            {"type": "page", "path": "/files/", "pause_ms": 3000},
            {
                "type": "pdf",
                "path": "/view/file/basic/",
                "title": "basic.xml PDF output",
                "pause_ms": 4500,
            },
            {
                "type": "pdf",
                "path": "/view/companies/",
                "title": "companies.xml PDF output",
                "pause_ms": 4500,
            },
            {
                "type": "pdf",
                "path": "/report/example/",
                "title": "combined report PDF output",
                "pause_ms": 4500,
            },
            {
                "type": "pdf",
                "path": "/report/headed-notepaper/",
                "title": "headed notepaper PDF output",
                "pause_ms": 4500,
            },
            {"type": "page", "path": "/", "pause_ms": 2500},
        ]
        for step in steps:
            step_type = str(step["type"])
            step_path = str(step["path"])
            pause_ms = int(step["pause_ms"])
            if step_type == "page":
                page.goto(f"{base_url}{step_path}", wait_until="load")
            elif step_type == "pdf":
                render_pdf_preview(
                    page=page,
                    pdf_url=f"{base_url}{step_path}",
                    title=str(step["title"]),
                )
            else:
                raise ValueError(f"Unknown demo step type: {step_type}")
            page.wait_for_timeout(pause_ms)

        video = page.video
        context.close()
        browser.close()
        return Path(video.path())


def render_pdf_preview(page, pdf_url: str, title: str) -> None:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError(
            "PyMuPDF is required to render PDF previews during recording."
        ) from exc

    with urllib.request.urlopen(pdf_url, timeout=15) as response:
        pdf_data = response.read()

    document = fitz.open(stream=pdf_data, filetype="pdf")
    try:
        first_page = document[0]
        pixmap = first_page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
        png_bytes = pixmap.tobytes("png")
    finally:
        document.close()

    image_b64 = base64.b64encode(png_bytes).decode("ascii")
    safe_title = html.escape(title)
    page.set_content(
        f"""
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>{safe_title}</title>
    <style>
      body {{
        margin: 0;
        font-family: Arial, sans-serif;
        background: #f3f4f6;
      }}
      h1 {{
        margin: 0;
        padding: 18px 24px;
        font-size: 24px;
        background: #111827;
        color: #ffffff;
      }}
      .container {{
        padding: 24px;
        display: flex;
        justify-content: center;
      }}
      img {{
        max-width: 95%;
        max-height: 610px;
        border: 1px solid #d1d5db;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.14);
        background: #ffffff;
      }}
    </style>
  </head>
  <body>
    <h1>{safe_title}</h1>
    <div class="container">
      <img alt="{safe_title}" src="data:image/png;base64,{image_b64}">
    </div>
  </body>
</html>
""",
        wait_until="load",
    )


def transcode_to_mp4(source_webm: Path, output_mp4: Path) -> None:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg is required but was not found on PATH.")

    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(source_webm),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-an",
        str(output_mp4),
    ]
    print(f"$ {' '.join(command)}")
    subprocess.run(command, check=True)


def main() -> int:
    args = parse_args()

    if not MANAGE_PY.exists():
        raise FileNotFoundError(f"Could not locate {MANAGE_PY}")

    if not args.skip_setup:
        run_manage("migrate", "--noinput")
        run_manage("import_advanced_pdf")

    server = start_dev_server(args.port)
    try:
        with tempfile.TemporaryDirectory(prefix="demo-video-") as tmp_dir:
            webm = record_webm(f"http://127.0.0.1:{args.port}", Path(tmp_dir))
            transcode_to_mp4(webm, args.output.resolve())
    finally:
        stop_process(server)

    print(f"Demo video written to: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
