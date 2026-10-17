"""One-time Spotify authorisation: prints the refresh token the worker needs.

Usage:
  SPOTIFY_CLIENT_ID=... SPOTIFY_CLIENT_SECRET=... python3 scripts/spotify_auth.py

The Spotify app must list http://127.0.0.1:8899/callback as a redirect URI.
Nothing is written to disk; paste the printed token into
``npx wrangler secret put SPOTIFY_REFRESH_TOKEN`` from worker/spotify.
"""

from __future__ import annotations

import base64
import json
import os
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from getpass import getpass
from http.server import BaseHTTPRequestHandler, HTTPServer

AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
REDIRECT_URI = "http://127.0.0.1:8899/callback"
SCOPES = "user-read-currently-playing user-read-recently-played"


def main() -> int:
  client_id = (
    os.environ.get("SPOTIFY_CLIENT_ID") or input("spotify client id: ").strip()
  )
  client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET") or getpass(
    "spotify client secret: "
  )
  if not client_id or not client_secret:
    print("client id and secret are required", file=sys.stderr)
    return 1

  state = secrets.token_urlsafe(16)
  auth_url = (
    AUTHORIZE_URL
    + "?"
    + urllib.parse.urlencode(
      {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "state": state,
        "show_dialog": "false",
      }
    )
  )
  result: dict[str, str] = {}

  class Callback(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 (http.server naming)
      parsed = urllib.parse.urlsplit(self.path)
      query = dict(urllib.parse.parse_qsl(parsed.query))
      if parsed.path != "/callback":
        self.send_error(404)
        return
      if query.get("state") != state or "code" not in query:
        result["error"] = query.get("error", "state mismatch")
        self._reply(400, "authorisation failed, check the terminal.")
        return
      result["code"] = query["code"]
      self._reply(200, "authorised. you can close this tab.")

    def _reply(self, status: int, text: str) -> None:
      body = text.encode("utf-8")
      self.send_response(status)
      self.send_header("content-type", "text/plain; charset=utf-8")
      self.send_header("content-length", str(len(body)))
      self.end_headers()
      self.wfile.write(body)

    def log_message(self, *_args: object) -> None:
      return

  server = HTTPServer(("127.0.0.1", 8899), Callback)
  print(
    "opening the spotify consent page; if nothing opens, visit:\n" + auth_url + "\n"
  )
  webbrowser.open(auth_url)
  try:
    while "code" not in result and "error" not in result:
      server.handle_request()
  finally:
    server.server_close()
  if "error" in result:
    print(f"spotify returned: {result['error']}", file=sys.stderr)
    return 1

  data = urllib.parse.urlencode(
    {
      "grant_type": "authorization_code",
      "code": result["code"],
      "redirect_uri": REDIRECT_URI,
    }
  ).encode("utf-8")
  basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode("ascii")
  request = urllib.request.Request(
    TOKEN_URL,
    data=data,
    headers={
      "Authorization": f"Basic {basic}",
      "Content-Type": "application/x-www-form-urlencoded",
    },
  )
  try:
    with urllib.request.urlopen(request, timeout=30) as response:
      tokens = json.load(response)
  except urllib.error.HTTPError as exc:
    print(f"token exchange failed ({exc.code}): {exc.read().decode()}", file=sys.stderr)
    return 1

  print("refresh token (keep it secret):\n")
  print(tokens["refresh_token"])
  print("\nnext, from worker/spotify:")
  print("  npx wrangler secret put SPOTIFY_REFRESH_TOKEN")
  return 0


if __name__ == "__main__":
  sys.exit(main())
