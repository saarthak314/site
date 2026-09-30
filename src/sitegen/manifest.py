import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

MANIFEST_NAME = ".sitegen-manifest.json"
MANIFEST_VERSION = 1


@dataclass(frozen=True)
class BuildManifest:
  version: int = MANIFEST_VERSION
  entries: dict[str, str] = field(default_factory=dict)

  @classmethod
  def load(cls, root: Path) -> "BuildManifest":
    path = root / MANIFEST_NAME
    try:
      data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
      return cls()
    if not isinstance(data, dict) or data.get("version") != MANIFEST_VERSION:
      return cls()
    entries = data.get("entries")
    if not isinstance(entries, dict) or not all(
      isinstance(key, str) and isinstance(value, str) for key, value in entries.items()
    ):
      return cls()
    return cls(entries=dict(entries))

  def write(self, root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    path = root / MANIFEST_NAME
    payload = {"version": self.version, "entries": self.entries}
    path.write_text(
      json.dumps(payload, indent=2, sort_keys=True) + "\n",
      encoding="utf-8",
    )


def digest_paths(paths: Iterable[Path], root: Path) -> str:
  digest = hashlib.sha256()
  for path in sorted(paths, key=lambda item: item.as_posix()):
    try:
      relative = path.relative_to(root)
    except ValueError:
      relative = path
    digest.update(relative.as_posix().encode("utf-8"))
    if path.is_file():
      digest.update(path.read_bytes())
    else:
      digest.update(b"<missing>")
  return digest.hexdigest()
