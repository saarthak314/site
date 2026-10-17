# now playing worker

a cloudflare worker that answers `GET /now` with the spotify track playing right now, or the last one played, as json:

```json
{"playing": true, "progress_ms": 134000, "played_at": null, "fetched_at": "...",
 "track": {"title": "...", "artists": ["..."], "album": "...", "duration_ms": 251000, "url": "https://open.spotify.com/track/...", "art": "https://i.scdn.co/..."}}
```

responses are cached for 30 seconds. errors come back as `502 {"error": "..."}`. browsers may read it only from the origins in `ALLOWED_ORIGINS`.

## setup

1. create an app at https://developer.spotify.com/dashboard with the redirect uri `http://127.0.0.1:8899/callback` and the web api enabled. note the client id and secret.
2. mint the refresh token once, from the repo root:
   ```sh
   SPOTIFY_CLIENT_ID=... SPOTIFY_CLIENT_SECRET=... python3 scripts/spotify_auth.py
   ```
3. deploy, from this directory:
   ```sh
   npx wrangler login
   npx wrangler secret put SPOTIFY_CLIENT_ID
   npx wrangler secret put SPOTIFY_CLIENT_SECRET
   npx wrangler secret put SPOTIFY_REFRESH_TOKEN
   npx wrangler deploy
   ```
4. check it: `curl https://sarrthak-now.<account>.workers.dev/now`
5. put that url in the page's front matter as `now_playing:` and rebuild the site.

`npx wrangler dev` runs it locally with the values from `.dev.vars` (see `.dev.vars.example`).
