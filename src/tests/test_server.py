import importlib
import inspect
import io
import os
import sys
import tempfile
import types
import unittest
from collections.abc import Iterator
from contextlib import contextmanager, redirect_stderr
from dataclasses import dataclass
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import urlopen


@dataclass(frozen=True)
class FakeBuildOptions:
  include_drafts: bool = False
  incremental: bool = True


class PlaceholderBuilder:
  def __init__(self, project_root: Path) -> None:
    self.project_root = project_root


class PlaceholderValidator:
  pass


@contextmanager
def import_sitegen_module(module_name: str) -> Iterator[types.ModuleType]:
  injected = {
    "sitegen.build": types.ModuleType("sitegen.build"),
    "sitegen.validate": types.ModuleType("sitegen.validate"),
  }
  injected["sitegen.build"].BuildOptions = FakeBuildOptions
  injected["sitegen.build"].SiteBuilder = PlaceholderBuilder
  injected["sitegen.validate"].SiteValidator = PlaceholderValidator
  managed_names = (*injected, "sitegen.cli", "sitegen.server")
  saved_modules = {name: sys.modules.get(name) for name in managed_names}

  for name in ("sitegen.cli", "sitegen.server"):
    sys.modules.pop(name, None)
  sys.modules.update(injected)

  try:
    yield importlib.import_module(module_name)
  finally:
    for name in managed_names:
      sys.modules.pop(name, None)
      if saved_modules[name] is not None:
        sys.modules[name] = saved_modules[name]


