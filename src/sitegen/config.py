import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from sitegen.models import ContentError


@dataclass(frozen=True)
class SiteConfig:
  project_root: Path
  site_url: str
  email: str
  social_image: str
  author_name: str
  twitter_handle: str
  posts_per_page: int
  content_dir: Path
  template_dir: Path
  static_dir: Path
  output_dir: Path

  @classmethod
  def load(cls, project_root: Path) -> "SiteConfig":
    root = project_root.absolute()
    config_path = root / "config.json"
    try:
      raw = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
      raise ContentError(f"{config_path}: configuration file not found") from exc
    except json.JSONDecodeError as exc:
      raise ContentError(f"{config_path}: invalid JSON: {exc.msg}") from exc

    if not isinstance(raw, dict):
      raise ContentError(f"{config_path}: configuration must be an object")

    site_url = _required_string(raw, "site_url", config_path).rstrip("/")
    parsed_url = urlparse(site_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
      raise ContentError(f"{config_path}: site_url must be an absolute http(s) URL")

    email = _required_string(raw, "email", config_path)
    social_image = _required_string(raw, "social_image", config_path)
    author_name = raw.get("author_name", "Sarthak Tomar")
    twitter_handle = raw.get("twitter_handle", "@sarthak2143")
    if not isinstance(author_name, str) or not author_name.strip():
      raise ContentError(f"{config_path}: author_name must be a non-empty string")
    if not isinstance(twitter_handle, str) or not twitter_handle.startswith("@"):
      raise ContentError(f"{config_path}: twitter_handle must start with @")
    posts_per_page = raw.get("posts_per_page", 10)
    if not isinstance(posts_per_page, int) or isinstance(posts_per_page, bool):
      raise ContentError(f"{config_path}: posts_per_page must be an integer")
    if posts_per_page < 1:
      raise ContentError(f"{config_path}: posts_per_page must be greater than zero")

    return cls(
      project_root=root,
      site_url=site_url,
      email=email,
      social_image=social_image,
      author_name=author_name.strip(),
      twitter_handle=twitter_handle,
      posts_per_page=posts_per_page,
      content_dir=_path_setting(raw, "content_dir", root / "content", root),
      template_dir=_path_setting(raw, "template_dir", root / "templates", root),
      static_dir=_path_setting(raw, "static_dir", root / "static", root),
      output_dir=_path_setting(raw, "output_dir", root / "docs", root),
    )


def _required_string(raw: dict, key: str, path: Path) -> str:
  value = raw.get(key)
  if not isinstance(value, str) or not value.strip():
    raise ContentError(f"{path}: missing required {key}")
  return value.strip()


def _path_setting(raw: dict, key: str, default: Path, root: Path) -> Path:
  value = raw.get(key)
  if value is None:
    return default
  if not isinstance(value, str) or not value.strip():
    raise ContentError(f"{root / 'config.json'}: {key} must be a path string")
  path = Path(value)
  return path if path.is_absolute() else root / path
