from __future__ import annotations

import math
import mimetypes
import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from urllib.parse import unquote, urlsplit

from markdown_it import MarkdownIt
from markdown_it.common.utils import escapeHtml
from markdown_it.renderer import RendererHTML
from markdown_it.rules_inline.state_inline import StateInline
from markdown_it.token import Token
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import TextLexer, get_lexer_by_name
from pygments.util import ClassNotFound

_WORD_RE = re.compile(r"\b[\w']+\b", re.UNICODE)
_CONTROL_RE = re.compile(r"[\x00-\x20\x7f]+")
_DANGEROUS_SCHEMES = {"data", "file", "javascript", "vbscript"}
_GENERIC_LINK_LABELS = {"here", "link", "more", "this"}
_VIDEO_SUFFIXES = (".mp4", ".webm")


@dataclass(frozen=True, slots=True)
class RenderedMarkdown:
  html: str
  description: str
  reading_time: str
  has_math: bool
  has_code: bool
  headings: tuple[tuple[int, str, str], ...] = ()


class MarkdownRenderer:
  def __init__(
    self,
    description_limit: int = 160,
    words_per_minute: int = 200,
    static_dir: Path | None = None,
  ):
    self.description_limit = description_limit
    self.words_per_minute = words_per_minute
    self.static_dir = static_dir.resolve() if static_dir is not None else None
    self._markdown = self._create_markdown()

  def render(self, markdown: str) -> RenderedMarkdown:
    environment: dict[str, object] = {}
    tokens = self._markdown.parse(markdown, environment)
    headings = self._assign_heading_ids(tokens)
    self._label_generic_links(tokens)
    self._add_image_attributes(tokens)
    _mark_image_figures(tokens)

    return RenderedMarkdown(
      html=self._markdown.renderer.render(tokens, self._markdown.options, environment),
      description=self._description(tokens),
      reading_time=self._reading_time(tokens),
      has_math=any(token.type == "mathjax" for token in _walk_tokens(tokens)),
      has_code=any(
        token.type in {"code_block", "code_inline"}
        or (token.type == "fence" and not _is_diagram_fence(token))
        for token in _walk_tokens(tokens)
      ),
      headings=headings,
    )

  def _create_markdown(self) -> MarkdownIt:
    markdown = MarkdownIt(
      "commonmark",
      {
        "html": False,
        "linkify": False,
        "typographer": False,
      },
    ).enable("table")
    markdown.inline.ruler.before("escape", "mathjax", _mathjax_rule)
    markdown.inline.add_terminator_char("$")
    markdown.add_render_rule("mathjax", _render_mathjax)
    markdown.add_render_rule("visually_hidden", _render_visually_hidden)
    markdown.add_render_rule("fence", _render_fence)
    markdown.add_render_rule("image", _render_image)
    markdown.validateLink = _is_safe_link
    return markdown

  def _assign_heading_ids(
    self, tokens: Sequence[Token]
  ) -> tuple[tuple[int, str, str], ...]:
    counts: dict[str, int] = {}
    headings: list[tuple[int, str, str]] = []
    for index, token in enumerate(tokens[:-1]):
      if token.type != "heading_open":
        continue

      inline = tokens[index + 1]
      if inline.type != "inline":
        continue

      text = _normalize_whitespace(_plain_text(inline.children or ()))
      base = _slugify(text)
      counts[base] = counts.get(base, 0) + 1
      suffix = "" if counts[base] == 1 else f"-{counts[base]}"
      heading_id = f"{base}{suffix}"
      token.attrSet("id", heading_id)
      headings.append((int(token.tag[1:]), text, heading_id))
    return tuple(headings)

  def _label_generic_links(self, tokens: Sequence[Token]) -> None:
    for token in tokens:
      children = token.children
      if not children:
        continue

      index = 0
      while index < len(children):
        opening = children[index]
        if opening.type != "link_open":
          index += 1
          continue

        closing_index = next(
          (
            candidate
            for candidate in range(index + 1, len(children))
            if children[candidate].type == "link_close"
          ),
          None,
        )
        if closing_index is None:
          break

        label = _normalize_whitespace(
          _plain_text(children[index + 1 : closing_index])
        ).casefold()
        href = opening.attrGet("href") or ""
        parsed = urlsplit(href)
        hostname = parsed.hostname
        if (
          label in _GENERIC_LINK_LABELS
          and parsed.scheme.lower() in {"http", "https"}
          and hostname
        ):
          hidden = Token("visually_hidden", "span", 0)
          hidden.content = f" at {hostname}"
          children.insert(closing_index, hidden)
          closing_index += 1

        index = closing_index + 1

  def _add_image_attributes(self, tokens: Sequence[Token]) -> None:
    for token in _walk_tokens(tokens):
      if token.type != "image":
        continue
      source = token.attrGet("src") or ""
      if _is_video_source(source):
        token.meta["video"] = True
        if self.static_dir is not None:
          poster = _local_asset_path(self.static_dir, _poster_source(source))
          if poster is not None and poster.is_file():
            token.meta["poster"] = _poster_source(source)
        continue
      token.attrSet("loading", "lazy")
      token.attrSet("decoding", "async")

      if self.static_dir is None:
        continue
      image_path = _local_asset_path(self.static_dir, source)
      if image_path is None or not image_path.is_file():
        continue
      dimensions = image_dimensions(image_path)
      if dimensions is None:
        continue
      width, height = dimensions
      token.attrSet("width", str(width))
      token.attrSet("height", str(height))
      variants = _responsive_variants(image_path, source)
      if variants:
        token.attrSet("srcset", ", ".join([*variants, f"{source} {width}w"]))
        token.attrSet("sizes", "(max-width: 640px) calc(100vw - 40px), 660px")

  def _description(self, tokens: Sequence[Token]) -> str:
    for index, token in enumerate(tokens[:-1]):
      if token.type != "paragraph_open" or token.level != 0:
        continue

      inline = tokens[index + 1]
      if inline.type != "inline":
        continue

      description = _normalize_whitespace(_plain_text(inline.children or ()))
      if description:
        return _truncate(description, self.description_limit)
    return ""

  def _reading_time(self, tokens: Sequence[Token]) -> str:
    words = 0
    for token in _walk_tokens(tokens):
      if token.type not in {"mathjax", "text"}:
        continue
      words += len(_WORD_RE.findall(token.content))

    minutes = max(1, math.ceil(words / self.words_per_minute))
    return f"{minutes} min read"


