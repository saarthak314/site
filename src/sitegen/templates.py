import re
import unicodedata
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from sitegen.render import TemplateRenderer


def create_environment(template_dir: Path) -> Environment:
  environment = Environment(
    loader=FileSystemLoader(str(template_dir)),
    undefined=StrictUndefined,
    autoescape=select_autoescape(enabled_extensions=("html", "xml")),
  )
  environment.filters.update(
    full_date=_full_date,
    iso_date=_iso_date,
    month_year=_month_year,
    tag_slug=_tag_slug,
  )
  return environment


def _full_date(value: date) -> str:
  return value.strftime("%d %b %Y").lower()


def _iso_date(value: date) -> str:
  return value.isoformat()


def _month_year(value: date) -> str:
  return value.strftime("%b %Y").lower()


def _tag_slug(value: str) -> str:
  normalized = unicodedata.normalize("NFKD", value)
  ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
  return re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")


__all__ = ["TemplateRenderer", "create_environment"]
