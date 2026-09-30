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
      if (!lane) return;
      const state = { alive: 0, timer: 0, paused: false, visible: false, glitchTimer: 0, shakeTimer: 0 };
      const maxShips = () => (window.innerWidth > 1400 ? 3 : 2);
      const spawn = () => {
        state.timer = 0;
        if (state.paused || !state.visible) return;
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
          if (!state.timer) schedule(state.alive ? between(5000, 9000) : 1500);
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