def _mathjax_rule(state: StateInline, silent: bool) -> bool:
  source = state.src
  start = state.pos
  delimiter = ""
  closing = ""

  if source.startswith("$$", start):
    delimiter, closing = "$$", "$$"
  elif source.startswith(r"\(", start):
    delimiter, closing = r"\(", r"\)"
  elif source.startswith(r"\[", start):
    delimiter, closing = r"\[", r"\]"
  elif source.startswith("$", start):
    delimiter, closing = "$", "$"
    if start + 1 >= state.posMax or source[start + 1].isspace():
      return False
  else:
    return False

  end = _find_unescaped(source, closing, start + len(delimiter), state.posMax)
  if end < 0:
    return False
  if delimiter == "$" and source[end - 1].isspace():
    return False

  state.pos = end + len(closing)
  if not silent:
    token = state.push("mathjax", "", 0)
    token.content = source[start : state.pos]
  return True


def _find_unescaped(source: str, delimiter: str, start: int, limit: int) -> int:
  position = start
  while position < limit:
    position = source.find(delimiter, position, limit)
    if position < 0:
      return -1
    if not _is_escaped(source, position):
      return position
    position += len(delimiter)
  return -1


def _is_escaped(source: str, position: int) -> bool:
  backslashes = 0
  position -= 1
  while position >= 0 and source[position] == "\\":
    backslashes += 1
    position -= 1
  return backslashes % 2 == 1


def _render_mathjax(
  renderer: RendererHTML,
  tokens: Sequence[Token],
  index: int,
  options: dict[str, object],
  environment: dict[str, object],
) -> str:
  del renderer, options, environment
  return escapeHtml(tokens[index].content)


def _render_visually_hidden(
  renderer: RendererHTML,
  tokens: Sequence[Token],
  index: int,
  options: dict[str, object],
  environment: dict[str, object],
) -> str:
  del renderer, options, environment
  return f'<span class="visually-hidden">{escapeHtml(tokens[index].content)}</span>'


