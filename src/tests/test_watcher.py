import importlib
import io
import json
import sys
import tempfile
import time
import types
import unittest
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from threading import Event, Thread


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


class TestPollingWatcher(unittest.TestCase):
  def test_snapshot_sources_tracks_only_build_inputs(self) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
      project_root = Path(temp_dir)
      tracked_paths = [
        project_root / "config.json",
        project_root / "content" / "post" / "index.md",
        project_root / "templates" / "blog.html",
        project_root / "static" / "index.css",
      ]
      ignored_paths = [
        project_root / "docs" / "index.html",
        project_root / "README.md",
      ]
      for path in tracked_paths + ignored_paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(path.name)

      with import_sitegen_module("sitegen.server") as server:
        snapshot = server.snapshot_sources(project_root)

    self.assertEqual(set(snapshot), set(tracked_paths))
    self.assertTrue(all(isinstance(mtime, int) for mtime in snapshot.values()))

  def test_snapshot_sources_uses_configured_input_directories(self) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
      project_root = Path(temp_dir)
      project_root.joinpath("config.json").write_text(
        json.dumps(
          {
            "site_url": "https://example.com",
            "email": "hello@example.com",
            "social_image": "/social.png",
            "content_dir": "articles",
            "template_dir": "views",
            "static_dir": "assets",
          }
        )
      )
      configured_paths = [
        project_root / "articles" / "post.md",
        project_root / "views" / "page.html",
        project_root / "assets" / "site.css",
      ]
      default_path = project_root / "content" / "ignored.md"
      for path in configured_paths + [default_path]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(path.name)

      with import_sitegen_module("sitegen.server") as server:
        snapshot = server.snapshot_sources(project_root)

    self.assertEqual(
      set(snapshot),
      {project_root / "config.json", *configured_paths},
    )

  def test_polling_watcher_debounces_and_coalesces_changes(self) -> None:
    state = {"snapshot": {Path("content/post.md"): 1}}
    rebuilds: list[tuple[Path, ...]] = []

    def snapshotter(_: Path) -> dict[Path, int]:
      return dict(state["snapshot"])

    with import_sitegen_module("sitegen.server") as server:
      watcher = server.PollingWatcher(
        Path("/project"),
        rebuilds.append,
        debounce_seconds=0.2,
        snapshotter=snapshotter,
      )

      state["snapshot"] = {Path("content/post.md"): 2}
      watcher.poll(now=1.0)
      state["snapshot"] = {Path("content/post.md"): 3}
      watcher.poll(now=1.1)
      watcher.poll(now=1.29)
      watcher.poll(now=1.31)

    self.assertEqual(rebuilds, [(Path("content/post.md"),)])

  def test_polling_watcher_survives_failure_and_rebuilds_next_change(self) -> None:
    state = {"snapshot": {Path("templates/blog.html"): 1}}
    attempts = 0

    def snapshotter(_: Path) -> dict[Path, int]:
      return dict(state["snapshot"])

    def rebuild(_changed_paths: tuple[Path, ...]) -> None:
      nonlocal attempts
      attempts += 1
      if attempts == 1:
        raise RuntimeError("bad template")

    with tempfile.TemporaryDirectory() as temp_dir:
      output = Path(temp_dir) / "docs" / "index.html"
      output.parent.mkdir(parents=True)
      output.write_text("last valid output")

      with import_sitegen_module("sitegen.server") as server:
        watcher = server.PollingWatcher(
          Path(temp_dir),
          rebuild,
          debounce_seconds=0.1,
          snapshotter=snapshotter,
          stderr=io.StringIO(),
        )

        state["snapshot"] = {Path("templates/blog.html"): 2}
        watcher.poll(now=1.0)
        watcher.poll(now=1.11)
        self.assertEqual(output.read_text(), "last valid output")

        state["snapshot"] = {Path("templates/blog.html"): 3}
        watcher.poll(now=2.0)
        watcher.poll(now=2.11)

    self.assertEqual(attempts, 2)

  def test_stop_waits_for_an_active_rebuild(self) -> None:
    state = {"snapshot": {Path("content/post.md"): 1}}
    rebuild_started = Event()
    release_rebuild = Event()

    def snapshotter(_: Path) -> dict[Path, int]:
      return dict(state["snapshot"])

    def rebuild(_changed_paths: tuple[Path, ...]) -> None:
      rebuild_started.set()
      release_rebuild.wait()

    with import_sitegen_module("sitegen.server") as server:
      watcher = server.PollingWatcher(
        Path("/project"),
        rebuild,
        debounce_seconds=0,
        poll_interval=0.01,
        snapshotter=snapshotter,
      )
      watcher.start()
      state["snapshot"] = {Path("content/post.md"): 2}
      self.assertTrue(rebuild_started.wait(timeout=1))

      releaser = Thread(
        target=lambda: (time.sleep(1.1), release_rebuild.set()),
        daemon=True,
      )
      releaser.start()
      started_at = time.monotonic()
      watcher.stop()
      elapsed = time.monotonic() - started_at
      releaser.join()

    self.assertGreaterEqual(elapsed, 1.05)
    self.assertFalse(watcher._thread.is_alive())


if __name__ == "__main__":
  unittest.main()
