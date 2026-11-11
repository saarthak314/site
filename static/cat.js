// A simple wave through the home banner's dots, under the cursor or a finger.
//
// site.js imports this the first time the mouse really moves over the banner
// (not when the page scrolls under a resting cursor) or a finger touches it,
// so a page load only ever pays for the picture. On start a canvas is laid over
// the SVG, which stays where it is, invisible but still labelled for screen
// readers. The twinkling stars are a separate layer above, and keep twinkling
// either way.
//
// The canvas keeps a still copy of the art, each dot the same circle at the
// same place as in the SVG, so at rest the two look the same. A frame copies
// tiles back from it and draws only the dots the wave carries.
//
// Around the cursor the dots ride a sine wave that rolls sideways: crests
// lift the dots and swell them, troughs let them sink. Moving the mouse stirs
// the water; scrolling does not. On a touch screen a tap stirs it where the
// finger lands, holding the finger down keeps it stirred, and dragging sideways
// carries the wave along (a vertical drag still scrolls the page). When the
// mouse stops or leaves, or the finger lifts, the wave settles and the loop
// sleeps. A frame only touches the tiles under the wave,
// and a moment after the mouse leaves the canvas lets go of its pixels and
// the text returns.

// Each dot, in cells, as the SVG draws it: its radius and how far down its
// cell its centre sits ("·" and "•" as JetBrains Mono sets them on the grid).
// Across, every dot is centred 0.75 cells into its cell. The radius is only a
// fallback: the stylesheet's stroke widths are read back, since small screens
// draw the dots larger.
const SMALL = { r: 0.205, y: 0.5475 };
const LARGE = { r: 0.3, y: 0.4875 };
const ACROSS = 0.75;
// a filled circle comes out a shade heavier than the SVG's round cap of the
// same radius; this much smaller and the two match
const INK = 0.977;

// The water, in cells and seconds.
const WAVE = 16; // distance from one crest to the next
const FLOW = 12; // how fast the crests roll sideways
const WIDE = 13; // how far the wave reaches either side of the cursor...
const TALL = 6; // ...and above and below it, before it fades out
const LIFT = 1; // how high a crest lifts a dot
const SWELL = 0.8; // how much a crest grows a dot (a trough shrinks it)
const FOLLOW = 0.06; // the wave's centre trails the cursor by about this long
const STIR = 0.25; // a movement keeps stirring the water for about this long
const TAP = 0.5; // a tap keeps it stirred for this long before it settles
const CALM = 0.35; // the wave rises and settles over about this long
const STILL = 0.04; // a dot moved less than this (in cells) is left as drawn
const REACH = 1.4; // the farthest a dot may travel
const MARGIN = 2; // cells around a dot that its travel can touch
const TILE = 8; // the canvas repaints in squares of this many cells
const TAU = Math.PI * 2;

