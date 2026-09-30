from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Callable, Sequence
from datetime import date
from pathlib import Path
from typing import TextIO

from .build import BuildOptions, SiteBuilder
from .server import serve
from .validate import SiteValidator

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")


def create_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(prog="sitegen")
  commands = parser.add_subparsers(dest="command", required=True)

  build_parser = commands.add_parser("build", help="build the site")
  _add_drafts_option(build_parser)
  build_parser.add_argument(
    "--no-incremental",
    action="store_true",
    help="render every output instead of reusing unchanged files",
  )

  check_parser = commands.add_parser("check", help="build and validate the site")
  _add_drafts_option(check_parser)

  serve_parser = commands.add_parser("serve", help="build and serve the site")
  _add_drafts_option(serve_parser)
  serve_parser.add_argument(
    "--watch",
    action="store_true",
    help="rebuild after source changes",
  )
  serve_parser.add_argument("--host", default="127.0.0.1")
  serve_parser.add_argument("--port", type=int, default=8888)

  dev_parser = commands.add_parser("dev", help="serve with local development tools")
  dev_parser.set_defaults(drafts=True)
  dev_parser.add_argument(
    "--no-drafts",
    action="store_false",
    dest="drafts",
    help="exclude draft content",
  )
  dev_parser.add_argument("--host", default="127.0.0.1")
  dev_parser.add_argument("--port", type=int, default=8888)
  dev_parser.add_argument(
    "--open",
    action="store_true",
    dest="open_browser",
    help="open the site in the default browser",
  )

  new_parser = commands.add_parser("new", help="create a draft writing")
  new_parser.add_argument("slug")
  new_parser.add_argument("--title")

  return parser


def _add_drafts_option(parser: argparse.ArgumentParser) -> None:
  parser.add_argument(
    "--drafts",
    action="store_true",
    help="include draft content",
  )


def _build_options(arguments: argparse.Namespace) -> BuildOptions:
  return BuildOptions(
    include_drafts=arguments.drafts,
    incremental=not getattr(arguments, "no_incremental", False),
  )


def _print_report(report: object, stdout: TextIO) -> None:
  print(
    f"built {report.rendered} page(s), reused {report.reused} -> {report.output_dir}",
    file=stdout,
  )


def _scaffold_post(project_root: Path, slug: str, title: str | None = None) -> Path:
  if not SLUG_PATTERN.fullmatch(slug):
    raise ValueError(
      "invalid slug: use lowercase letters, digits, hyphens, or underscores"
    )
  post_path = project_root / "content" / "blogs" / slug / "index.md"
  if post_path.exists():
    raise FileExistsError(f"{post_path}: already exists")
  post_path.parent.mkdir(parents=True, exist_ok=False)
  resolved_title = (
    title.strip()
    if title and title.strip()
    else slug.replace("_", " ").replace("-", " ")
  )
  post_path.write_text(
    f"title: {resolved_title}\n"
    f"date: {date.today().isoformat()}\n"
    "draft: true\n"
    "description: add a short summary\n"
    "-----\n\n"
    "start writing.\n",
    encoding="utf-8",
  )
  return post_path


def main(
  argv: Sequence[str] | None = None,
  *,
  project_root: Path | None = None,
  builder_factory: Callable[[Path], SiteBuilder] = SiteBuilder,
  validator_factory: Callable[[], SiteValidator] = SiteValidator,
  serve_func: Callable[..., int] = serve,
  stdout: TextIO | None = None,
  stderr: TextIO | None = None,
) -> int:
  output = stdout or sys.stdout
  errors = stderr or sys.stderr
  root = Path.cwd() if project_root is None else Path(project_root)
  arguments = create_parser().parse_args(argv)

  try:
    if arguments.command == "new":
      created = _scaffold_post(root, arguments.slug, arguments.title)
      print(f"created {created}", file=output)
      return 0

    options = _build_options(arguments)
    if arguments.command == "serve":
      result = serve_func(
        root,
        options,
        host=arguments.host,
        port=arguments.port,
        watch=arguments.watch,
        builder_factory=builder_factory,
        stdout=output,
        stderr=errors,
      )
      return 0 if result is None else result

    if arguments.command == "dev":
      result = serve_func(
        root,
        options,
        host=arguments.host,
        port=arguments.port,
        watch=True,
        live_reload=True,
        open_browser=arguments.open_browser,
        builder_factory=builder_factory,
        stdout=output,
        stderr=errors,
      )
      return 0 if result is None else result

    builder = builder_factory(root)
    report = builder.build(options)

    if arguments.command == "build":
      _print_report(report, output)
      return 0

    print(f"valid: {report.output_dir}", file=output)
    return 0
  except Exception as error:
    print(f"error: {error}", file=errors)
    return 1