def _render_fence(
  renderer: RendererHTML,
  tokens: Sequence[Token],
  index: int,
  options: dict[str, object],
  environment: dict[str, object],
) -> str:
  del renderer, options, environment
  token = tokens[index]
  if _is_diagram_fence(token):
    label = token.info.strip()[len("diagram") :].strip() or "diagram"
    content = token.content.rstrip("\n")
    columns = max((len(line) for line in content.splitlines()), default=1)
    drawing = escapeHtml(content)
    return (
      '<figure class="figure figure--diagram">'
      f'<pre role="img" aria-label="{escapeHtml(label)}" style="--cols: {columns}">'
      f"{drawing}</pre></figure>\n"
    )
  language = token.info.strip().split(maxsplit=1)[0] if token.info.strip() else "text"
  safe_language = re.sub(r"[^a-zA-Z0-9_+-]", "", language) or "text"
  try:
    lexer = get_lexer_by_name(safe_language)
  except ClassNotFound:
    lexer = TextLexer()
  highlighted = highlight(token.content, lexer, HtmlFormatter(nowrap=True))
  return (
    f'<pre><code class="language-{escapeHtml(safe_language)}">'
    f"{highlighted}</code></pre>\n"
  )


def _is_diagram_fence(token: Token) -> bool:
  return token.type == "fence" and token.info.strip().split(maxsplit=1)[:1] == [
    "diagram"
  ]


def _mark_image_figures(tokens: Sequence[Token]) -> None:
  """Hide the paragraph around a lone image so it can render as a figure."""
  for index, token in enumerate(tokens[:-2]):
    if token.type != "paragraph_open" or tokens[index + 2].type != "paragraph_close":
      continue
    inline = tokens[index + 1]
    if inline.type != "inline":
      continue
    content = [
      child
      for child in inline.children or ()
      if not (child.type in {"text", "softbreak"} and not child.content.strip())
    ]
    if len(content) != 1 or content[0].type != "image":
      continue
    token.hidden = True
    tokens[index + 2].hidden = True
    content[0].meta["figure"] = True


def _render_image(
  renderer: RendererHTML,
  tokens: Sequence[Token],
  index: int,
  options: dict[str, object],
  environment: dict[str, object],
) -> str:
  token = tokens[index]
  if token.meta.get("video"):
    media = _render_video(renderer, token)
    figure_class = "figure figure--video"
  else:
    media = RendererHTML.image(renderer, tokens, index, options, environment)
    figure_class = "figure"
  if not token.meta.get("figure"):
    return media
  caption = token.attrGet("title")
  figcaption = f"<figcaption>{escapeHtml(caption)}</figcaption>" if caption else ""
  return f'<figure class="{figure_class}">{media}{figcaption}</figure>'


def _render_video(renderer: RendererHTML, token: Token) -> str:
  source = escapeHtml(token.attrGet("src") or "")
  label = escapeHtml(renderer.renderInlineAsText(token.children or [], {}, {}))
  poster = token.meta.get("poster")
  poster_attribute = f' poster="{escapeHtml(poster)}"' if poster else ""
  return (
    f'<video controls playsinline preload="metadata" src="{source}"'
    f'{poster_attribute} aria-label="{label}"></video>'
  )


def _is_video_source(source: str) -> bool:
  return urlsplit(source).path.lower().endswith(_VIDEO_SUFFIXES)


def _poster_source(source: str) -> str:
  return source.rsplit(".", 1)[0] + ".jpg"


def _is_safe_link(url: str) -> bool:
  normalized = _CONTROL_RE.sub("", unquote(unescape(url))).strip().lower()
  return urlsplit(normalized).scheme not in _DANGEROUS_SCHEMES


def _walk_tokens(tokens: Iterable[Token]) -> Iterable[Token]:
  for token in tokens:
    yield token
    if token.type != "image" and token.children:
      yield from _walk_tokens(token.children)


def _plain_text(tokens: Iterable[Token]) -> str:
  parts: list[str] = []
  for token in tokens:
    if token.type in {"code_inline", "mathjax", "text"}:
      parts.append(token.content)
    elif token.type in {"hardbreak", "softbreak"}:
      parts.append(" ")
    elif token.type != "image" and token.children:
      parts.append(_plain_text(token.children))
  return "".join(parts)


def _slugify(value: str) -> str:
  slug: list[str] = []
  for character in unicodedata.normalize("NFKC", value).casefold():
    if character.isalnum():
      slug.append(character)
    elif slug and slug[-1] != "-":
      slug.append("-")
  return "".join(slug).strip("-") or "section"


def _normalize_whitespace(value: str) -> str:
  return " ".join(value.split())


