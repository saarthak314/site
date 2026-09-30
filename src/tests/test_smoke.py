import importlib.util
import io
import sys
import threading
import unittest
from collections import defaultdict
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SMOKE_MODULE_PATH = PROJECT_ROOT / "src" / "sitegen" / "smoke.py"


def load_smoke_module():
  spec = importlib.util.spec_from_file_location("sitegen.smoke", SMOKE_MODULE_PATH)
  if spec is None or spec.loader is None:
    raise RuntimeError("could not load production smoke module")
  module = importlib.util.module_from_spec(spec)
  sys.modules[spec.name] = module
  spec.loader.exec_module(module)
  return module


@contextmanager
def serve_responses(responses):
  counts = defaultdict(int)

  class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
      sequence = responses.get(
        self.path,
        [(404, "text/plain; charset=utf-8", "missing")],
      )
      index = min(counts[self.path], len(sequence) - 1)
      counts[self.path] += 1
      status, content_type, body = sequence[index]
      encoded = body.encode("utf-8")
      self.send_response(status)
      self.send_header("Content-Type", content_type)
      self.send_header("Content-Length", str(len(encoded)))
      self.end_headers()
      self.wfile.write(encoded)

    def log_message(self, _format: str, *_args: object) -> None:
      pass

  server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    host, port = server.server_address
    yield f"http://{host}:{port}", counts
  finally:
    server.shutdown()
    server.server_close()
    thread.join()


class TestProductionSmokeChecks(unittest.TestCase):
  def load_smoke(self):
    self.assertTrue(SMOKE_MODULE_PATH.is_file(), "production smoke module is missing")
    return load_smoke_module()

  def test_default_expectations_cover_published_and_not_found_routes(self) -> None:
    smoke = self.load_smoke()
    expectations = {item.path: item for item in smoke.DEFAULT_EXPECTATIONS}

    for path in (
      "/",
      "/about/",
      "/blogs/",
      "/blogs/make_cool_stuff/",
      "/feed.xml",
      "/sitemap.xml",
      "/robots.txt",
      "/llms.txt",
      "/404.html",
    ):
      self.assertIn(path, expectations)
      self.assertEqual(expectations[path].status, 200)

    missing = expectations["/__sitegen-smoke-missing__/"]
    self.assertEqual(missing.status, 404)
    self.assertIn("nothing here", missing.contains)

  def test_smoke_checks_retry_transient_failures_and_accept_custom_404s(self) -> None:
    smoke = self.load_smoke()
    responses = {
      "/": [
        (503, "text/plain; charset=utf-8", "warming up"),
        (200, "text/html; charset=utf-8", "<title>sλrthak</title>"),
      ],
      "/missing/": [
        (404, "text/html; charset=utf-8", "<h1>nothing here</h1>"),
      ],
    }
    expectations = (
      smoke.RouteExpectation("/", 200, ("sλrthak",)),
      smoke.RouteExpectation("/missing/", 404, ("nothing here",)),
    )

    with serve_responses(responses) as (base_url, counts):
      output = io.StringIO()
      smoke.run_smoke_checks(
        base_url,
        expectations=expectations,
        attempts=2,
        delay=0,
        stdout=output,
      )

    self.assertEqual(counts["/"], 2)
    self.assertEqual(counts["/missing/"], 1)
    self.assertIn("ok 200 /", output.getvalue())
    self.assertIn("ok 404 /missing/", output.getvalue())

  def test_smoke_checks_report_the_failed_route_and_missing_marker(self) -> None:
    smoke = self.load_smoke()
    responses = {
      "/": [(200, "text/html; charset=utf-8", "<title>wrong site</title>")],
    }

    with serve_responses(responses) as (base_url, _counts):
      with self.assertRaises(smoke.SmokeCheckError) as caught:
        smoke.run_smoke_checks(
          base_url,
          expectations=(smoke.RouteExpectation("/", 200, ("sλrthak",)),),
          attempts=1,
          delay=0,
        )

    message = str(caught.exception)
    self.assertIn("/", message)
    self.assertIn("sλrthak", message)


if __name__ == "__main__":
  unittest.main()
