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

  // A hotkey, w, mirrors the writing link in the header. It stays out of the
  // way of form fields and of any shortcut with a modifier.
  const hotkeys = { w: "/blogs/" };
  document.addEventListener("keydown", (event) => {
    if (event.metaKey || event.ctrlKey || event.altKey || event.shiftKey) return;
    const target = event.target;
    if (
      target instanceof HTMLElement &&
      (target.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName))
    ) {
      return;
    }
    const href = hotkeys[event.key];
    if (href && window.location.pathname !== href) window.location.assign(href);
  });

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
  // last one played); this prints it in the rail and keeps the meter moving.
  document.querySelectorAll("[data-now]").forEach((box) => {
    const endpoint = box.dataset.now;
    const pre = box.querySelector(".now__pre");
    const label = box.querySelector(".now__state");
    if (!endpoint || !pre || !label || !window.fetch) return;
    // Characters per line follow the rail's width and the block's font size.
    const columns = () => {
      const size = parseFloat(window.getComputedStyle(pre).fontSize) || 12;
      return Math.max(20, Math.min(60, Math.floor(pre.clientWidth / (size * 0.6))));
    };
    const cells = 8;
    const lower = (value) => String(value || "").toLowerCase();
    const clip = (text, width) =>
      text.length > width ? text.slice(0, width - 2).trimEnd() + ".." : text;
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
    const node = (tag, className, text) => {
      const element = document.createElement(tag);
      if (className) element.className = className;
      element.textContent = text;
      return element;
    };
    let state = null;
    let meter = null;
    let timeLabel = null;
    let ticker = 0;
    let poller = 0;
    let failures = 0;
    let visible = false;

    const elapsed = () => {
      if (!state || !state.data.playing || state.data.progress_ms == null) return 0;
      const duration = state.data.track.duration_ms || 0;
      return Math.min(duration, state.data.progress_ms + (Date.now() - state.receivedAt));
    };
    const tick = () => {
      if (!state || !meter) return;
      const duration = state.data.track.duration_ms || 0;
      const done = elapsed();
      const filled = duration ? Math.round((done / duration) * cells) : 0;
      meter.textContent = "\u2593".repeat(filled) + "\u2591".repeat(cells - filled);
      timeLabel.textContent = " " + clock(done) + " / " + clock(duration) + " ";
      if (duration && done >= duration) load();
    };
    const render = () => {
      const data = state && state.data;
      if (!data || !data.track) {
        box.hidden = true;
        box.classList.add("now--off");
        return;
      }
      const track = data.track;
      box.hidden = false;
      pre.replaceChildren();
      const width = columns();
      label.textContent = data.playing
        ? "spotify // playing"
        : data.played_at
          ? "spotify // played " + ago(data.played_at)
          : "spotify // paused";
      box.classList.toggle("now--playing", Boolean(data.playing));
      const title = node(track.url ? "a" : "span", "now__title", clip(lower(track.title), width - 2));
      if (track.url) {
        title.href = track.url;
        title.rel = "noopener";
      }
      pre.append(node("span", "now__mark", data.playing ? "\u25b6 " : "\u25b7 "), title, "\n");
      // Artists always; the album only when the whole line fits the rail.
      const artists = lower((track.artists || []).join(", "));
      const withAlbum = track.album ? artists + " // " + lower(track.album) : artists;
      pre.append("  ", node("span", "now__meta", clip(withAlbum.length <= width - 2 ? withAlbum : artists, width - 2)));
      meter = null;
      if (data.playing && data.progress_ms != null && track.duration_ms) {
        meter = node("span", "now__meter", "");
        timeLabel = node("span", "", "");
        const eq = node("span", "now__eq", "");
        "\u2582\u2585\u2583\u2587".split("").forEach((glyph, index) => {
          const bar = node("span", "", glyph);
          bar.style.setProperty("--i", index);
          eq.append(bar);
        });
        pre.append("\n  ", meter, timeLabel, eq);
        tick();
      }
      box.hidden = false;
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
        render();
        label.textContent = "spotify // syncing";
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
        thrust("▪═") + hull("▐") + hi("▤") + hull("▌▐") + hi("▤") + hull("▌▐") + hi("▤") + hull("▌") + "▐█" + hi("▙") + hull("▶"),
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
