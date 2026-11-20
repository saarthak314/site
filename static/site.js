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

  // The banner's dots ride a wave under the mouse, or under a finger. That
  // code lives in cat.js and loads the first time the mouse really moves over
  // the banner or a finger touches it, so a page load pays for nothing but the
  // picture; reduced motion never loads it.
  const banner = document.querySelector(".banner");
  const motion = "(prefers-reduced-motion: no-preference)";
  // The sky (twinkling stars, a shooting star) holds still while the banner
  // is out of view.
  if (banner && "IntersectionObserver" in window) {
    new IntersectionObserver((entries) => {
      entries.forEach((entry) => banner.classList.toggle("banner--still", !entry.isIntersecting));
    }).observe(banner);
  }
  if (banner && window.matchMedia(motion).matches) {
    const wake = (event) => {
      // a mouse wakes it by moving (the page scrolling under a resting cursor
      // reports a move with no movement); a finger or a pen by touching down
      const mouse = event.pointerType === "mouse";
      const moved = event.type === "pointermove" && (event.movementX || event.movementY);
      if (mouse ? !moved : event.type !== "pointerdown") return;
      banner.removeEventListener("pointermove", wake);
      banner.removeEventListener("pointerdown", wake);
      import("/cat.js").then((art) => art.start(banner, event)).catch(() => {});
    };
    banner.addEventListener("pointermove", wake, { passive: true });
    banner.addEventListener("pointerdown", wake, { passive: true });
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

  // The rail follows the reader: the meter says how far down the article they
  // are, and the contents mark the section they are in. Both go by a reading
  // line 30% down the screen. Near the end of a page the article can't scroll
  // that far up, so the meter counts the furthest the page scrolls as the end,
  // and the marking line slides down to the foot of the screen over the last
  // screenful of scrolling, so the closing sections still get their turn.
  const article = document.querySelector(".blog-article");
  const progress = document.querySelector(".rail__progress");
  const sections = Array.from(document.querySelectorAll('.rail__list a[href^="#"]'))
    .map((link) => ({ link, heading: document.getElementById(link.getAttribute("href").slice(1)) }))
    .filter((section) => section.heading);
  if (article && (progress || sections.length)) {
    const cells = 12;
    let meter = null;
    let stats = null;
    let minutes = 0;
    let count = "";
    if (progress) {
      minutes = parseInt(progress.dataset.minutes, 10) || 0;
      const words = (article.textContent || "").trim().split(/\s+/).length;
      count = words >= 1000 ? (words / 1000).toFixed(1) + "k" : String(words);
      meter = document.createElement("span");
      stats = document.createElement("span");
      meter.className = "progress__meter";
      stats.className = "progress__hi";
      progress.append("read ", meter, "\n", stats);
    }

    let current = null;
    const mark = (link) => {
      if (link === current) return;
      if (current) current.removeAttribute("aria-current");
      if (link) link.setAttribute("aria-current", "location");
      current = link;
      // a contents list taller than the screen scrolls inside the rail; keep
      // the marked line in it, with a line or two of room either side
      if (!link || !fold || fold.scrollHeight <= fold.clientHeight) return;
      const box = fold.getBoundingClientRect();
      const row = link.getBoundingClientRect();
      const room = row.height * 2;
      if (row.top < box.top + room) fold.scrollTop -= box.top + room - row.top;
      else if (row.bottom > box.bottom - room) fold.scrollTop += row.bottom - (box.bottom - room);
    };

    // A jump from the contents (or any link to a heading) marks that heading
    // even when the page can't scroll it up to the line, and holds the mark
    // until the reader scrolls on after the jump has come to rest.
    let pinned = false;
    let moving = 0;
    const rest = () => {
      window.clearTimeout(moving);
      moving = window.setTimeout(() => {
        moving = 0;
      }, 200);
    };
    const pin = (id) => {
      const section = sections.find((entry) => entry.heading.id === id);
      if (!section) return;
      pinned = true;
      mark(section.link);
      rest();
    };
    // the heading a #hash names (a malformed escape is taken as it stands)
    const named = () => {
      const hash = window.location.hash.slice(1);
      try {
        return decodeURIComponent(hash);
      } catch {
        return hash;
      }
    };
    sections.forEach(({ link, heading }) => link.addEventListener("click", () => pin(heading.id)));
    window.addEventListener("hashchange", () => pin(named()));

    let queued = false;
    const paint = () => {
      queued = false;
      const view = window.innerHeight;
      const y = window.scrollY;
      const end = Math.max(0, document.documentElement.scrollHeight - view);
      if (meter) {
        const box = article.getBoundingClientRect();
        const start = Math.max(0, box.top + y - view * 0.3);
        const finish = Math.min(end, box.bottom + y - view * 0.3);
        const fraction = finish > start ? Math.min(1, Math.max(0, (y - start) / (finish - start))) : Number(y >= finish);
        const filled = Math.round(fraction * cells);
        meter.textContent = "\u2593".repeat(filled) + "\u2591".repeat(cells - filled) + " " + Math.round(fraction * 100) + "%";
        const left = Math.max(0, Math.ceil(minutes * (1 - fraction)));
        stats.textContent = (left ? left + " min left" : "done") + " // " + count + " words";
      }
      if (pinned || !sections.length) return;
      // (a page that scrolls less than a screen slides it over what it has)
      const line = view * (0.3 + 0.7 * Math.max(0, 1 - (end - y) / (Math.min(view, end) || 1)));
      let found = null;
      for (const { link, heading } of sections) {
        if (heading.getBoundingClientRect().top > line) break;
        found = link;
      }
      mark(found);
    };
    const request = () => {
      if (queued) return;
      queued = true;
      window.requestAnimationFrame(paint);
    };
    window.addEventListener(
      "scroll",
      () => {
        if (pinned && !moving) pinned = false;
        else if (pinned) rest();
        request();
      },
      { passive: true },
    );
    window.addEventListener("resize", request);
    // images and late fonts change the article's height without a scroll
    if ("ResizeObserver" in window) new ResizeObserver(request).observe(article);
    paint();
    // arriving on a link to a heading that is on screen marks that heading
    const target = sections.find((entry) => entry.heading.id === named());
    if (target) {
      const top = target.heading.getBoundingClientRect().top;
      if (top >= 0 && top < window.innerHeight) pin(target.heading.id);
    }
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

    // A spectrum in dots, drawn like the cat at the top: low bars of dots in
    // the earth's blue on a floor of small dim ones. It isn't the song's real
    // sound (spotify no longer shares that): the bars sway slowly and lift a
    // little on a beat taken from the track's place in the song, so they pause
    // with it and settle flat when it stops. A small canvas, redrawn only when
    // a bar gains or loses a dot, and only on screen.
    const viz = box.querySelector(".now__viz");
    const canvas = viz && viz.querySelector("canvas");
    const pen = canvas && canvas.getContext("2d");
    const ROWS = 4;
    let ink = null; // the floor's and the bars' colours, from the stylesheet
    let cell = 6; // CSS pixels a dot's square
    let scale = 1;
    const calm = window.matchMedia("(prefers-reduced-motion: reduce)");
    let columns = 0;
    let bars = [];
    let shown = ""; // the bar heights on the canvas now
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
      if (!viz.clientWidth) return;
      const style = window.getComputedStyle(viz);
      ink = ["--rest", "--bar"].map((name) => style.getPropertyValue(name).trim());
      cell = viz.clientHeight / ROWS;
      scale = Math.min(3, window.devicePixelRatio || 1);
      const width = Math.round(viz.clientWidth * scale);
      const height = Math.round(viz.clientHeight * scale);
      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width;
        canvas.height = height;
        shown = "";
      }
      // as many bands as fit with the last dot whole (a dot reaches 1.05 cells in)
      const next = Math.max(12, Math.floor(viz.clientWidth / cell - 0.05));
      if (next === columns) return;
      columns = next;
      bars = new Array(columns).fill(0);
      shown = "";
    };
    const step = (settle) => {
      const playing = box.classList.contains("now--playing");
      const t = elapsed();
      const beat = (t / 60000) * bpm;
      const kick = Math.exp(-(beat % 1) * 3);
      for (let c = 0; c < columns; c += 1) {
        const x = c / (columns - 1);
        // a slow swell, silent in places and falling off to the top end; each
        // band keeps a reach of its own, and the beat lifts only the low end
        const swell = Math.max(0, noise(c * 0.32, t * 0.0005) - 0.4) / 0.6;
        const level =
          swell * (1.3 - 0.45 * x) * (0.7 + 0.6 * hash(c * 7.3 + 1)) + 0.35 * kick * Math.max(0, 1 - x * 2.5);
        const target = playing ? Math.min(1, level) : 0;
        // eased both ways, so a bar climbs and sinks a dot at a time
        bars[c] = settle ? target : bars[c] + (target - bars[c]) * 0.3;
      }
    };
    // each dot as the cat's are: a "·" is 0.41 of its cell across, a "•" 0.6,
    // centred 0.75 cells in
    const dot = (c, row, big) => {
      const x = (c + 0.75) * cell * scale;
      const y = (ROWS - row + (big ? 0.4875 : 0.5475)) * cell * scale;
      const r = (big ? 0.3 : 0.205) * cell * scale;
      pen.moveTo(x + r, y);
      pen.arc(x, y, r, 0, Math.PI * 2);
    };
    const heights = () => bars.map((v) => Math.round(v * ROWS));
    const draw = () => {
      if (!ink || !columns) return;
      const now = heights();
      const key = now.join("");
      if (key === shown) return;
      shown = key;
      pen.clearRect(0, 0, canvas.width, canvas.height);
      // a small dim dot where a bar is down to nothing, the bars over the rest
      const layers = [[], []];
      now.forEach((height, c) => {
        if (!height) layers[0].push(c, 1);
        for (let row = 1; row <= height; row += 1) layers[1].push(c, row);
      });
      layers.forEach((cells, k) => {
        pen.globalAlpha = k ? 1 : 0.6;
        pen.fillStyle = ink[k];
        pen.beginPath();
        for (let n = 0; n < cells.length; n += 2) dot(cells[n], cells[n + 1], k > 0);
        pen.fill();
      });
    };
    const moving = () =>
      visible && !document.hidden && (box.classList.contains("now--playing") || heights().some(Boolean));
    const animate = () => {
      frame = 0;
      step(false);
      draw();
      if (moving()) frame = window.setTimeout(animate, 100);
    };
    const wake = () => {
      if (!pen) return;
      fit();
      if (calm.matches) step(true);
      if (!calm.matches && !frame && moving()) animate();
      else draw();
    };
    // a new width refits the bands; under reduced motion the still frame is
    // drawn again rather than left flat
    if (viz && "ResizeObserver" in window) new ResizeObserver(() => wake()).observe(viz);

    // nothing to show: the pane goes, the room kept for it goes, and nothing in
    // it keeps moving; a later answer brings it back
    const off = () => {
      box.hidden = true;
      box.classList.add("now--off");
      box.classList.remove("now--playing");
    };
    const render = (note) => {
      const data = state && state.data;
      if (!data || !data.track) {
        off();
        return;
      }
      box.classList.remove("now--off");
      const track = data.track;
      const playing = running() && !note;
      box.classList.toggle("now--playing", playing);
      title.textContent = lower(track.title);
      title.title = title.textContent;
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
          off();
          stop();
          loading = false;
          return;
        }
      }
      loading = false;
      schedule();
    };
    const sync = () => {
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
    const spriteRows = (rows, left) => {
      if (!left) return rows;
      const mirrored = rows.map((row) => mirrorRow(row));
      const max = Math.max.apply(null, mirrored.map((row) => row.width));
      return mirrored.map((row) => row.html + " ".repeat(max - row.width));
    };
    // A ship is a small picture, set like the city's layers: an SVG of its
    // glyphs, 6 units a column and 10 a line, the baseline 8.6 down.
    const shipSvg = (rows) => {
      const cols = Math.max.apply(null, rows.map((row) => Array.from(row.replace(/<[^>]+>/g, "")).length));
      const lines = rows.map(
        (row, r) =>
          '<tspan x="0" y="' + (r * 10 + 8.6).toFixed(1) + '">' +
          row.replace(/<span /g, "<tspan ").replace(/<\/span>/g, "</tspan>") +
          "</tspan>",
      );
      return (
        '<svg viewBox="0 0 ' + cols * 6 + " " + rows.length * 10 + '" style="--cols: ' + cols +
        "; --rows: " + rows.length + '"><text xml:space="preserve">' + lines.join("") + "</text></svg>"
      );
    };
    const between = (low, high) => low + Math.random() * (high - low);

    cities.forEach((city) => {
      const lane = city.querySelector(".city__ships");
      const state = { alive: 0, timer: 0, paused: false, visible: false };
      const spawn = () => {
        state.timer = 0;
        if (!lane || state.paused || !state.visible) return;
        if (state.alive < 1) {
          const ship = document.createElement("div");
          const left = Math.random() < 0.5;
          const far = Math.random() < 0.45;
          const rows = padRows(sprites[Math.floor(Math.random() * sprites.length)]);
          ship.className = "ship" + (left ? " ship--left" : "") + (far ? " ship--far" : " ship--near");
          ship.setAttribute("aria-hidden", "true");
          ship.innerHTML = shipSvg(spriteRows(rows, left));
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
