// A Cloudflare Worker that answers GET /now with the track playing on Spotify,
// or the last one played. It holds the refresh token so the site never does.
//
// Secrets (wrangler secret put ...): SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET,
// SPOTIFY_REFRESH_TOKEN. Vars (wrangler.toml): ALLOWED_ORIGINS.

const TOKEN_URL = "https://accounts.spotify.com/api/token";
const NOW_URL = "https://api.spotify.com/v1/me/player/currently-playing";
const RECENT_URL = "https://api.spotify.com/v1/me/player/recently-played?limit=1";
const CACHE_MS = 30_000;
const DEFAULT_ORIGINS = "https://sarrthak.com";

// Per-isolate caches: good enough for a 30 second window, no storage needed.
let token = { value: null, expiresAt: 0 };
let cached = { body: null, at: 0 };

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const cors = corsHeaders(request.headers.get("Origin"), env);
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors });
    }
    if (request.method !== "GET" || url.pathname !== "/now") {
      return json({ error: "not found" }, 404, cors);
    }
    try {
      if (!cached.body || Date.now() - cached.at > CACHE_MS) {
        cached = { body: await nowPlaying(env), at: Date.now() };
      }
      return json(cached.body, 200, { ...cors, "cache-control": "public, max-age=30" });
    } catch (error) {
      const message = error && error.message ? error.message : String(error);
      return json({ error: message }, 502, { ...cors, "cache-control": "no-store" });
    }
  },
};

function corsHeaders(origin, env) {
  const allowed = String(env.ALLOWED_ORIGINS || DEFAULT_ORIGINS)
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
  const headers = {
    "access-control-allow-methods": "GET, OPTIONS",
    "access-control-max-age": "86400",
    vary: "Origin",
  };
  if (origin && allowed.includes(origin)) headers["access-control-allow-origin"] = origin;
  return headers;
}

function json(body, status, headers) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", ...headers },
  });
}

async function accessToken(env) {
  if (token.value && Date.now() < token.expiresAt - 60_000) return token.value;
  for (const name of ["SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET", "SPOTIFY_REFRESH_TOKEN"]) {
    if (!env[name]) throw new Error(`${name} is not set`);
  }
  const response = await fetch(TOKEN_URL, {
    method: "POST",
    headers: {
      authorization: "Basic " + btoa(`${env.SPOTIFY_CLIENT_ID}:${env.SPOTIFY_CLIENT_SECRET}`),
      "content-type": "application/x-www-form-urlencoded",
    },
    body: new URLSearchParams({
      grant_type: "refresh_token",
      refresh_token: env.SPOTIFY_REFRESH_TOKEN,
    }),
  });
  if (!response.ok) throw new Error(`spotify token refresh failed (${response.status})`);
  const data = await response.json();
  token = {
    value: data.access_token,
    expiresAt: Date.now() + (data.expires_in || 3600) * 1000,
  };
  return token.value;
}

async function nowPlaying(env) {
  const headers = { authorization: `Bearer ${await accessToken(env)}` };
  const fetchedAt = new Date().toISOString();
  const current = await fetch(NOW_URL, { headers });
  if (current.status === 200) {
    const data = await current.json();
    if (data && data.item && data.currently_playing_type === "track") {
      return {
        playing: Boolean(data.is_playing),
        progress_ms: data.progress_ms ?? null,
        played_at: null,
        fetched_at: fetchedAt,
        track: track(data.item),
      };
    }
  } else if (current.status !== 204) {
    if (current.status === 401) token = { value: null, expiresAt: 0 };
    throw new Error(`spotify currently-playing failed (${current.status})`);
  }
  // Nothing playing, or an ad or podcast: fall back to the last track played.
  const recent = await fetch(RECENT_URL, { headers });
  if (!recent.ok) throw new Error(`spotify recently-played failed (${recent.status})`);
  const data = await recent.json();
  const item = data.items && data.items[0];
  if (!item || !item.track) {
    return { playing: false, progress_ms: null, played_at: null, fetched_at: fetchedAt, track: null };
  }
  return {
    playing: false,
    progress_ms: null,
    played_at: item.played_at,
    fetched_at: fetchedAt,
    track: track(item.track),
  };
}

function track(item) {
  const images = (item.album && item.album.images) || [];
  return {
    title: item.name,
    artists: (item.artists || []).map((artist) => artist.name),
    album: item.album ? item.album.name : null,
    duration_ms: item.duration_ms,
    url: item.external_urls ? item.external_urls.spotify : null,
    art: images.length ? images[images.length - 1].url : null,
  };
}
