from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from typing import TextIO
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class RouteExpectation:
  path: str
  status: int
  contains: tuple[str, ...]


DEFAULT_EXPECTATIONS = (
  RouteExpectation("/", 200, ("systems, models, machines",)),
  RouteExpectation("/about/", 200, ("about me", "current setup")),
  RouteExpectation("/blogs/", 200, ("all writings",)),
  RouteExpectation("/blogs/make_cool_stuff/", 200, ("make cool stuff",)),
  RouteExpectation("/feed.xml", 200, ("<rss",)),
  RouteExpectation("/sitemap.xml", 200, ("<urlset",)),
  RouteExpectation(
    "/robots.txt",
    200,
    ("Sitemap: https://sarrthak.com/sitemap.xml",),
  ),
  RouteExpectation("/llms.txt", 200, ("# sλrthak",)),
  RouteExpectation("/404.html", 200, ("nothing here", "wrong turn.")),
  RouteExpectation(
    "/__sitegen-smoke-missing__/",
    404,
    ("nothing here", "wrong turn."),
  ),
)


class SmokeCheckError(RuntimeError):
  pass


def fetch_route(url: str) -> tuple[int, str]:
  request = Request(url, headers={"User-Agent": "sarrthak-sitegen-smoke/2"})
  try:
    with urlopen(request, timeout=15) as response:
      status = response.status
      body = response.read()
      charset = response.headers.get_content_charset() or "utf-8"
  except HTTPError as error:
    status = error.code
    body = error.read()
    charset = error.headers.get_content_charset() or "utf-8"
  return status, body.decode(charset, errors="replace")


def check_route(base_url: str, expectation: RouteExpectation) -> None:
  url = f"{base_url.rstrip('/')}{expectation.path}"
  status, body = fetch_route(url)
  if status != expectation.status:
    raise SmokeCheckError(
      f"{expectation.path}: expected status {expectation.status}, got {status}"
    )
  for marker in expectation.contains:
    if marker not in body:
      raise SmokeCheckError(
        f"{expectation.path}: response is missing marker {marker!r}"
      )


def run_smoke_checks(
  base_url: str,
  *,
  expectations: tuple[RouteExpectation, ...] = DEFAULT_EXPECTATIONS,
  attempts: int = 10,
  delay: float = 3,
  stdout: TextIO = sys.stdout,
) -> None:
  if attempts < 1:
    raise ValueError("attempts must be at least 1")

  for expectation in expectations:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
      try:
        check_route(base_url, expectation)
      except (SmokeCheckError, URLError, TimeoutError) as error:
        last_error = error
        if attempt < attempts:
          time.sleep(delay)
          continue
        break
      last_error = None
      print(f"ok {expectation.status} {expectation.path}", file=stdout)
      break
    else:
      raise AssertionError("unreachable")

    if last_error is not None and attempt == attempts:
      raise SmokeCheckError(str(last_error)) from last_error


def build_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(description="Smoke-test the deployed site")
  parser.add_argument("--base-url", required=True)
  parser.add_argument("--attempts", type=int, default=10)
  parser.add_argument("--delay", type=float, default=3)
  return parser


def main(argv: list[str] | None = None) -> int:
  args = build_parser().parse_args(argv)
  try:
    run_smoke_checks(
      args.base_url,
      attempts=args.attempts,
      delay=args.delay,
    )
  except (SmokeCheckError, ValueError) as error:
    print(f"smoke failed: {error}", file=sys.stderr)
    return 1
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
