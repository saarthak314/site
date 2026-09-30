import re
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlsplit

import yaml

from sitegen.models import (
  ContentError,
  ExperienceItem,
  PageMetadata,
  ParsedDocument,
  ProjectItem,
)

LEGACY_DELIMITER = re.compile(r"(?m)^-----[ \t]*$")
YAML_DELIMITER = re.compile(r"(?m)^---[ \t]*$")
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")


def parse_document(path: Path) -> ParsedDocument:
  try:
    text = path.read_text(encoding="utf-8")
  except OSError as exc:
    raise ContentError(f"{path}: unable to read content: {exc}") from exc

  header, body = _split_front_matter(path, text)
  try:
    raw = yaml.safe_load(header) or {}
  except yaml.YAMLError as exc:
    raise ContentError(f"{path}: invalid YAML metadata: {exc}") from exc
  if not isinstance(raw, dict):
    raise ContentError(f"{path}: metadata must be a mapping")

  title = _required_string(path, raw, "title")
  published = _date_value(path, raw.get("date"), "date", required=True)
  updated = _date_value(path, raw.get("updated"), "updated", required=False)
  draft = raw.get("draft", False)
  if not isinstance(draft, bool):
    raise ContentError(f"{path}: draft must be true or false")

  slug = _optional_string(path, raw, "slug")
  if slug and not SLUG_PATTERN.fullmatch(slug):
    raise ContentError(
      f"{path}: slug must contain lowercase letters, digits, hyphens, or underscores"
    )

  permalink = _optional_string(path, raw, "permalink")
  if permalink:
    if not permalink.startswith("/") or not permalink.endswith("/"):
      raise ContentError(f"{path}: permalink must start and end with /")
    if ".." in permalink or "//" in permalink or "?" in permalink or "#" in permalink:
      raise ContentError(f"{path}: permalink contains an invalid path segment")

  tags = _tags_value(path, raw.get("tags"))
  aliases = _aliases_value(path, raw.get("aliases"))
  noindex = raw.get("noindex", False)
  if not isinstance(noindex, bool):
    raise ContentError(f"{path}: noindex must be true or false")
  metadata = PageMetadata(
    title=title,
    date=published,
    updated=updated,
    draft=draft,
    slug=slug,
    permalink=permalink,
    description=_optional_string(path, raw, "description"),
    social_image=_optional_string(path, raw, "social_image"),
    tags=tags,
    template=_optional_string(path, raw, "template"),
    aliases=aliases,
    noindex=noindex,
    experience=_experience_value(path, raw.get("experience")),
    projects=_projects_value(path, raw.get("projects")),
  )
  return ParsedDocument(metadata=metadata, body=body)


def _split_front_matter(path: Path, text: str) -> tuple[str, str]:
  if text.startswith("---\n") or text.startswith("---\r\n"):
    matches = list(YAML_DELIMITER.finditer(text))
    if len(matches) < 2:
      raise ContentError(f"{path}: unclosed YAML front matter")
    header = text[matches[0].end() : matches[1].start()].lstrip("\r\n")
    body = _remove_one_line_ending(text[matches[1].end() :])
    return header, body

  match = LEGACY_DELIMITER.search(text)
  if not match:
    raise ContentError(f"{path}: missing front matter delimiter")
  header = text[: match.start()].rstrip("\r\n")
  body = _remove_one_line_ending(text[match.end() :])
  return header, body


def _remove_one_line_ending(text: str) -> str:
  if text.startswith("\r\n"):
    return text[2:]
  if text.startswith("\n") or text.startswith("\r"):
    return text[1:]
  return text


def _required_string(path: Path, raw: dict, key: str) -> str:
  value = raw.get(key)
  if not isinstance(value, str) or not value.strip():
    raise ContentError(f"{path}: missing required {key}")
  return value.strip()


def _optional_string(path: Path, raw: dict, key: str) -> str | None:
  value = raw.get(key)
  if value is None:
    return None
  if not isinstance(value, str) or not value.strip():
    raise ContentError(f"{path}: {key} must be a non-empty string")
  return value.strip()


def _date_value(path: Path, value: object, key: str, *, required: bool) -> date | None:
  if value is None:
    if required:
      raise ContentError(f"{path}: missing required {key}")
    return None
  if isinstance(value, datetime):
    return value.date()
  if isinstance(value, date):
    return value
  if isinstance(value, str):
    try:
      return date.fromisoformat(value)
    except ValueError as exc:
      raise ContentError(f"{path}: invalid {key}: expected YYYY-MM-DD") from exc
  raise ContentError(f"{path}: invalid {key}: expected YYYY-MM-DD")


