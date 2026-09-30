from __future__ import annotations

import sys
import time
import webbrowser
from collections.abc import Callable
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import TextIO

from .build import BuildOptions, SiteBuilder
from .http_server import ServedDirectory, SiteRequestHandler
from .live_reload import LiveReloadState
from .watcher import PollingWatcher, snapshot_sources


def serve(
  project_root: Path,
  options: BuildOptions,
  *,
  host: str = "127.0.0.1",
  port: int = 8888,
  watch: bool = False,
  live_reload: bool = False,
  open_browser: bool = False,
  builder_factory: Callable[[Path], SiteBuilder] = SiteBuilder,
  server_factory: Callable[..., ThreadingHTTPServer] = ThreadingHTTPServer,
  watcher_factory: Callable[..., PollingWatcher] = PollingWatcher,
  handler_factory: type[SimpleHTTPRequestHandler] = SiteRequestHandler,
  reload_state_factory: Callable[[], LiveReloadState] = LiveReloadState,
  browser_opener: Callable[[str], object] = webbrowser.open,
  clock: Callable[[], float] = time.perf_counter,
  stdout: TextIO | None = None,
  stderr: TextIO | None = None,
) -> int:
  output = stdout or sys.stdout
  errors = stderr or sys.stderr
  root = Path(project_root)
  initial_snapshot = snapshot_sources(root) if watch else None
  builder = builder_factory(root)
  report = builder.build(options)
  output_dir = Path(report.output_dir)
  served_directory = ServedDirectory(output_dir)
  reload_state = reload_state_factory() if live_reload else None
  handler = partial(
    handler_factory,
    directory=served_directory,
    reload_state=reload_state,
  )
  watcher: PollingWatcher | None = None

  def rebuild(changed_paths: tuple[Path, ...] = ()) -> None:
    started_at = clock()
    displayed_paths: list[str] = []
    for path in changed_paths:
      try:
        displayed_paths.append(path.relative_to(root).as_posix())
      except ValueError:
        displayed_paths.append(path.as_posix())
    changed = ", ".join(displayed_paths) or "source change"
    try:
      rebuilt = builder.build(options)
    except Exception as error:
      elapsed_ms = round((clock() - started_at) * 1000)
      message = f"rebuild failed in {elapsed_ms}ms [{changed}]: {error}"
      print(message, file=errors)
      if reload_state is not None:
        reload_state.publish("build-error", message)
      return
    elapsed_ms = round((clock() - started_at) * 1000)
    served_directory.update(Path(rebuilt.output_dir))
    print(
      f"rebuilt {rebuilt.rendered} page(s), reused {rebuilt.reused} "
      f"in {elapsed_ms}ms [{changed}]",
      file=output,
    )
    if reload_state is not None:
      event_kind = (
        "css"
        if changed_paths
        and all(path.suffix.lower() == ".css" for path in changed_paths)
        else "reload"
      )
      reload_state.publish(event_kind, changed)

  with server_factory((host, port), handler) as httpd:
    if watch:
      watcher = watcher_factory(
        root,
        rebuild,
        initial_snapshot=initial_snapshot,
      )
      watcher.start()

    print(f"serving {output_dir} at http://{host}:{port}", file=output)
    if open_browser:
      browser_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
      browser_opener(f"http://{browser_host}:{port}")
    try:
      httpd.serve_forever()
    except KeyboardInterrupt:
      pass
    finally:
      if watcher is not None:
        watcher.stop()

  return 0


__all__ = [
  "PollingWatcher",
  "ServedDirectory",
  "SiteRequestHandler",
  "serve",
  "snapshot_sources",
]
