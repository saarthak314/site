// A simple wave through the home banner's dots, under the cursor.
//
// site.js imports this the first time the mouse really moves over the banner
// (not when the page scrolls under a resting cursor), so a page load, and
// every phone, only ever pays for the text. On start a canvas is laid over
// the text, which stays where it is, invisible but still labelled for screen
// readers. The twinkling stars are a separate layer above, and keep twinkling
// either way.
//
// The canvas keeps a still copy of the art, each dot a circle of the glyph's
// exact size and place (circles match the text more closely than the canvas's
// own text drawing, which macOS thickens), so at rest the two look the same.
// A frame copies tiles back from it and draws only the dots the wave carries.
//
// Around the cursor the dots ride a sine wave that rolls sideways: crests
// lift the dots and swell them, troughs let them sink. Moving the mouse stirs
// the water; scrolling does not. When the mouse stops or leaves, the wave
// settles and the loop sleeps. A frame only touches the tiles under the wave,
// and a moment after the mouse leaves the canvas lets go of its pixels and
// the text returns.

// Each glyph's ink, in em: its radius and how high its centre sits above the
// baseline (JetBrains Mono, 1000 units to the em). Horizontally the ink is
// centred 0.3em into the advance. Where the baselines fall is measured from the
// text itself, since the browser rounds font metrics and line boxes.
const SMALL = { glyph: "·", r: 0.082, lift: 0.341 }; // 164 units across
const LARGE = { glyph: "•", r: 0.12, lift: 0.365 }; // 240 units across

// The water, in cells and seconds.
const WAVE = 16; // distance from one crest to the next
const FLOW = 12; // how fast the crests roll sideways
const WIDE = 13; // how far the wave reaches either side of the cursor...
const TALL = 6; // ...and above and below it, before it fades out
const LIFT = 1; // how high a crest lifts a dot
const SWELL = 0.8; // how much a crest grows a dot (a trough shrinks it)
const FOLLOW = 0.06; // the wave's centre trails the cursor by about this long
const STIR = 0.25; // a movement keeps stirring the water for about this long
const CALM = 0.35; // the wave rises and settles over about this long
const STILL = 0.04; // a dot moved less than this (in cells) is left as drawn
const REACH = 1.4; // the farthest a dot may travel
const MARGIN = 2; // cells around a dot that its travel can touch
const TILE = 8; // the canvas repaints in squares of this many cells
const TAU = Math.PI * 2;

