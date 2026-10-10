import xml.etree.ElementTree as ET
from datetime import UTC, datetime, time
from email.utils import format_datetime

from sitegen.content import ContentIndex

SITEMAP_NAMESPACE = "http://www.sitemaps.org/schemas/sitemap/0.9"


def render_rss(index: ContentIndex, site_url: str) -> str:
  normalized_site_url = site_url.rstrip("/")
  rss = ET.Element("rss", {"version": "2.0"})
  channel = ET.SubElement(rss, "channel")
  ET.SubElement(channel, "title").text = "sλrthak // writing"
  ET.SubElement(channel, "link").text = normalized_site_url
  ET.SubElement(channel, "description").text = (
    "notes on inference systems, high-performance computing, distributed "
    "systems, and whatever i'm building next."
  )
  ET.SubElement(channel, "language").text = "en-us"
  published = [post for post in index.posts if not post.draft]
  if published:
    latest = max(post.updated or post.date for post in published)
    ET.SubElement(channel, "lastBuildDate").text = _rss_date(latest)

  for post in published:
    item = ET.SubElement(channel, "item")
    ET.SubElement(item, "title").text = post.title
    ET.SubElement(item, "link").text = post.canonical_url
    ET.SubElement(item, "guid", {"isPermaLink": "true"}).text = post.canonical_url
    ET.SubElement(item, "pubDate").text = _rss_date(post.date)
    ET.SubElement(item, "description").text = post.description

  return _serialize_xml(rss)


def render_sitemap(index: ContentIndex, site_url: str) -> str:
  normalized_site_url = site_url.rstrip("/")
  ET.register_namespace("", SITEMAP_NAMESPACE)
  root = ET.Element(f"{{{SITEMAP_NAMESPACE}}}urlset")
  entries: list[tuple[str, str | None]] = []
  seen: set[str] = set()

  for page in index.pages:
    if page.noindex:
      continue
    modified = page.updated or page.date
    _append_entry(entries, seen, page.canonical_url, modified.isoformat())
  for pagination in index.pagination:
    if pagination.page == 1:
      continue
    modified = max(
      (post.updated or post.date for post in pagination.items), default=None
    )
    _append_entry(
      entries,
      seen,
      f"{normalized_site_url}{pagination.route}",
      modified.isoformat() if modified else None,
    )
  for tag in index.tags:
    modified = max((post.updated or post.date for post in tag.items), default=None)
    _append_entry(
      entries,
      seen,
      f"{normalized_site_url}{tag.route}",
      modified.isoformat() if modified else None,
    )

  for location, last_modified in entries:
    url = ET.SubElement(root, f"{{{SITEMAP_NAMESPACE}}}url")
    ET.SubElement(url, f"{{{SITEMAP_NAMESPACE}}}loc").text = location
    if last_modified:
      ET.SubElement(url, f"{{{SITEMAP_NAMESPACE}}}lastmod").text = last_modified
  return _serialize_xml(root)


def _append_entry(
  entries: list[tuple[str, str | None]],
  seen: set[str],
  location: str,
  last_modified: str | None,
) -> None:
  if location in seen:
    return
  seen.add(location)
  entries.append((location, last_modified))


def _rss_date(value) -> str:
  timestamp = datetime.combine(value, time.min, tzinfo=UTC)
  return format_datetime(timestamp)


def _serialize_xml(root: ET.Element) -> str:
  ET.indent(root, space="  ")
  return ET.tostring(root, encoding="unicode", xml_declaration=True) + "\n"
