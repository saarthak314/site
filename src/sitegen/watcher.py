from __future__ import annotations

import sys
import time
from collections.abc import Callable
from pathlib import Path
from threading import Event, Thread, current_thread
from typing import TextIO

from .config import SiteConfig

SOURCE_INPUTS = ("config.json", "content", "templates", "static")


def _source_inputs(project_root: Path) -> tuple[Path, ...]:
  defaults = tuple(project_root / name for name in SOURCE_INPUTS)
  try:
    config = SiteConfig.load(project_root)
  except (OSError, ValueError):
    return defaults
  return (
    project_root / "config.json",
    config.content_dir,
    config.template_dir,
    config.static_dir,
  )


def snapshot_sources(project_root: Path) -> dict[Path, int]:
  root = Path(project_root)
  snapshot: dict[Path, int] = {}

  for path in _source_inputs(root):
    if path.is_file():
      try:
        snapshot[path] = path.stat().st_mtime_ns
      except FileNotFoundError:
        pass
      continue

    if not path.is_dir():
      continue

    for child in sorted(path.rglob("*")):
      if not child.is_file():
        continue
      try:
        snapshot[child] = child.stat().st_mtime_ns
      except FileNotFoundError:
        pass

  return snapshot


class PollingWatcher:
  def __init__(
    self,
    project_root: Path,
    on_change: Callable[[tuple[Path, ...]], None],
    *,
    debounce_seconds: float = 0.25,
    poll_interval: float = 0.1,
    snapshotter: Callable[[Path], dict[Path, int]] = snapshot_sources,
    initial_snapshot: dict[Path, int] | None = None,
    stderr: TextIO | None = None,
  ) -> None:
    self.project_root = Path(project_root)
    self.on_change = on_change
    self.debounce_seconds = debounce_seconds
    self.poll_interval = poll_interval
    self.snapshotter = snapshotter
    self.stderr = stderr or sys.stderr
    self._snapshot = (
      dict(initial_snapshot)
      if initial_snapshot is not None
      else self.snapshotter(self.project_root)
    )
    self._changed_at: float | None = None
    self._changed_paths: set[Path] = set()
    self._stop_event = Event()
    self._thread: Thread | None = None

  def poll(self, *, now: float | None = None) -> bool:
    current_time = time.monotonic() if now is None else now
    current_snapshot = self.snapshotter(self.project_root)

    if current_snapshot != self._snapshot:
      paths = set(current_snapshot) | set(self._snapshot)
      self._changed_paths.update(
        path for path in paths if current_snapshot.get(path) != self._snapshot.get(path)
      )
      self._snapshot = current_snapshot
      self._changed_at = current_time
      return False

    if self._changed_at is None:
      return False
    if current_time - self._changed_at < self.debounce_seconds:
      return False

    self._changed_at = None
    changed_paths = tuple(sorted(self._changed_paths, key=str))
    self._changed_paths.clear()
    try:
      self.on_change(changed_paths)
    except Exception as error:
      print(f"rebuild failed: {error}", file=self.stderr)
    return True

  def run(self) -> None:
    while not self._stop_event.wait(self.poll_interval):
      self.poll()

  def start(self) -> None:
    if self._thread is not None and self._thread.is_alive():
      return
    self._stop_event.clear()
    self._thread = Thread(target=self.run, name="sitegen-watch", daemon=True)
    self._thread.start()

  def stop(self) -> None:
    self._stop_event.set()
    if self._thread is None or self._thread is current_thread():
      return
    self._thread.join()