export function start(banner, event) {
  const pre = banner.querySelector(".cat");
  if (!pre || banner.querySelector(".cat__live")) return;
  const cols = Number(pre.style.getPropertyValue("--cols"));
  if (!cols) return;

  // Read the dots back out of the text: one per "·" or "•", with its colour.
  const tones = [];
  const toneOf = new Map();
  const toneFor = (element) => {
    const key = element === pre ? "" : element.className;
    let index = toneOf.get(key);
    if (index === undefined) {
      index = tones.length;
      toneOf.set(key, index);
      tones.push(window.getComputedStyle(element).color);
    }
    return index;
  };
  const found = [];
  let col = 0;
  let row = 0;
  const read = (text, tone) => {
    for (const glyph of text) {
      if (glyph === "\n") {
        row += 1;
        col = 0;
        continue;
      }
      if (glyph === SMALL.glyph || glyph === LARGE.glyph) {
        found.push(col, row, glyph === LARGE.glyph ? 1 : 0, tone);
      }
      col += 1;
    }
  };
  pre.childNodes.forEach((node) => {
    read(node.textContent, toneFor(node.nodeType === Node.TEXT_NODE ? pre : node));
  });
  const rows = row + 1;
  const count = found.length / 4;
  const hx = new Float32Array(count);
  const hy = new Float32Array(count);
  const large = new Uint8Array(count);
  const tone = new Uint8Array(count);
  const oy = new Float32Array(count); // how far the water has lifted each dot
  const grow = new Float32Array(count); // and how much it has swollen
  const seen = new Uint32Array(count); // the frame a dot was last visited
  const grid = new Int32Array(cols * rows).fill(-1);
  for (let i = 0; i < count; i += 1) {
    hx[i] = found[i * 4];
    hy[i] = found[i * 4 + 1];
    large[i] = found[i * 4 + 2];
    tone[i] = found[i * 4 + 3];
    grid[hy[i] * cols + hx[i]] = i;
  }
  const tilesAcross = Math.ceil(cols / TILE);
  const tilesDown = Math.ceil(rows / TILE);
  const dirty = new Uint8Array(tilesAcross * tilesDown);

  const canvas = document.createElement("canvas");
  canvas.className = "cat__live";
  canvas.setAttribute("aria-hidden", "true");
  canvas.hidden = true;
  const context = canvas.getContext("2d");
  const still = document.createElement("canvas"); // the art at rest, as text
  const stillContext = still.getContext("2d");
  if (!context || !stillContext) return;
  const buckets = tones.map(() => []);

  // Geometry, set by fit(), in device pixels: each row's baseline, and where
  // each glyph's ink sits relative to its cell and baseline.
  const baseline = new Float32Array(rows);
  let ratio = 1;
  let cell = 1; // device pixels per cell, across
  let size = 1; // the text's font size, in device pixels

  const centreX = (i) => hx[i] * cell + 0.3 * size;
  const centreY = (i) => baseline[hy[i]] - (large[i] ? LARGE : SMALL).lift * size;

  // Dots as circles, one fill per colour: at rest for the still copy, or
  // where the water has carried them.
  const paint = (target, indices, carried) => {
    buckets.forEach((bucket) => {
      bucket.length = 0;
    });
    for (const i of indices) buckets[tone[i]].push(i);
    buckets.forEach((bucket, k) => {
      if (!bucket.length) return;
      target.fillStyle = tones[k];
      target.beginPath();
      for (const i of bucket) {
        const swell = carried ? Math.min(2, Math.max(0.25, 1 + grow[i])) : 1;
        const lift = carried ? Math.max(-REACH, Math.min(REACH, oy[i])) * cell : 0;
        const r = (large[i] ? LARGE : SMALL).r * size * swell;
        const x = centreX(i);
        const y = centreY(i) + lift;
        target.moveTo(x + r, y);
        target.arc(x, y, r, 0, TAU);
      }
      target.fill();
    });
  };
  const everyDot = Array.from({ length: count }, (_, i) => i);
  const drawStill = () => {
    still.width = canvas.width;
    still.height = canvas.height;
    paint(stillContext, everyDot, false);
  };

  // Where the browser actually put each line: the box of its first character
  // (one read for every line, no layout in between). The browser snaps lines
  // and baselines in ways no formula here would match exactly.
  const lineTops = (across) => {
    const tops = new Array(rows).fill(null);
    const range = document.createRange();
    const walker = document.createTreeWalker(pre, NodeFilter.SHOW_TEXT);
    let line = 0;
    let fresh = true;
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      for (let k = 0; k < node.data.length; k += 1) {
        if (node.data[k] === "\n") {
          line += 1;
          fresh = true;
        } else if (fresh) {
          range.setStart(node, k);
          range.setEnd(node, k + 1);
          tops[line] = range.getBoundingClientRect().top;
          fresh = false;
        }
      }
    }
    // an empty line has no character to measure; take it from its neighbours
    const known = tops.flatMap((top, r) => (top === null ? [] : [r]));
    for (let r = 0; r < rows; r += 1) {
      if (tops[r] !== null) continue;
      const before = known.filter((k) => k < r).pop();
      const after = known.find((k) => k > r);
      const a = before ?? after;
      const b = after ?? before;
      tops[r] = a === b ? tops[a] + (r - a) * across : tops[a] + ((tops[b] - tops[a]) * (r - a)) / (b - a);
    }
    return tops;
  };
  // A zero-size box set on the first line sits on its baseline: how far that
  // is below the top of the line's text is the same on every line.
  const baselineDrop = (top) => {
    const mark = document.createElement("span");
    mark.style.cssText = "display:inline-block;width:0;height:0";
    pre.prepend(mark);
    const y = mark.getBoundingClientRect().top;
    mark.remove();
    return y - top;
  };

  // Lay the canvas exactly over the text, in whole device pixels so nothing
  // is resampled, and copy the still art onto it.
  let across = 1; // CSS pixels per cell
  let width = 0;
  let live = false;
  const fit = () => {
    const box = pre.getBoundingClientRect();
    if (!live || box.width === width) return;
    width = box.width;
    const frame = pre.parentElement.getBoundingClientRect();
    const style = window.getComputedStyle(pre);
    ratio = Math.min(2, window.devicePixelRatio || 1);
    across = box.width / cols;
    cell = across * ratio;
    size = parseFloat(style.fontSize) * ratio;
    const tops = lineTops(across);
    const drop = baselineDrop(tops[0]);
    // text is painted on whole CSS pixels of the page; so are these baselines
    for (let r = 0; r < rows; r += 1) {
      const y = Math.round(tops[r] + drop + window.scrollY) - window.scrollY;
      baseline[r] = (y - box.top) * ratio;
    }
    canvas.width = Math.ceil(box.width * ratio);
    canvas.height = Math.ceil(box.height * ratio);
    canvas.style.left = `${box.left - frame.left}px`;
    canvas.style.top = `${box.top - frame.top}px`;
    canvas.style.width = `${canvas.width / ratio}px`;
    canvas.style.height = `${canvas.height / ratio}px`;
    drawStill();
    context.drawImage(still, 0, 0);
  };
  pre.after(canvas); // under the twinkling stars, which come next
  new ResizeObserver(fit).observe(pre);

  // The two look the same, so swapping between them never shows.
  let idle = 0;
  const show = () => {
    window.clearTimeout(idle);
    if (live) return;
    live = true;
    width = 0;
    fit();
    canvas.hidden = false;
    pre.classList.add("cat--live");
  };
  const hide = () => {
    live = false;
    pre.classList.remove("cat--live");
    canvas.hidden = true;
    canvas.width = 0;
    canvas.height = 0;
    still.width = 0;
    still.height = 0;
  };

  let pointer = null; // where the cursor is, in cells, while it is over the art
  let centre = null; // where the wave is: it trails the cursor
  let stir = 0; // 1 just after the mouse moves, falling back to 0
  let strength = 0; // how tall the wave is now, following the stirring
  let clock = 0; // seconds the water has been moving, for the crests' phase
  let last = 0;
  let moved = []; // dots the water carried last frame
  let tick = 0;
  let raf = 0;

  const markTiles = (i) => {
    // a dot's travel can reach MARGIN cells past its own; mark those tiles
    const left = Math.floor(Math.max(0, hx[i] - MARGIN) / TILE);
    const right = Math.floor(Math.min(cols - 1, hx[i] + MARGIN) / TILE);
    const up = Math.floor(Math.max(0, hy[i] - MARGIN) / TILE);
    const down = Math.floor(Math.min(rows - 1, hy[i] + MARGIN) / TILE);
    for (let ty = up; ty <= down; ty += 1) {
      for (let tx = left; tx <= right; tx += 1) dirty[ty * tilesAcross + tx] = 1;
    }
  };

  const frame = (now) => {
    raf = 0;
    tick += 1;
    const dt = last ? Math.min(0.05, (now - last) / 1000) : 1 / 60;
    last = now;
    clock += dt;
    stir *= Math.exp(-dt / STIR);
    strength += (stir - strength) * (1 - Math.exp(-dt / CALM));
    if (pointer && centre) {
      const pull = 1 - Math.exp(-dt / FOLLOW);
      centre.x += (pointer.x - centre.x) * pull;
      centre.y += (pointer.y - centre.y) * pull;
    }

    // Last frame's dots start from rest; the wave then carries whoever it reaches.
    for (const i of moved) {
      oy[i] = 0;
      grow[i] = 0;
      markTiles(i);
    }
    const carried = [];
    if (centre && strength > 0.01) {
      const reachX = WIDE * 2.2;
      const reachY = TALL * 2.2;
      const top = Math.max(0, Math.floor(centre.y - reachY));
      const bottom = Math.min(rows - 1, Math.ceil(centre.y + reachY));
      for (let r = top; r <= bottom; r += 1) {
        const dy = r + 0.5 - centre.y;
        const span = reachX * Math.sqrt(Math.max(0, 1 - (dy / reachY) ** 2));
        const c0 = Math.max(0, Math.ceil(centre.x - span - 0.75));
        const c1 = Math.min(cols - 1, Math.floor(centre.x + span - 0.75));
        for (let c = c0; c <= c1; c += 1) {
          const i = grid[r * cols + c];
          if (i < 0) continue;
          const dx = c + 0.75 - centre.x;
          const fade = Math.exp(-((dx / WIDE) ** 2) - (dy / TALL) ** 2);
          const height = strength * Math.sin((TAU * (c - FLOW * clock)) / WAVE) * fade;
          if (Math.abs(height * LIFT) < STILL) continue;
          if (seen[i] !== tick) {
            seen[i] = tick;
            carried.push(i);
          }
          oy[i] -= LIFT * height;
          grow[i] += SWELL * height;
        }
      }
    }
    for (const i of carried) markTiles(i);
    moved = carried;

    // Repaint the marked tiles from the still art (on whole device pixels),
    // lift the carried dots out of it, and draw them where the water has them.
    context.save();
    context.beginPath();
    let any = false;
    for (let t = 0; t < dirty.length; t += 1) {
      if (!dirty[t]) continue;
      dirty[t] = 0;
      any = true;
      const x = Math.floor((t % tilesAcross) * TILE * cell);
      const y = Math.floor(Math.floor(t / tilesAcross) * TILE * cell);
      const w = Math.min(canvas.width, Math.ceil(((t % tilesAcross) + 1) * TILE * cell)) - x;
      const h = Math.min(canvas.height, Math.ceil((Math.floor(t / tilesAcross) + 1) * TILE * cell)) - y;
      context.clearRect(x, y, w, h);
      context.drawImage(still, x, y, w, h, x, y, w, h);
      context.rect(x, y, w, h);
    }
    if (any && carried.length) {
      context.clip();
      const half = Math.ceil(0.4 * cell);
      for (const i of carried) {
        context.clearRect(Math.floor(centreX(i)) - half, Math.floor(centreY(i)) - half, half * 2 + 1, half * 2 + 1);
      }
      paint(context, carried, true);
    }
    context.restore();

    // Keep going while the water moves; then sleep until the mouse moves again.
    if (stir > 0.01 || strength > 0.01 || moved.length) raf = window.requestAnimationFrame(frame);
    else {
      last = 0;
      if (pointer) return;
      window.clearTimeout(idle);
      idle = window.setTimeout(hide, 1500);
    }
  };
  const wake = () => {
    if (!raf) raf = window.requestAnimationFrame(frame);
  };

  // Where a pointer is, in cells of the art.
  const cellAt = (input) => {
    const box = pre.getBoundingClientRect();
    return { x: (input.clientX - box.left) / across, y: (input.clientY - box.top) / across };
  };
  // Only a mouse that really moved stirs the water. When the page scrolls
  // under a resting cursor, the browser reports a move with no movement;
  // that only keeps track of where the cursor now is over the art.
  let screen = { x: event.screenX, y: event.screenY };
  const stirAt = (input) => {
    show();
    pointer = cellAt(input);
    if (!centre) centre = { ...pointer };
    stir = 1;
    wake();
  };

  banner.addEventListener(
    "pointermove",
    (move) => {
      if (move.pointerType !== "mouse") return;
      const moving = move.screenX !== screen.x || move.screenY !== screen.y;
      screen = { x: move.screenX, y: move.screenY };
      if (moving) stirAt(move);
      else if (live) pointer = cellAt(move);
    },
    { passive: true },
  );
  banner.addEventListener("pointerleave", () => {
    pointer = null;
    wake();
  });
  // site.js starts this on a real move; the cursor may have left since.
  if (banner.matches(":hover")) stirAt(event);
}