export function start(banner, event) {
  const art = banner.querySelector("svg.cat");
  if (!art || banner.querySelector(".cat__live")) return;
  const view = art.viewBox.baseVal;
  const cols = view.width;
  const rows = view.height;
  if (!cols || !rows) return;

  // Read the dots back out of the paths: a path is one colour and size, and
  // each "M x y" or "m dx dy" in it is one dot.
  const tones = [];
  const paths = [];
  const found = [];
  art.querySelectorAll("path").forEach((path) => {
    const tone = tones.length;
    tones.push(window.getComputedStyle(path).stroke);
    paths.push(path);
    const big = path.classList.contains("l") ? 1 : 0;
    const drop = (big ? LARGE : SMALL).y;
    let x = 0;
    let y = 0;
    const moves = /([Mm])(-?[\d.]+)[ ,](-?[\d.]+)/g;
    for (let m = moves.exec(path.getAttribute("d")); m; m = moves.exec(path.getAttribute("d"))) {
      x = m[1] === "M" ? Number(m[2]) : x + Number(m[2]);
      y = m[1] === "M" ? Number(m[3]) : y + Number(m[3]);
      found.push(Math.round(x - ACROSS), Math.round(y - drop), big, tone);
    }
  });
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
    if (hx[i] >= 0 && hx[i] < cols && hy[i] >= 0 && hy[i] < rows) grid[hy[i] * cols + hx[i]] = i;
  }
  // Each colour's dot radius, in cells: half its stroke width as drawn now.
  const radius = new Float32Array(tones.length);
  const measure = () => {
    paths.forEach((path, k) => {
      const stroke = Number.parseFloat(window.getComputedStyle(path).strokeWidth);
      radius[k] = stroke > 0 ? stroke / 2 : (path.classList.contains("l") ? LARGE : SMALL).r;
    });
  };
  const tilesAcross = Math.ceil(cols / TILE);
  const tilesDown = Math.ceil(rows / TILE);
  const dirty = new Uint8Array(tilesAcross * tilesDown);

  const canvas = document.createElement("canvas");
  canvas.className = "cat__live";
  canvas.setAttribute("aria-hidden", "true");
  canvas.hidden = true;
  const context = canvas.getContext("2d");
  const still = document.createElement("canvas"); // the art at rest
  const stillContext = still.getContext("2d");
  if (!context || !stillContext) return;
  const buckets = tones.map(() => []);

  // Geometry, set by fit(), in device pixels: the size of a cell, and where
  // the art's corner falls inside the canvas (the canvas sits on whole device
  // pixels; the art need not).
  let ratio = 1;
  let cell = 1; // device pixels per cell
  let offsetX = 0;
  let offsetY = 0;

  const centreX = (i) => offsetX + (hx[i] + ACROSS) * cell;
  const centreY = (i) => offsetY + (hy[i] + (large[i] ? LARGE : SMALL).y) * cell;

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
        const r = radius[k] * cell * swell * INK;
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

  // Lay the canvas over the art on whole device pixels, so nothing is
  // resampled, and copy the still art onto it.
  let across = 1; // CSS pixels per cell
  let width = 0;
  let live = false;
  const fit = () => {
    const box = art.getBoundingClientRect();
    if (!live || box.width === width) return;
    width = box.width;
    const frame = art.parentElement.getBoundingClientRect();
    // as sharp as the screen: phones are 3x, and a 2x canvas there blurs
    ratio = Math.min(3, window.devicePixelRatio || 1);
    across = box.width / cols;
    cell = across * ratio;
    const left = (box.left - frame.left) * ratio;
    const top = (box.top - frame.top) * ratio;
    offsetX = left - Math.floor(left);
    offsetY = top - Math.floor(top);
    canvas.width = Math.ceil(box.width * ratio + offsetX);
    canvas.height = Math.ceil(box.height * ratio + offsetY);
    canvas.style.left = `${Math.floor(left) / ratio}px`;
    canvas.style.top = `${Math.floor(top) / ratio}px`;
    canvas.style.width = `${canvas.width / ratio}px`;
    canvas.style.height = `${canvas.height / ratio}px`;
    measure();
    drawStill();
    context.drawImage(still, 0, 0);
  };
  art.after(canvas); // under the twinkling stars, which come next
  new ResizeObserver(fit).observe(art);

  // The two look the same, so swapping between them never shows.
  let idle = 0;
  const show = () => {
    window.clearTimeout(idle);
    if (live) return;
    live = true;
    width = 0;
    fit();
    canvas.hidden = false;
    art.classList.add("cat--live");
  };
  const hide = () => {
    live = false;
    art.classList.remove("cat--live");
    canvas.hidden = true;
    canvas.width = 0;
    canvas.height = 0;
    still.width = 0;
    still.height = 0;
  };

  let pointer = null; // where the cursor is, in cells, while it is over the art
  let centre = null; // where the wave is: it trails the cursor
  let stir = 0; // 1 just after the mouse moves, falling back to 0
  const fingers = new Set(); // the fingers down on the banner
  let touching = false; // any finger is
  let hold = 0; // the clock time a tap stops stirring the water
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
    stir = touching || clock < hold ? 1 : stir * Math.exp(-dt / STIR);
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
      const x = Math.floor(offsetX + (t % tilesAcross) * TILE * cell);
      const y = Math.floor(offsetY + Math.floor(t / tilesAcross) * TILE * cell);
      const w = Math.min(canvas.width, Math.ceil(offsetX + ((t % tilesAcross) + 1) * TILE * cell)) - x;
      const h = Math.min(canvas.height, Math.ceil(offsetY + (Math.floor(t / tilesAcross) + 1) * TILE * cell)) - y;
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
    const box = art.getBoundingClientRect();
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

  // A finger (or a pen) stirs the water where it lands, and keeps stirring it
  // while it stays down.
  const touch = (input) => {
    fingers.add(input.pointerId);
    touching = true;
    stirAt(input);
    hold = clock + TAP;
  };
  const lift = (up) => {
    if (up.pointerType === "mouse") return;
    fingers.delete(up.pointerId);
    if (fingers.size) return;
    touching = false;
    pointer = null;
    wake();
  };
  banner.addEventListener(
    "pointerdown",
    (down) => {
      if (down.pointerType !== "mouse") touch(down);
    },
    { passive: true },
  );
  banner.addEventListener("pointerup", lift);
  banner.addEventListener("pointercancel", lift);
  banner.addEventListener(
    "pointermove",
    (move) => {
      if (move.pointerType !== "mouse") {
        if (touching) stirAt(move);
        return;
      }
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
  // site.js starts this on a real move or a touch; the cursor may have left,
  // or the finger lifted, since. A touch gets its wave either way, settling
  // where the finger landed.
  if (event.pointerType !== "mouse") {
    touch(event);
    fingers.clear();
    touching = false;
    pointer = null;
  } else if (banner.matches(":hover")) stirAt(event);
}
