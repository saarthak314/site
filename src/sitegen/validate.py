from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import SplitResult, unquote, urlsplit
from xml.etree import ElementTree


@dataclass(frozen=True, slots=True)
class ValidationIssue:
  path: Path
  message: str

  @property
  def source_path(self) -> Path:
    return self.path

  def format(self) -> str:
    return f"{self.path}: {self.message}"


class _HtmlDocument(HTMLParser):
  def __init__(self) -> None:
    super().__init__(convert_charrefs=True)
    self.canonical_hrefs: list[str] = []
    self.hrefs: list[str] = []
    self.srcs: list[str] = []
    self.ids: set[str] = set()

  def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
    attributes = {name.lower(): value for name, value in attrs}

    element_id = attributes.get("id")
    if element_id:
      self.ids.add(element_id)

    href = attributes.get("href")
    if href is not None:
      self.hrefs.append(href)

    if tag.lower() == "link" and href is not None:
      rel = attributes.get("rel") or ""
      if "canonical" in {value.lower() for value in rel.split()}:
        self.canonical_hrefs.append(href)

    src = attributes.get("src")
    if src is not None:
      self.srcs.append(src)


class SiteValidator:
  def validate(self, root: Path) -> list[ValidationIssue]:
    root = Path(root)
    if not root.is_dir():
      return [ValidationIssue(root, "output root does not exist or is not a directory")]

    issues: list[ValidationIssue] = []
    html_documents: dict[Path, _HtmlDocument] = {}
    xml_contents: dict[Path, str] = {}

    for path in sorted(root.rglob("*")):
      if not path.is_file() or path.suffix.lower() not in {".html", ".xml"}:
        continue

      try:
        content = path.read_text(encoding="utf-8")
      except (OSError, UnicodeError) as error:
        issues.append(ValidationIssue(path, f"unable to read output: {error}"))
        continue

      issues.extend(self._template_marker_issues(path, content))

      if path.suffix.lower() == ".html":
        document = _HtmlDocument()
        document.feed(content)
        document.close()
        html_documents[path.resolve()] = document
        issues.extend(self._canonical_issues(path, document))
      else:
        xml_contents[path] = content

    root_resolved = root.resolve()
    site_origins = {
      self._origin(parsed)
      for document in html_documents.values()
      for href in document.canonical_hrefs
      if (parsed := self._parse_reference(href)) is not None
      and self._is_absolute_http_url(href)
    }
    for resolved_path, document in html_documents.items():
      source_path = self._display_path(root, root_resolved, resolved_path)
      issues.extend(
        self._href_issues(
          root_resolved,
          source_path,
          resolved_path,
          document,
          html_documents,
          site_origins,
        )
      )
      issues.extend(
        self._src_issues(root_resolved, source_path, resolved_path, document)
      )

    for path, content in xml_contents.items():
      issues.extend(self._xml_issues(path, content))

    return sorted(issues, key=lambda issue: (str(issue.path), issue.message))

  def _template_marker_issues(self, path: Path, content: str) -> list[ValidationIssue]:
    issues = []
    for marker in ("{{", "{%"):
      if marker in content:
        issues.append(ValidationIssue(path, f'unresolved template marker "{marker}"'))
    return issues

  def _canonical_issues(
    self, path: Path, document: _HtmlDocument
  ) -> list[ValidationIssue]:
    if not document.canonical_hrefs:
      return [ValidationIssue(path, "missing canonical link")]

    return [
      ValidationIssue(path, f'non-absolute canonical link: "{href}"')
      for href in document.canonical_hrefs
      if not self._is_absolute_http_url(href)
    ]

  def _href_issues(
    self,
    root: Path,
    source_path: Path,
    resolved_source: Path,
    document: _HtmlDocument,
    html_documents: dict[Path, _HtmlDocument],
    site_origins: set[tuple[str, str]],
  ) -> list[ValidationIssue]:
    issues = []
    for href in document.hrefs:
      parsed = self._parse_reference(href)
      if parsed is None or self._is_ignored_href(parsed, site_origins):
        continue

      target = self._resolve_target(
        root, resolved_source, parsed.path, allow_directory_route=True
      )
      if target is None:
        issues.append(
          ValidationIssue(source_path, f'broken internal href target: "{href}"')
        )
        continue

      fragment = unquote(parsed.fragment)
      if not fragment or target.suffix.lower() != ".html":
        continue

      target_document = html_documents.get(target.resolve())
      if target_document is None or fragment not in target_document.ids:
        issues.append(
          ValidationIssue(source_path, f'missing fragment target in href: "{href}"')
        )

    return issues

  def _src_issues(
    self,
    root: Path,
    source_path: Path,
    resolved_source: Path,
    document: _HtmlDocument,
  ) -> list[ValidationIssue]:
    issues = []
    for src in document.srcs:
      if not src.strip():
        issues.append(ValidationIssue(source_path, 'missing local src asset: ""'))
        continue

      parsed = self._parse_reference(src)
      if parsed is None or self._is_external_reference(parsed):
        continue

      target = self._resolve_target(
        root, resolved_source, parsed.path, allow_directory_route=False
      )
      if target is None:
        issues.append(ValidationIssue(source_path, f'missing local src asset: "{src}"'))
    return issues

  def _xml_issues(self, path: Path, content: str) -> list[ValidationIssue]:
    name = path.name.lower()
    kind = "RSS XML" if name == "feed.xml" else "sitemap XML"
    if name not in {"feed.xml", "sitemap.xml"}:
      kind = "XML"

    try:
      root = ElementTree.fromstring(content)
    except ElementTree.ParseError as error:
      return [ValidationIssue(path, f"{kind} is not parseable: {error}")]

    if name != "sitemap.xml":
      return []

    issues = []
    for element in root.iter():
      if self._local_name(element.tag) != "loc":
        continue
      value = (element.text or "").strip()
      if not self._is_absolute_http_url(value):
        display_value = value or "<empty>"
        issues.append(
          ValidationIssue(
            path,
            f'non-absolute sitemap loc: "{display_value}"',
          )
        )
    return issues

  def _resolve_target(
    self,
    root: Path,
    source: Path,
    reference_path: str,
    *,
    allow_directory_route: bool,
  ) -> Path | None:
    decoded_path = unquote(reference_path)
    if decoded_path.startswith("/"):
      target = root / decoded_path.lstrip("/")
    elif decoded_path:
      target = source.parent / decoded_path
    else:
      target = source

    target = target.resolve()
    try:
      target.relative_to(root)
    except ValueError:
      return None

    candidates = [target]
    if allow_directory_route and (
      decoded_path.endswith("/") or target.is_dir() or not target.suffix
    ):
      candidates.append(target / "index.html")

    for candidate in candidates:
      if candidate.is_file():
        return candidate
    return None

  def _parse_reference(self, value: str) -> SplitResult | None:
    try:
      return urlsplit(value.strip())
    except ValueError:
      return None

  def _is_external_reference(self, parsed: SplitResult) -> bool:
    return bool(parsed.netloc or parsed.scheme)

  def _is_ignored_href(
    self, parsed: SplitResult, site_origins: set[tuple[str, str]]
  ) -> bool:
    if parsed.scheme.lower() in {"http", "https"}:
      return self._origin(parsed) not in site_origins
    return bool(parsed.netloc or parsed.scheme)

  def _origin(self, parsed: SplitResult) -> tuple[str, str]:
    return parsed.scheme.lower(), parsed.netloc.lower()

  def _is_absolute_http_url(self, value: str) -> bool:
    try:
      parsed = urlsplit(value.strip())
    except ValueError:
      return False
    return parsed.scheme.lower() in {"http", "https"} and bool(parsed.netloc)

  def _display_path(self, root: Path, root_resolved: Path, path: Path) -> Path:
    if root == root_resolved:
      return path
    return root / path.relative_to(root_resolved)

  def _local_name(self, tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