def _truncate(value: str, limit: int) -> str:
  if len(value) <= limit:
    return value
  shortened = value[: limit - 1].rsplit(" ", 1)[0].rstrip(".,;:")
  return f"{shortened or value[: limit - 1].rstrip()}…"


def _local_asset_path(static_dir: Path, source: str) -> Path | None:
  parsed = urlsplit(unescape(source))
  if parsed.scheme or parsed.netloc:
    return None
  relative_path = unquote(parsed.path).lstrip("/")
  candidate = (static_dir / relative_path).resolve()
  try:
    candidate.relative_to(static_dir)
  except ValueError:
    return None
  return candidate


def image_dimensions(image_path: Path) -> tuple[int, int] | None:
  data = image_path.read_bytes()
  if b"<svg" in data[:1024]:
    return _svg_dimensions(data[:4096].decode("utf-8", "ignore"))
  if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
  if data.startswith((b"GIF87a", b"GIF89a")) and len(data) >= 10:
    return int.from_bytes(data[6:8], "little"), int.from_bytes(data[8:10], "little")
  if data.startswith(b"\xff\xd8"):
    offset = 2
    while offset + 9 < len(data):
      if data[offset] != 0xFF:
        offset += 1
        continue
      marker = data[offset + 1]
      offset += 2
      if marker in {0xD8, 0xD9}:
        continue
      if offset + 2 > len(data):
        break
      segment_length = int.from_bytes(data[offset : offset + 2], "big")
      if marker in {
        0xC0,
        0xC1,
        0xC2,
        0xC3,
        0xC5,
        0xC6,
        0xC7,
        0xC9,
        0xCA,
        0xCB,
        0xCD,
        0xCE,
        0xCF,
      }:
        return (
          int.from_bytes(data[offset + 5 : offset + 7], "big"),
          int.from_bytes(data[offset + 3 : offset + 5], "big"),
        )
      offset += max(segment_length, 2)
  if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
    chunk = data[12:16]
    payload = data[20:]
    if chunk == b"VP8X" and len(payload) >= 10:
      return int.from_bytes(payload[4:7], "little") + 1, int.from_bytes(
        payload[7:10], "little"
      ) + 1
    if chunk == b"VP8 " and len(payload) >= 10:
      return int.from_bytes(payload[6:8], "little") & 0x3FFF, int.from_bytes(
        payload[8:10], "little"
      ) & 0x3FFF
    if chunk == b"VP8L" and len(payload) >= 5:
      width = 1 + payload[1] + ((payload[2] & 0x3F) << 8)
      height = 1 + (payload[2] >> 6) + (payload[3] << 2) + ((payload[4] & 0x0F) << 10)
      return width, height
  ispe_index = data.find(b"ispe")
  if ispe_index >= 4 and ispe_index + 16 <= len(data):
    return (
      int.from_bytes(data[ispe_index + 8 : ispe_index + 12], "big"),
      int.from_bytes(data[ispe_index + 12 : ispe_index + 16], "big"),
    )
  return None


def _svg_dimensions(head: str) -> tuple[int, int] | None:
  tag = re.search(r"<svg\b[^>]*>", head)
  if tag is None:
    return None
  attributes = tag.group(0)
  width = re.search(r'\swidth="(\d+)(?:px)?"', attributes)
  height = re.search(r'\sheight="(\d+)(?:px)?"', attributes)
  if width and height:
    return int(width.group(1)), int(height.group(1))
  view_box = re.search(
    r'\sviewBox="[\d.\-]+[\s,]+[\d.\-]+[\s,]+([\d.]+)[\s,]+([\d.]+)"', attributes
  )
  if view_box:
    return round(float(view_box.group(1))), round(float(view_box.group(2)))
  return None


def image_type(image_path: Path) -> str:
  guessed, _ = mimetypes.guess_type(image_path.name)
  return guessed or "image/jpeg"


def _responsive_variants(image_path: Path, source: str) -> list[str]:
  pattern = re.compile(
    rf"^{re.escape(image_path.stem)}-(\d+)w{re.escape(image_path.suffix)}$"
  )
  variants: list[tuple[int, str]] = []
  source_dir = source.rsplit("/", 1)[0]
  for candidate in image_path.parent.glob(f"{image_path.stem}-*w{image_path.suffix}"):
    match = pattern.fullmatch(candidate.name)
    if match:
      width = int(match.group(1))
      variants.append((width, f"{source_dir}/{candidate.name} {width}w"))
  return [value for _, value in sorted(variants)]