def _tags_value(path: Path, value: object) -> tuple[str, ...]:
  if value in (None, ""):
    return ()
  if isinstance(value, str):
    candidates = value.split(",")
  elif isinstance(value, list):
    candidates = value
  else:
    raise ContentError(f"{path}: tags must be a list or comma-separated string")

  tags: list[str] = []
  for candidate in candidates:
    if not isinstance(candidate, str) or not candidate.strip():
      raise ContentError(f"{path}: every tag must be a non-empty string")
    tag = candidate.strip()
    if tag not in tags:
      tags.append(tag)
  return tuple(tags)


def _aliases_value(path: Path, value: object) -> tuple[str, ...]:
  if value in (None, ""):
    return ()
  if not isinstance(value, list):
    raise ContentError(f"{path}: aliases must be a list")

  aliases: list[str] = []
  for candidate in value:
    if not isinstance(candidate, str) or not candidate.strip():
      raise ContentError(f"{path}: every alias must be a non-empty string")
    alias = candidate.strip()
    if not alias.startswith("/") or not alias.endswith("/"):
      raise ContentError(f"{path}: alias must start and end with /")
    if ".." in alias or "//" in alias or "?" in alias or "#" in alias:
      raise ContentError(f"{path}: alias contains an invalid path segment")
    if alias not in aliases:
      aliases.append(alias)
  return tuple(aliases)


def _experience_value(path: Path, value: object) -> tuple[ExperienceItem, ...]:
  if value is None:
    return ()
  if not isinstance(value, list):
    raise ContentError(f"{path}: experience must be a list")

  items: list[ExperienceItem] = []
  for index, candidate in enumerate(value, start=1):
    label = f"experience item {index}"
    if not isinstance(candidate, dict):
      raise ContentError(f"{path}: {label} must be a mapping")
    role = _item_string(path, candidate, "role", label, required=True)
    company = _item_string(path, candidate, "company", label, required=False)
    company_url = _item_string(
      path,
      candidate,
      "company_url",
      label,
      required=False,
    )
    period = _item_string(path, candidate, "period", label, required=True)
    highlights = (
      _string_list(path, candidate["highlights"], f"{label} highlights")
      if "highlights" in candidate
      else ()
    )
    if company_url:
      _validate_http_url(path, company_url, f"{label} company_url")
      if not company:
        raise ContentError(f"{path}: {label} company_url requires company")
    items.append(
      ExperienceItem(
        role=role,
        company=company,
        company_url=company_url,
        period=period,
        highlights=highlights,
      )
    )
  return tuple(items)


def _projects_value(path: Path, value: object) -> tuple[ProjectItem, ...]:
  if value is None:
    return ()
  if not isinstance(value, list):
    raise ContentError(f"{path}: projects must be a list")

  items: list[ProjectItem] = []
  for index, candidate in enumerate(value, start=1):
    label = f"project item {index}"
    if not isinstance(candidate, dict):
      raise ContentError(f"{path}: {label} must be a mapping")
    name = _item_string(path, candidate, "name", label, required=True)
    url = _item_string(path, candidate, "url", label, required=False)
    description = _item_string(
      path,
      candidate,
      "description",
      label,
      required=True,
    )
    if url:
      _validate_http_url(path, url, f"{label} url")
    tech = _string_list(path, candidate.get("tech"), f"{label} tech")
    items.append(
      ProjectItem(
        name=name,
        url=url,
        description=description,
        tech=tech,
      )
    )
  return tuple(items)


def _item_string(
  path: Path,
  item: dict,
  key: str,
  label: str,
  *,
  required: bool,
) -> str | None:
  value = item.get(key)
  if value is None and not required:
    return None
  if not isinstance(value, str) or not value.strip():
    requirement = "missing required" if required else "invalid"
    raise ContentError(f"{path}: {label} has {requirement} {key}")
  return value.strip()


def _string_list(path: Path, value: object, label: str) -> tuple[str, ...]:
  if not isinstance(value, list) or not value:
    raise ContentError(f"{path}: {label} must be a non-empty list")
  items: list[str] = []
  for candidate in value:
    if not isinstance(candidate, str) or not candidate.strip():
      raise ContentError(f"{path}: every {label} value must be a non-empty string")
    normalized = candidate.strip()
    if normalized not in items:
      items.append(normalized)
  return tuple(items)


def _validate_http_url(path: Path, value: str, label: str) -> None:
  parsed = urlsplit(value)
  if parsed.scheme not in {"http", "https"} or not parsed.netloc:
    raise ContentError(f"{path}: {label} must be an absolute http(s) URL")
