from __future__ import annotations

import json
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
from threading import Lock
from urllib.parse import parse_qs, urlsplit

from .live_reload import LiveReloadState, inject_live_reload


class SiteRequestHandler(SimpleHTTPRequestHandler):
  def __init__(
    self,
    *args: object,
    directory: str | Path | None = None,
    reload_state: LiveReloadState | None = None,
    **kwargs: object,
  ) -> None:
    self.reload_state = reload_state
    super().__init__(*args, directory=directory, **kwargs)

  def guess_type(self, path: str) -> str:
    content_type = super().guess_type(path)
    if content_type.startswith("text/") and "charset=" not in content_type:
      return f"{content_type}; charset=utf-8"
    return content_type

  def end_headers(self) -> None:
    if self.reload_state is not None:
      self.send_header("Cache-Control", "no-store")
    super().end_headers()

  def log_message(self, format: str, *args: object) -> None:
    if self.reload_state is not None:
      return
    super().log_message(format, *args)

  def do_GET(self) -> None:
    if self.reload_state is not None:
      if urlsplit(self.path).path == "/__sitegen/events":
        self._serve_events()
        return
      if self._serve_live_html():
        return
    super().do_GET()

  def send_error(
    self,
    code: int,
    message: str | None = None,
    explain: str | None = None,
  ) -> None:
    if code == HTTPStatus.NOT_FOUND and self._serve_not_found():
      return
    super().send_error(code, message, explain)

  def _serve_events(self) -> None:
    query = parse_qs(urlsplit(self.path).query)
    supplied_version = query.get("version", ["0"])[0]
    last_event_id = self.headers.get("Last-Event-ID", supplied_version)
    try:
      version = int(last_event_id)
    except ValueError:
      version = 0

    event = self.reload_state.wait_for_update(version, timeout=15)
    if event is None:
      body = b": ping\nretry: 100\n\n"
    else:
      data = json.dumps({"message": event.message})
      body = (
        f"id: {event.version}\nevent: {event.kind}\ndata: {data}\nretry: 100\n\n"
      ).encode()

    self.send_response(200)
    self.send_header("Content-Type", "text/event-stream; charset=utf-8")
    self.send_header("Content-Length", str(len(body)))
    self.end_headers()
    self.wfile.write(body)

  def _serve_live_html(self) -> bool:
    request_path = urlsplit(self.path).path
    translated = Path(self.translate_path(request_path))
    if translated.is_dir():
      if not request_path.endswith("/"):
        return False
      translated /= "index.html"
    if translated.suffix.lower() != ".html" or not translated.is_file():
      return False

    html = translated.read_text(encoding="utf-8")
    body = inject_live_reload(html, self.reload_state.version).encode("utf-8")
    self.send_response(200)
    self.send_header("Content-Type", "text/html; charset=utf-8")
    self.send_header("Content-Length", str(len(body)))
    self.end_headers()
    self.wfile.write(body)
    return True

  def _serve_not_found(self) -> bool:
    not_found_path = Path(self.translate_path("/404.html"))
    if not not_found_path.is_file():
      return False

    html = not_found_path.read_text(encoding="utf-8")
    if self.reload_state is not None:
      html = inject_live_reload(html, self.reload_state.version)
    body = html.encode("utf-8")
    self.send_response(HTTPStatus.NOT_FOUND)
    self.send_header("Content-Type", "text/html; charset=utf-8")
    self.send_header("Content-Length", str(len(body)))
    self.end_headers()
    if self.command != "HEAD":
      self.wfile.write(body)
    return True


class ServedDirectory:
  def __init__(self, path: Path) -> None:
    self._path = Path(path)
    self._lock = Lock()

  def update(self, path: Path) -> None:
    with self._lock:
      self._path = Path(path)

  def __fspath__(self) -> str:
    with self._lock:
      return str(self._path)
