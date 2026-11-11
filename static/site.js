(() => {
  "use strict";

  // The rail's table of contents folds on narrow screens. Without this script it
  // stays open everywhere, which is a fine fallback.
  const wide = window.matchMedia("(min-width: 1000px)");
  const fold = document.querySelector(".rail__fold");
  if (fold) {
    const sync = () => {
      fold.open = wide.matches;
    };
    sync();
    wide.addEventListener("change", sync);
  }

  // The banner's dots ride a wave under the mouse. That code lives in cat.js
  // and loads the first time the mouse really moves over the banner, so a page
  // load pays for nothing but the text; touch screens and reduced motion never
  // load it.
  const banner = document.querySelector(".banner");
  const pointer = "(hover: hover) and (pointer: fine) and (prefers-reduced-motion: no-preference)";
  // The sky (twinkling stars, a shooting star) holds still while the banner
  // is out of view.
  if (banner && "IntersectionObserver" in window) {
    new IntersectionObserver((entries) => {
      entries.forEach((entry) => banner.classList.toggle("banner--still", !entry.isIntersecting));
    }).observe(banner);
  }
  if (banner && window.matchMedia(pointer).matches) {
    const wake = (event) => {
      // the page scrolling under a resting cursor reports a move with no movement
      if (event.pointerType !== "mouse" || (!event.movementX && !event.movementY)) return;
      banner.removeEventListener("pointermove", wake);
      import("/cat.js").then((art) => art.start(banner, event)).catch(() => {});
    };
    banner.addEventListener("pointermove", wake, { passive: true });
  }

  // A copy affordance on code blocks, revealed on hover.
  if (navigator.clipboard) {
    document.querySelectorAll(".blog-article pre > code").forEach((code) => {
      const pre = code.parentElement;
      if (!pre) return;
      const button = document.createElement("button");
      button.type = "button";
      button.className = "copy";
      button.textContent = "copy";
      button.setAttribute("aria-label", "copy code");
      button.addEventListener("click", async () => {
        try {
          await navigator.clipboard.writeText(code.textContent || "");
          button.textContent = "copied";
          window.setTimeout(() => {
            button.textContent = "copy";
          }, 1500);
        } catch {
          button.textContent = "copy";
        }
      });
      pre.appendChild(button);
    });
  }

  // Mark the heading currently in view in the rail.
  const links = Array.from(document.querySelectorAll('.rail__list a[href^="#"]'));
  if (links.length && "IntersectionObserver" in window) {
    const byId = new Map(links.map((link) => [link.getAttribute("href").slice(1), link]));
    const headings = Array.from(byId.keys())
      .map((id) => document.getElementById(id))
      .filter(Boolean);
    let current = null;
    const setCurrent = (id) => {
      const next = byId.get(id);
      if (!next || next === current) return;
      if (current) current.removeAttribute("aria-current");
      next.setAttribute("aria-current", "true");
      current = next;
    };
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) setCurrent(entry.target.id);
        });
      },
      { rootMargin: "0px 0px -70% 0px" },
    );
    headings.forEach((heading) => observer.observe(heading));
  }

  // Reading meter: how far down the article the reader is, in the rail's register.
  const progress = document.querySelector(".rail__progress");
  const article = document.querySelector(".blog-article");
  if (progress && article) {
    const minutes = parseInt(progress.dataset.minutes, 10) || 0;
    const words = (article.textContent || "").trim().split(/\s+/).length;
    const count = words >= 1000 ? (words / 1000).toFixed(1) + "k" : String(words);
    const cells = 12;
    const meter = document.createElement("span");
    const stats = document.createElement("span");
    meter.className = "progress__meter";
    stats.className = "progress__hi";
    progress.append("read ", meter, "\n", stats);
    let queued = false;
    const paint = () => {
      queued = false;
      const rect = article.getBoundingClientRect();
      const line = window.innerHeight * 0.35;
      const fraction = Math.min(1, Math.max(0, (line - rect.top) / Math.max(1, rect.height)));
      const filled = Math.round(fraction * cells);
      meter.textContent = "\u2593".repeat(filled) + "\u2591".repeat(cells - filled) + " " + Math.round(fraction * 100) + "%";
      const left = Math.max(0, Math.ceil(minutes * (1 - fraction)));
      stats.textContent = (left ? left + " min left" : "done") + " // " + count + " words";
    };
    const request = () => {
      if (queued) return;
      queued = true;
      window.requestAnimationFrame(paint);
    };
    window.addEventListener("scroll", request, { passive: true });
    window.addEventListener("resize", request);
    paint();
  }

  // Now playing: a worker answers /now with the spotify track playing (or the
  // last one played); this fills the small player and keeps its clock and rail
  // moving while it plays.
  document.querySelectorAll("[data-now]").forEach((box) => {
    const endpoint = box.dataset.now;
    const title = box.querySelector(".now__title");
    const by = box.querySelector(".now__by");
    const at = box.querySelector(".now__at");
    const length = box.querySelector(".now__length");
    if (!endpoint || !title || !by || !at || !length || !window.fetch) return;
    const lower = (value) => String(value || "").toLowerCase();
    const clock = (ms) => {
      const seconds = Math.max(0, Math.floor(ms / 1000));
      return Math.floor(seconds / 60) + ":" + String(seconds % 60).padStart(2, "0");
    };
    const ago = (iso) => {
      const minutes = Math.max(1, Math.round((Date.now() - Date.parse(iso)) / 60000));
      if (minutes < 60) return minutes + "m ago";
      const hours = Math.round(minutes / 60);
      if (hours < 48) return hours + "h ago";
      return Math.round(hours / 24) + "d ago";
    };
    let state = null;
    let ticker = 0;
    let poller = 0;
    let failures = 0;
    let visible = false;

    const running = () =>
      Boolean(state && state.data.playing && state.data.progress_ms != null && state.data.track.duration_ms);
    const elapsed = () => {
      if (!running()) return 0;
      const duration = state.data.track.duration_ms;
      return Math.min(duration, state.data.progress_ms + (Date.now() - state.receivedAt));
    };
    const tick = () => {
      if (!running()) return;
      const duration = state.data.track.duration_ms;
      const done = elapsed();
      at.textContent = clock(done);
      length.textContent = clock(duration);
      box.style.setProperty("--progress", (done / duration).toFixed(4));
      if (done >= duration) load();
    };

    // A spectrum in dots, set like the cat at the top. It isn't the song's real
    // sound (spotify no longer shares that): the bars keep a beat taken from
    // the track's place in the song, so they pause with it and settle flat when
    // it stops. About twelve frames a second, and only while it's on screen.
    const viz = box.querySelector(".now__viz");
    const lit = viz && viz.querySelector(".now__lit");
    const peaks = viz && viz.querySelector(".now__caps");
    const rest = viz && viz.querySelector(".now__rest");
    const ROWS = 6;
    const calm = window.matchMedia("(prefers-reduced-motion: reduce)");
    let columns = 0;
    let bars = [];
    let caps = [];
    let bpm = 112;
    let frame = 0;
    const hash = (n) => {
      const s = Math.sin(n * 127.1) * 43758.5453;
      return s - Math.floor(s);
    };
    // smooth noise across the bands and through the song, so neighbours rise together
    const noise = (x, y) => {
      const i = Math.floor(x);
      const j = Math.floor(y);
      const u = (x - i) * (x - i) * (3 - 2 * (x - i));
      const v = (y - j) * (y - j) * (3 - 2 * (y - j));
      const a = hash(i + j * 57);
      const b = hash(i + 1 + j * 57);
      const c = hash(i + (j + 1) * 57);
      const d = hash(i + 1 + (j + 1) * 57);
      return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
    };
    const fit = () => {
      const cell = parseFloat(window.getComputedStyle(viz).fontSize) * 0.4;
      const next = Math.max(12, Math.floor(viz.clientWidth / cell));
      if (next === columns) return;
      columns = next;
      bars = new Array(columns).fill(0);
      caps = new Array(columns).fill(0);
      rest.textContent = new Array(ROWS).fill("\u00b7".repeat(columns)).join("\n");
    };
    const step = (settle) => {
      const playing = box.classList.contains("now--playing");
      const t = elapsed();
      const beat = (t / 60000) * bpm;
      const kick = Math.exp(-(beat % 1) * 5);
      const snare = Math.exp(-((beat + 1) % 2) * 4);
      const hat = Math.exp(-((beat * 2) % 1) * 7);
      const flicker = Math.floor(t / 83);
      for (let c = 0; c < columns; c += 1) {
        const x = c / (columns - 1);
        const n = noise(c * 0.45, t * 0.0016);
        // the kick lifts the low end, the snare the middle, the hats the top
        const hit =
          Math.max(0, 1 - x * 3) * kick +
          Math.max(0, 1 - Math.abs(x - 0.45) * 4) * snare * 0.8 +
          Math.max(0, x * 1.6 - 0.6) * hat * 0.6;
        const level =
          (0.1 + 0.75 * n * n) * (1 - 0.3 * x) +
          0.6 * hit * (0.4 + n) +
          0.12 * kick +
          0.12 * (hash(c * 13 + flicker) - 0.5);
        const target = playing ? Math.min(1, Math.max(0, level)) : 0;
        // up at once, down under gravity; a dot left at each peak drifts after it
        if (settle || target > bars[c]) bars[c] = target;
        else bars[c] = Math.max(target, bars[c] - 0.07);
        caps[c] = settle || bars[c] >= caps[c] ? bars[c] : caps[c] - 0.025;
      }
    };
    // the bars and the dot each peak leaves behind are drawn on two layers, so
    // each keeps one solid colour
    const draw = () => {
      const lines = [];
      const tops = [];
      for (let row = ROWS; row >= 1; row -= 1) {
        let line = "";
        let top = "";
        for (let c = 0; c < columns; c += 1) {
          const bar = row <= Math.round(bars[c] * ROWS);
          line += bar ? "\u2022" : " ";
          top += !bar && row === Math.round(caps[c] * ROWS) ? "\u2022" : " ";
        }
        lines.push(line);
        tops.push(top);
      }
      lit.textContent = lines.join("\n");
      peaks.textContent = tops.join("\n");
    };
    const moving = () =>
      visible && !document.hidden && (box.classList.contains("now--playing") || caps.some((v) => v > 0));
    const animate = () => {
      frame = 0;
      step(false);
      draw();
      if (moving()) frame = window.setTimeout(animate, 83);
    };
    const wake = () => {
      if (!lit || !rest || !peaks) return;
      fit();
      if (calm.matches) {
        step(true);
        draw();
      } else if (!frame && moving()) animate();
    };
    if (viz && "ResizeObserver" in window) {
      new ResizeObserver(() => {
        const before = columns;
        fit();
        if (columns !== before) draw();
      }).observe(viz);
    }

    const render = (note) => {
      const data = state && state.data;
      if (!data || !data.track) {
        box.hidden = true;
        box.classList.add("now--off");
        return;
      }
      const track = data.track;
      const playing = running() && !note;
      box.classList.toggle("now--playing", playing);
      title.textContent = lower(track.title);
      if (track.url) {
        title.href = track.url;
        title.rel = "noopener";
      } else {
        title.removeAttribute("href");
      }
      // each track keeps its own tempo, somewhere between 92 and 132
      bpm = 92 + Math.floor(hash([...String(track.title)].reduce((h, ch) => (h * 31 + ch.charCodeAt(0)) % 9973, 7)) * 40);
      const artists = lower((track.artists || []).join(", "));
      by.textContent = track.album ? artists + " // " + lower(track.album) : artists;
      if (playing) tick();
      else {
        at.textContent =
          note || (data.playing ? "playing" : data.played_at ? "last played " + ago(data.played_at) : "paused");
        length.textContent = "";
      }
      box.hidden = false;
      wake();
    };
    const stop = () => {
      if (ticker) window.clearInterval(ticker);
      if (poller) window.clearTimeout(poller);
      ticker = 0;
      poller = 0;
    };
    const schedule = () => {
      if (poller) window.clearTimeout(poller);
      poller = 0;
      if (!visible || document.hidden) return;
      const playing = Boolean(state && state.data.playing);
      poller = window.setTimeout(load, playing ? 30000 : 120000);
      if (playing && !ticker) ticker = window.setInterval(tick, 1000);
      if (!playing && ticker) {
        window.clearInterval(ticker);
        ticker = 0;
      }
    };
    const storageKey = "sarrthak.now";
    const remember = (data) => {
      try {
        window.localStorage.setItem(storageKey, JSON.stringify(data));
      } catch {
        // storage can be full or disabled; the block still works without it
      }
    };
    // The page head started the first request before this script ran.
    let early = window.__now instanceof Promise ? window.__now : null;
    let loading = false;
    const load = async () => {
      if (loading) return;
      loading = true;
      if (poller) window.clearTimeout(poller);
      poller = 0;
      try {
        const response = early ? await early : await fetch(endpoint, { mode: "cors" });
        early = null;
        if (!response || !response.ok) throw new Error(String(response && response.status));
        state = { data: await response.json(), receivedAt: Date.now() };
        failures = 0;
        remember(state.data);
        render();
      } catch {
        failures += 1;
        if (failures >= 2) {
          box.hidden = true;
          box.classList.add("now--off");
          stop();
          loading = false;
          return;
        }
      }
      loading = false;
      schedule();
    };
    const sync = () => {
      box.classList.toggle("now--away", !visible || document.hidden);
      if (state) wake();
      if (visible && !document.hidden) {
        if (!state) load();
        else schedule();
      } else {
        stop();
      }
    };
    // Show the last known track at once; the fresh answer replaces it.
    try {
      const stored = JSON.parse(window.localStorage.getItem(storageKey) || "null");
      if (stored && stored.track && !state) {
        state = { data: { ...stored, playing: false, progress_ms: null }, receivedAt: Date.now() };
        render("syncing");
        state = null;
      }
    } catch {
      // ignore unreadable storage
    }
    if (early) load();
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            visible = entry.isIntersecting;
          });
          sync();
        },
        { rootMargin: "120px 0px" },
      ).observe(box.parentElement || box); // the box is hidden until data arrives
    } else {
      visible = true;
      sync();
    }
    document.addEventListener("visibilitychange", sync);
  });

  // Ships over the footer city. Each ship is one CSS transform animation on its
  // own element; this scheduler only decides when and where the next one appears.
  const cities = Array.from(document.querySelectorAll("[data-city]"));
  const stillness = window.matchMedia("(prefers-reduced-motion: reduce)");
  if (cities.length && !stillness.matches && "IntersectionObserver" in window) {
    const hull = (text) => '<span class="hull">' + text + "</span>";
    const hi = (text) => '<span class="hi">' + text + "</span>";
    const thrust = (text) => '<span class="thrust">' + text + "</span>";
    // Right-facing sprites, drawn as silhouettes: dark hull, lit edges, lavender exhaust.
    const sprites = [
      // corvette: raised bridge, long hull, twin exhaust
      [
        "        " + hi("▄▟▀▀▙"),
        thrust("▪═══") + hull("▐") + hi("▛") + "▀▀▀▀▀▀▀▀" + hi("▙") + hull("▶"),
        thrust("▪═") + "  " + hull("▝▀▀▀▀▀▀▀▀▀▀▘"),
      ],
      // freighter: cab hauling three containers
      [
        "  " + hull("┌─┐┌─┐┌─┐ ") + hi("▄▄"),
        thrust("▪═") + hull("▐") + hi("▒") + hull("▌▐") + hi("▒") + hull("▌▐") + hi("▒") + hull("▌") + "▐█" + hi("▙") + hull("▶"),
        "  " + hull("└─┘└─┘└─┘ ") + hull("▀▀"),
      ],
      // saucer: lit dome over a wide disc
      [
        "   " + hi("▄▟▀▀▙▄"),
        hull("◂") + "▀▀▀" + thrust("▀") + "▀▀" + thrust("▀") + "▀▀▀" + hull("▶"),
        "    " + hull("▀▄▄▀"),
      ],
      // hauler: two hull segments on a spine, engines aft
      [
        "   " + hi("▄▄▄▄") + "     " + hi("▄▄▄▄▄▄"),
        thrust("▪▪") + hull("▐▒▒▒▒▌") + "═══" + hull("▐▒▒▒▒▒▒▌") + hi("▶"),
        "   " + hull("▀▀▀▀") + "     " + hull("▀▀▀▀▀▀"),
      ],
      // interceptor: swept arrow with a hot tail
      [
        "      " + hi("▄▄▟▛"),
        thrust("▪══") + hull("▐") + "▀▀▀▀▀▀▀▀" + hi("▶"),
        "      " + hull("▀▀▜▙"),
      ],
    ];
    const mirrorMap = {
      "▶": "◂", "◂": "▶", "▸": "◃", "◃": "▸", "▐": "▌", "▌": "▐", "▙": "▟", "▟": "▙",
      "▛": "▜", "▜": "▛", "┌": "┐", "┐": "┌", "└": "┘", "┘": "└", "╭": "╮", "╮": "╭",
      "╰": "╯", "╯": "╰", "╣": "╠", "╠": "╣", "╘": "╛", "╛": "╘", "╱": "╲", "╲": "╱",
      "▝": "▘", "▘": "▝", "▖": "▗", "▗": "▖",
      "<": ">", ">": "<", "(": ")", ")": "(", "/": "\\", "\\": "/",
    };
    const mirrorText = (text) =>
      Array.from(text)
        .reverse()
        .map((glyph) => mirrorMap[glyph] || glyph)
        .join("");
    // Rows contain tone spans; mirror each text segment and reverse the segment order.
    const mirrorRow = (row) => {
      const width = Array.from(row.replace(/<[^>]+>/g, "")).length;
      const segments = row.split(/(<span class="[a-z]+">|<\/span>)/).filter(Boolean);
      const out = [];
      for (let index = segments.length - 1; index >= 0; index -= 1) {
        const segment = segments[index];
        if (segment === "</span>") out.push(null);
        else if (segment.startsWith("<span")) out.push(segment);
        else out.push(mirrorText(segment));
      }
      // Re-pair the spans: after reversal each open tag follows its text.
      const rebuilt = [];
      let pending = null;
      out.forEach((piece) => {
        if (piece === null) return;
        if (piece.startsWith("<span")) {
          if (pending !== null) rebuilt.push(piece + pending + "</span>");
          pending = null;
        } else if (pending !== null) {
          rebuilt.push(pending);
          pending = piece;
        } else {
          pending = piece;
        }
      });
      if (pending !== null) rebuilt.push(pending);
      return { html: rebuilt.join(""), width };
    };
    const padRows = (rows) => {
      const widths = rows.map((row) => Array.from(row.replace(/<[^>]+>/g, "")).length);
      const max = Math.max.apply(null, widths);
      return rows.map((row, index) => " ".repeat(max - widths[index]) + row);
    };
    const spriteHtml = (rows, left) => {
      if (!left) return rows.join("\n");
      const mirrored = rows.map((row) => mirrorRow(row));
      const max = Math.max.apply(null, mirrored.map((row) => row.width));
      return mirrored.map((row) => row.html + " ".repeat(max - row.width)).join("\n");
    };
    const between = (low, high) => low + Math.random() * (high - low);

    cities.forEach((city) => {
      const lane = city.querySelector(".city__ships");
      const state = { alive: 0, timer: 0, paused: false, visible: false };
      const spawn = () => {
        state.timer = 0;
        if (!lane || state.paused || !state.visible) return;
        if (state.alive < 1) {
          const ship = document.createElement("pre");
          const left = Math.random() < 0.5;
          const far = Math.random() < 0.45;
          const rows = padRows(sprites[Math.floor(Math.random() * sprites.length)]);
          ship.className = "ship" + (left ? " ship--left" : "") + (far ? " ship--far" : " ship--near");
          ship.setAttribute("aria-hidden", "true");
          ship.innerHTML = spriteHtml(rows, left);
          ship.style.setProperty("--y", between(far ? 4 : 18, far ? 24 : 40).toFixed(1) + "%");
          ship.style.setProperty("--dur", (far ? between(32, 44) : between(22, 30)).toFixed(1) + "s");
          ship.style.setProperty("--scale", (far ? between(0.6, 0.8) : between(0.95, 1.2)).toFixed(2));
          ship.addEventListener("animationend", () => {
            ship.remove();
            state.alive -= 1;
          });
          lane.appendChild(ship);
          state.alive += 1;
        }
        schedule(between(18000, 30000));
      };
      const schedule = (delay) => {
        if (state.timer) window.clearTimeout(state.timer);
        state.timer = window.setTimeout(spawn, delay);
      };
      const sync = () => {
        const running = state.visible && !document.hidden;
        state.paused = !running;
        city.classList.toggle("city--paused", !running);
        if (running) {
          if (lane && !state.timer) schedule(state.alive ? between(18000, 30000) : 6000);
        } else {
          if (state.timer) window.clearTimeout(state.timer);
          state.timer = 0;
        }
      };
      new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            state.visible = entry.isIntersecting;
          });
          sync();
        },
        { rootMargin: "80px 0px" },
      ).observe(city);
      document.addEventListener("visibilitychange", sync);
    });
  }
})();