class TestServer(unittest.TestCase):
  def test_live_reload_state_publishes_versioned_events(self) -> None:
    with import_sitegen_module("sitegen.live_reload") as live_reload:
      state_class = getattr(live_reload, "LiveReloadState", None)
      self.assertIsNotNone(state_class)
      state = state_class()

      event = state.publish("css", "static/index.css")

      self.assertEqual(event.version, 1)
      self.assertEqual(event.kind, "css")
      self.assertEqual(event.message, "static/index.css")
      self.assertEqual(state.wait_for_update(0, timeout=0), event)
      self.assertIsNone(state.wait_for_update(1, timeout=0))

  def test_live_reload_markup_injects_versioned_client_before_body(self) -> None:
    with import_sitegen_module("sitegen.live_reload") as live_reload:
      inject = getattr(live_reload, "inject_live_reload", None)
      self.assertTrue(callable(inject))

      html = "<!doctype html><html><body><main>hello</main></body></html>"
      rendered = inject(html, version=7)

    self.assertIn("new EventSource", rendered)
    self.assertIn("version=7", rendered)
    self.assertLess(rendered.index("new EventSource"), rendered.index("</body>"))

  def test_live_reload_client_swaps_css_and_renders_build_errors(self) -> None:
    with import_sitegen_module("sitegen.live_reload") as live_reload:
      client = getattr(live_reload, "LIVE_RELOAD_CLIENT", "")

    self.assertIn('link[rel="stylesheet"]', client)
    self.assertIn("build-error", client)
    self.assertIn("__sitegen-error", client)

  def test_request_handler_injects_live_reload_and_disables_cache(self) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
      root = Path(temp_dir)
      (root / "index.html").write_text(
        "<!doctype html><html><body>hello</body></html>",
        encoding="utf-8",
      )

      with import_sitegen_module("sitegen.server") as server:
        parameters = inspect.signature(server.SiteRequestHandler.__init__).parameters
        self.assertIn("reload_state", parameters)
        state = server.LiveReloadState()
        handler = partial(
          server.SiteRequestHandler,
          directory=root,
          reload_state=state,
        )
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
          host, port = httpd.server_address
          with urlopen(f"http://{host}:{port}/", timeout=2) as response:
            html = response.read().decode("utf-8")
            cache_control = response.headers.get("Cache-Control")
        finally:
          httpd.shutdown()
          httpd.server_close()
          thread.join()

    self.assertEqual(cache_control, "no-store")
    self.assertIn("data-sitegen-live-reload", html)
    self.assertIn("version=0", html)

  def test_request_handler_streams_versioned_reload_events(self) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
      root = Path(temp_dir)
      with import_sitegen_module("sitegen.server") as server:
        self.assertTrue(hasattr(server.SiteRequestHandler, "_serve_events"))
        state = server.LiveReloadState()
        state.publish("css", "static/index.css")
        handler = partial(
          server.SiteRequestHandler,
          directory=root,
          reload_state=state,
        )
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
          host, port = httpd.server_address
          with urlopen(
            f"http://{host}:{port}/__sitegen/events?version=0",
            timeout=2,
          ) as response:
            payload = response.read().decode("utf-8")
            content_type = response.headers.get_content_type()
        finally:
          httpd.shutdown()
          httpd.server_close()
          thread.join()

    self.assertEqual(content_type, "text/event-stream")
    self.assertIn("id: 1", payload)
    self.assertIn("event: css", payload)
    self.assertIn('data: {"message": "static/index.css"}', payload)

  def test_request_handler_suppresses_access_logs_during_live_reload(self) -> None:
    with import_sitegen_module("sitegen.server") as server:
      self.assertIn("log_message", server.SiteRequestHandler.__dict__)
      handler = server.SiteRequestHandler.__new__(server.SiteRequestHandler)
      handler.reload_state = server.LiveReloadState()
      stderr = io.StringIO()
      with redirect_stderr(stderr):
        handler.log_message("GET %s", "/__sitegen/events")

    self.assertEqual(stderr.getvalue(), "")

  def test_request_handler_declares_utf8_for_text_assets(self) -> None:
    with import_sitegen_module("sitegen.server") as server:
      handler = server.SiteRequestHandler.__new__(server.SiteRequestHandler)

      self.assertEqual(
        handler.guess_type("llms.txt"),
        "text/plain; charset=utf-8",
      )
      self.assertEqual(
        handler.guess_type("index.html"),
        "text/html; charset=utf-8",
      )
      self.assertEqual(handler.guess_type("image.png"), "image/png")

  def test_request_handler_serves_the_generated_404_for_unknown_paths(self) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
      root = Path(temp_dir)
      (root / "404.html").write_text(
        "<!doctype html><html><body>custom not found</body></html>",
        encoding="utf-8",
      )

      with import_sitegen_module("sitegen.server") as server:
        state = server.LiveReloadState()
        handler = partial(
          server.SiteRequestHandler,
          directory=root,
          reload_state=state,
        )
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
          host, port = httpd.server_address
          with self.assertRaises(HTTPError) as raised:
            urlopen(f"http://{host}:{port}/missing/", timeout=2)
          response = raised.exception
          html = response.read().decode("utf-8")
          cache_control = response.headers.get("Cache-Control")
          content_type = response.headers.get_content_type()
        finally:
          httpd.shutdown()
          httpd.server_close()
          thread.join()

    self.assertEqual(response.code, 404)
    self.assertEqual(content_type, "text/html")
    self.assertEqual(cache_control, "no-store")
    self.assertIn("custom not found", html)
    self.assertIn("data-sitegen-live-reload", html)

  def test_serve_snapshots_inputs_before_the_initial_build(self) -> None:
    events: list[object] = []
    initial_snapshot = {Path("content/post.md"): 1}

    class Builder:
      def __init__(self, project_root: Path) -> None:
        self.output_dir = project_root / "docs"

      def build(self, _options: FakeBuildOptions) -> SimpleNamespace:
        events.append("build")
        return SimpleNamespace(rendered=1, reused=0, output_dir=self.output_dir)

    class FakeWatcher:
      def __init__(
        self,
        _project_root: Path,
        _rebuild: object,
        *,
        initial_snapshot: dict[Path, int] | None = None,
      ) -> None:
        events.append(("watcher", initial_snapshot))

      def start(self) -> None:
        events.append("watcher-started")

      def stop(self) -> None:
        events.append("watcher-stopped")

    class FakeHttpServer:
      def __init__(self, _address: tuple[str, int], _handler: object) -> None:
        events.append("server")

      def __enter__(self) -> "FakeHttpServer":
        return self

      def __exit__(self, *_: object) -> None:
        pass

      def serve_forever(self) -> None:
        pass

    with tempfile.TemporaryDirectory() as temp_dir:
      project_root = Path(temp_dir)
      with import_sitegen_module("sitegen.server") as server:
        server.snapshot_sources = lambda _root: (
          events.append("snapshot") or initial_snapshot
        )
        server.serve(
          project_root,
          FakeBuildOptions(),
          watch=True,
          builder_factory=Builder,
          server_factory=FakeHttpServer,
          watcher_factory=FakeWatcher,
          stdout=io.StringIO(),
        )

    self.assertEqual(
      events,
      [
        "snapshot",
        "build",
        "server",
        ("watcher", initial_snapshot),
        "watcher-started",
        "watcher-stopped",
      ],
    )

  def test_serve_builds_before_starting_threading_http_server(self) -> None:
    events: list[object] = []

    class Builder:
      def __init__(self, project_root: Path) -> None:
        self.output_dir = project_root / "public"

      def build(self, options: FakeBuildOptions) -> SimpleNamespace:
        events.append(("build", options))
        return SimpleNamespace(rendered=1, reused=0, output_dir=self.output_dir)

    class FakeHttpServer:
      def __init__(self, address: tuple[str, int], handler: object) -> None:
        events.append(("server", address, handler))

      def __enter__(self) -> "FakeHttpServer":
        return self

      def __exit__(self, *_: object) -> None:
        events.append("closed")

      def serve_forever(self) -> None:
        events.append("serve_forever")

    with tempfile.TemporaryDirectory() as temp_dir:
      project_root = Path(temp_dir)
      with import_sitegen_module("sitegen.server") as server:
        server.serve(
          project_root,
          FakeBuildOptions(),
          host="127.0.0.1",
          port=9876,
          watch=False,
          builder_factory=Builder,
          server_factory=FakeHttpServer,
          stdout=io.StringIO(),
        )

    self.assertIs(server.ThreadingHTTPServer, ThreadingHTTPServer)
    self.assertEqual(events[0], ("build", FakeBuildOptions()))
    self.assertEqual(events[1][0:2], ("server", ("127.0.0.1", 9876)))
    self.assertEqual(
      os.fspath(events[1][2].keywords["directory"]),
      str(project_root / "public"),
    )
    self.assertEqual(events[2:], ["serve_forever", "closed"])

  def test_serve_does_not_open_a_socket_when_the_initial_build_fails(self) -> None:
    server_started = False

    class BrokenBuilder:
      def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

      def build(self, options: FakeBuildOptions) -> SimpleNamespace:
        raise RuntimeError("initial build failed")

    def server_factory(*_: object) -> object:
      nonlocal server_started
      server_started = True
      return object()

    with tempfile.TemporaryDirectory() as temp_dir:
      with import_sitegen_module("sitegen.server") as server:
        with self.assertRaisesRegex(RuntimeError, "initial build failed"):
          server.serve(
            Path(temp_dir),
            FakeBuildOptions(),
            host="127.0.0.1",
            port=8888,
            watch=False,
            builder_factory=BrokenBuilder,
            server_factory=server_factory,
          )

    self.assertFalse(server_started)

  def test_watch_rebuild_failure_keeps_server_running_and_stops_watcher(self) -> None:
    events: list[object] = []
    published: list[tuple[str, str]] = []

    class Builder:
      def __init__(self, project_root: Path) -> None:
        self.output_dir = project_root / "docs"
        self.attempts = 0

      def build(self, options: FakeBuildOptions) -> SimpleNamespace:
        self.attempts += 1
        events.append(("build", self.attempts))
        if self.attempts == 2:
          raise RuntimeError("broken rebuild")
        return SimpleNamespace(rendered=1, reused=0, output_dir=self.output_dir)

    class FakeWatcher:
      def __init__(self, project_root: Path, rebuild: object, **_: object) -> None:
        self.project_root = project_root
        self.rebuild = rebuild
        events.append(("watcher", project_root))

      def start(self) -> None:
        events.append("watcher-started")
        self.rebuild((self.project_root / "templates" / "blog.html",))

      def stop(self) -> None:
        events.append("watcher-stopped")

    class FakeHttpServer:
      def __init__(self, _address: tuple[str, int], _handler: object) -> None:
        pass

      def __enter__(self) -> "FakeHttpServer":
        return self

      def __exit__(self, *_: object) -> None:
        events.append("server-closed")

      def serve_forever(self) -> None:
        events.append("serve_forever")

    class FakeReloadState:
      version = 0

      def publish(self, kind: str, message: str = "") -> None:
        published.append((kind, message))

    stderr = io.StringIO()
    times = iter((5.0, 5.025))
    with tempfile.TemporaryDirectory() as temp_dir:
      project_root = Path(temp_dir)
      with import_sitegen_module("sitegen.server") as server:
        server.serve(
          project_root,
          FakeBuildOptions(),
          host="127.0.0.1",
          port=8888,
          watch=True,
          live_reload=True,
          builder_factory=Builder,
          server_factory=FakeHttpServer,
          watcher_factory=FakeWatcher,
          reload_state_factory=FakeReloadState,
          clock=lambda: next(times),
          stdout=io.StringIO(),
          stderr=stderr,
        )

    self.assertIn(
      "rebuild failed in 25ms [templates/blog.html]: broken rebuild",
      stderr.getvalue(),
    )
    self.assertEqual(
      published,
      [
        (
          "build-error",
          "rebuild failed in 25ms [templates/blog.html]: broken rebuild",
        )
      ],
    )
    self.assertEqual(
      events,
      [
        ("build", 1),
        ("watcher", project_root),
        "watcher-started",
        ("build", 2),
        "serve_forever",
        "watcher-stopped",
        "server-closed",
      ],
    )

  def test_watch_updates_the_served_directory_after_a_valid_move(self) -> None:
    captured_handler: list[object] = []

    class Builder:
      def __init__(self, project_root: Path) -> None:
        self.outputs = [project_root / "docs", project_root / "preview"]

      def build(self, _options: FakeBuildOptions) -> SimpleNamespace:
        output_dir = self.outputs.pop(0)
        return SimpleNamespace(rendered=1, reused=0, output_dir=output_dir)

    class FakeWatcher:
      def __init__(self, _project_root: Path, rebuild: object, **_: object) -> None:
        self.rebuild = rebuild

      def start(self) -> None:
        self.rebuild()

      def stop(self) -> None:
        pass

    class FakeHttpServer:
      def __init__(self, _address: tuple[str, int], handler: object) -> None:
        captured_handler.append(handler)

      def __enter__(self) -> "FakeHttpServer":
        return self

      def __exit__(self, *_: object) -> None:
        pass

      def serve_forever(self) -> None:
        pass

    with tempfile.TemporaryDirectory() as temp_dir:
      project_root = Path(temp_dir)
      with import_sitegen_module("sitegen.server") as server:
        server.serve(
          project_root,
          FakeBuildOptions(),
          watch=True,
          builder_factory=Builder,
          server_factory=FakeHttpServer,
          watcher_factory=FakeWatcher,
          stdout=io.StringIO(),
        )

    directory = captured_handler[0].keywords["directory"]
    self.assertEqual(os.fspath(directory), str(project_root / "preview"))

  def test_watch_css_rebuild_publishes_hot_swap_event_and_timing(self) -> None:
    published: list[tuple[str, str]] = []

    class Builder:
      def __init__(self, project_root: Path) -> None:
        self.output_dir = project_root / "docs"

      def build(self, _options: FakeBuildOptions) -> SimpleNamespace:
        return SimpleNamespace(rendered=1, reused=6, output_dir=self.output_dir)

    class FakeWatcher:
      def __init__(self, project_root: Path, rebuild: object, **_: object) -> None:
        self.project_root = project_root
        self.rebuild = rebuild

      def start(self) -> None:
        self.rebuild((self.project_root / "static" / "index.css",))

      def stop(self) -> None:
        pass

    class FakeHttpServer:
      def __init__(self, _address: tuple[str, int], _handler: object) -> None:
        pass

      def __enter__(self) -> "FakeHttpServer":
        return self

      def __exit__(self, *_: object) -> None:
        pass

      def serve_forever(self) -> None:
        pass

    class FakeReloadState:
      version = 0

      def publish(self, kind: str, message: str = "") -> None:
        published.append((kind, message))

    times = iter((10.0, 10.015))
    stdout = io.StringIO()
    with tempfile.TemporaryDirectory() as temp_dir:
      project_root = Path(temp_dir)
      with import_sitegen_module("sitegen.server") as server:
        parameters = inspect.signature(server.serve).parameters
        self.assertIn("live_reload", parameters)
        server.serve(
          project_root,
          FakeBuildOptions(),
          watch=True,
          live_reload=True,
          builder_factory=Builder,
          server_factory=FakeHttpServer,
          watcher_factory=FakeWatcher,
          reload_state_factory=FakeReloadState,
          clock=lambda: next(times),
          stdout=stdout,
        )

    self.assertEqual(published, [("css", "static/index.css")])
    self.assertIn("rebuilt 1 page(s), reused 6 in 15ms", stdout.getvalue())
    self.assertIn("static/index.css", stdout.getvalue())

  def test_open_browser_uses_loopback_for_wildcard_host(self) -> None:
    opened: list[str] = []

    class Builder:
      def __init__(self, project_root: Path) -> None:
        self.output_dir = project_root / "docs"

      def build(self, _options: FakeBuildOptions) -> SimpleNamespace:
        return SimpleNamespace(rendered=1, reused=0, output_dir=self.output_dir)

    class FakeHttpServer:
      def __init__(self, _address: tuple[str, int], _handler: object) -> None:
        pass

      def __enter__(self) -> "FakeHttpServer":
        return self

      def __exit__(self, *_: object) -> None:
        pass

      def serve_forever(self) -> None:
        pass

    with tempfile.TemporaryDirectory() as temp_dir:
      with import_sitegen_module("sitegen.server") as server:
        server.serve(
          Path(temp_dir),
          FakeBuildOptions(),
          host="0.0.0.0",
          port=4321,
          open_browser=True,
          builder_factory=Builder,
          server_factory=FakeHttpServer,
          browser_opener=opened.append,
          stdout=io.StringIO(),
        )

    self.assertEqual(opened, ["http://127.0.0.1:4321"])


if __name__ == "__main__":
  unittest.main()
