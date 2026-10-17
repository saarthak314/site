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

  // Two hotkeys, w and a, mirror the header links. They stay out of the way of
  // form fields and of any shortcut with a modifier.
  const hotkeys = { w: "/blogs/", a: "/about/" };
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
        return;
      }
      const track = data.track;
      box.hidden = false;
      pre.replaceChildren();
      const width = columns();
      label.textContent = data.playing
        ? "spotify // playing"
        : data.played_at
          ? "spotify // last played " + ago(data.played_at)
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
    const load = async () => {
      if (poller) window.clearTimeout(poller);
      poller = 0;
      try {
        const response = await fetch(endpoint, { mode: "cors" });
        if (!response.ok) throw new Error(String(response.status));
        state = { data: await response.json(), receivedAt: Date.now() };
        failures = 0;
        render();
      } catch {
        failures += 1;
        if (failures >= 2) {
          box.hidden = true;
          stop();
          return;
        }
      }
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

  // The rail readout's vitals change on every visit: uptime days, load averages,
  // the meter percentages (bars redrawn to match) and the temperature.
  document.querySelectorAll(".rail__readout").forEach((readout) => {
    const between = (low, high) => low + Math.floor(Math.random() * (high - low + 1));
    const load = () => (0.08 + Math.random() * 1.4).toFixed(2);
    const ranges = { mem: [38, 86], swap: [0, 9], cpu: [3, 57] };
    const walker = document.createTreeWalker(readout, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach((node) => {
      let text = node.nodeValue;
      text = text.replace(/uptime (\d+)y(?: \d+d)?/g, (_, years) => "uptime " + years + "y " + between(1, 29) + "d");
      text = text.replace(/load \d+\.\d+ \d+\.\d+ \d+\.\d+/g, () => "load " + load() + " " + load() + " " + load());
      text = text.replace(/temp \d+c/g, () => "temp " + between(34, 61) + "c");
      text = text.replace(/(\w+) ([\u2593\u2591]+) (\d+)%/g, (_, word, bar) => {
        const range = ranges[word] || [5, 95];
        const percent = between(range[0], range[1]);
        const filled = Math.round((percent / 100) * bar.length);
        return word + " " + "\u2593".repeat(filled) + "\u2591".repeat(bar.length - filled) + " " + percent + "%";
      });
      if (text !== node.nodeValue) node.nodeValue = text;
    });
  });

  // Hex-dump glitches: on annotated pages a small patch of memory dump flashes in
  // a side margin for a second or two every so often. Never over the text, never
  // on narrow screens, never under reduced motion, and nothing while hidden.
  const calm = window.matchMedia("(prefers-reduced-motion: reduce)");
  if (document.body.classList.contains("page--annotated") && !calm.matches) {
    const rand = (n) => Math.floor(Math.random() * n);
    const hex = (digits) => {
      let out = "";
      for (let i = 0; i < digits; i += 1) out += "0123456789abcdef"[rand(16)];
      return out;
    };
    const glyphs = "..........MZ.@#$%&*+=-_/|<>?!~^";
    const dump = (lines, cols) => {
      let address = 0x80400000 + rand(0x4000) * 8;
      const rows = [];
      for (let i = 0; i < lines; i += 1) {
        let ascii = "";
        for (let c = 0; c < 8; c += 1) ascii += glyphs[rand(glyphs.length)];
        const row = address.toString(16).padStart(8, "0") + " " + hex(4) + " " + hex(4) + " " + hex(4) + " " + hex(4) + " " + ascii;
        rows.push(row.slice(0, cols));
        address += 8;
      }
      return rows.join("\n");
    };
    let timer = 0;
    const flash = () => {
      timer = 0;
      if (document.hidden) return;
      const margin = (window.innerWidth - 1080) / 2;
      if (margin >= 96) {
        const width = Math.min(220, margin - 28);
        const lines = 5 + rand(5);
        const height = lines * 15;
        const patch = document.createElement("pre");
        patch.className = "hexpatch";
        patch.setAttribute("aria-hidden", "true");
        patch.textContent = dump(lines, Math.floor(width / 6));
        const slack = Math.max(1, margin - width - 28);
        const left = Math.random() < 0.5 ? 14 + rand(slack) : window.innerWidth - margin + 14 + rand(slack);
        patch.style.left = left + "px";
        patch.style.top = 40 + rand(Math.max(1, window.innerHeight - height - 80)) + "px";
        patch.style.setProperty("--hold", (1 + Math.random()).toFixed(2) + "s");
        patch.addEventListener("animationend", () => patch.remove());
        document.body.appendChild(patch);
      }
      timer = window.setTimeout(flash, 6000 + rand(8000));
    };
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) {
        if (timer) window.clearTimeout(timer);
        timer = 0;
      } else if (!timer) {
        timer = window.setTimeout(flash, 2000 + rand(4000));
      }
    });
    timer = window.setTimeout(flash, 3000 + rand(5000));
  }

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
      // Scenes without a ship lane (the kernel panic) keep the lag patches and jolts.
      const lane = city.querySelector(".city__ships");
      const state = { alive: 0, timer: 0, paused: false, visible: false, glitchTimer: 0, shakeTimer: 0 };
      const maxShips = () => (window.innerWidth > 1400 ? 3 : 2);
      const spawn = () => {
        state.timer = 0;
        if (!lane || state.paused || !state.visible) return;
        if (state.alive < maxShips()) {
          const ship = document.createElement("pre");
          const left = Math.random() < 0.5;
          const far = Math.random() < 0.45;
          const rows = padRows(sprites[Math.floor(Math.random() * sprites.length)]);
          ship.className = "ship" + (left ? " ship--left" : "") + (far ? " ship--far" : " ship--near");
          ship.setAttribute("aria-hidden", "true");
          ship.innerHTML = spriteHtml(rows, left);
          ship.style.setProperty("--y", between(far ? 4 : 18, far ? 24 : 40).toFixed(1) + "%");
          ship.style.setProperty("--dur", (far ? between(24, 34) : between(14, 22)).toFixed(1) + "s");
          ship.style.setProperty("--scale", (far ? between(0.6, 0.8) : between(0.95, 1.2)).toFixed(2));
          ship.addEventListener("animationend", () => {
            ship.remove();
            state.alive -= 1;
          });
          lane.appendChild(ship);
          state.alive += 1;
        }
        schedule(between(5000, 9000));
      };
      // A rare whole-city jolt: three dropped frames, on/off/on/off.
      const jolt = () => {
        state.glitchTimer = 0;
        if (state.paused || !state.visible) return;
        [0, 60, 120].forEach((delay, index) => {
          window.setTimeout(() => city.classList.toggle("city--glitch", index % 2 === 0), delay);
        });
        window.setTimeout(() => city.classList.remove("city--glitch"), 180);
        state.glitchTimer = window.setTimeout(jolt, between(100000, 200000));
      };

      // Lag patches: one random rectangle of the skyline shakes for 600 ms, then
      // nothing animates until the next burst. Segments share an --i per patch.
      const patches = new Map();
      city.querySelectorAll(".glitch").forEach((segment) => {
        const key = segment.style.getPropertyValue("--i").trim().split(";")[0];
        if (!patches.has(key)) patches.set(key, []);
        patches.get(key).push(segment);
      });
      const patchKeys = Array.from(patches.keys());
      const shake = () => {
        state.shakeTimer = 0;
        if (state.paused || !state.visible || !patchKeys.length) return;
        const group = patches.get(patchKeys[Math.floor(Math.random() * patchKeys.length)]);
        group.forEach((segment) => segment.classList.add("glitch--on"));
        window.setTimeout(() => group.forEach((segment) => segment.classList.remove("glitch--on")), 700);
        state.shakeTimer = window.setTimeout(shake, between(8000, 14000));
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
          if (lane && !state.timer) schedule(state.alive ? between(5000, 9000) : 1500);
          if (!state.glitchTimer) state.glitchTimer = window.setTimeout(jolt, between(100000, 200000));
          if (!state.shakeTimer) state.shakeTimer = window.setTimeout(shake, between(3000, 8000));
          if (!state.budgeted && document.getAnimations) {
            state.budgeted = true;
            if (document.getAnimations().length > 100) city.classList.add("city--lean");
          }
        } else {
          if (state.timer) window.clearTimeout(state.timer);
          if (state.glitchTimer) window.clearTimeout(state.glitchTimer);
          if (state.shakeTimer) window.clearTimeout(state.shakeTimer);
          state.timer = 0;
          state.glitchTimer = 0;
          state.shakeTimer = 0;
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
