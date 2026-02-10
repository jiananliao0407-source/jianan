import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Streamlit Parkour", layout="centered")

st.title("🏃 Streamlit Parkour (Canvas)")

col1, col2, col3 = st.columns([1, 1, 1])
with col1:
    difficulty = st.slider("Difficulty", 1, 10, 4)
with col2:
    speed_mult = st.slider("Speed", 1.0, 3.0, 1.6, 0.1)
with col3:
    gravity = st.slider("Gravity", 0.6, 2.4, 1.2, 0.1)

st.caption("Controls: **Space / ↑** jump, **↓** fast drop. On mobile: tap to jump. Avoid red blocks, land on platforms.")

reset = st.button("🔄 Reset Game")

# Pass settings into the embedded JS game.
# To force reset, we change a key in the HTML (so Streamlit re-renders the component).
reset_key = 0
if reset:
    reset_key = st.session_state.get("reset_key", 0) + 1
    st.session_state["reset_key"] = reset_key
else:
    reset_key = st.session_state.get("reset_key", 0)

game_html = f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <style>
    body {{ margin: 0; padding: 0; background: #0b1020; font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial; }}
    .wrap {{
      width: 760px; max-width: 100%;
      margin: 0 auto; padding: 8px 0 0 0;
      color: #e8eefc;
    }}
    .hud {{
      display: flex; justify-content: space-between; align-items: baseline;
      padding: 8px 10px; margin: 6px 0 10px 0;
      background: rgba(255,255,255,0.06);
      border: 1px solid rgba(255,255,255,0.10);
      border-radius: 14px;
      backdrop-filter: blur(6px);
    }}
    .hud b {{ font-size: 18px; }}
    canvas {{
      width: 760px; max-width: 100%;
      aspect-ratio: 19 / 9;
      background: linear-gradient(180deg, #0b1020 0%, #111a33 50%, #121b2e 100%);
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 18px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.35);
      touch-action: manipulation;
    }}
    .help {{
      opacity: 0.85; font-size: 13px; padding: 8px 6px 12px 6px;
    }}
    .pill {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: 999px;
      background: rgba(255,255,255,0.08);
      border: 1px solid rgba(255,255,255,0.10);
      margin-left: 6px;
      font-size: 12px;
    }}
  </style>
</head>
<body>
  <div class="wrap" id="wrap-{reset_key}">
    <div class="hud">
      <div><b id="score">0</b> <span class="pill">score</span></div>
      <div>Best: <span id="best">0</span> <span class="pill">local</span></div>
      <div id="state" class="pill">RUNNING</div>
    </div>
    <canvas id="c" width="760" height="360"></canvas>
    <div class="help">
      Jump: <b>Space</b>/<b>↑</b>, Fast drop: <b>↓</b>, Restart: <b>R</b>.
      Tip: chain platform landings for safer runs.
    </div>
  </div>

<script>
(() => {{
  // --- Settings from Streamlit ---
  const DIFFICULTY = {difficulty};    // 1..10
  const SPEED_MULT = {speed_mult};    // 1.0..3.0
  const GRAVITY_MULT = {gravity};     // 0.6..2.4

  const canvas = document.getElementById('c');
  const ctx = canvas.getContext('2d');

  // Fit canvas to CSS size (crisp)
  function resizeForDPR() {{
    const dpr = window.devicePixelRatio || 1;
    const cssW = canvas.getBoundingClientRect().width;
    const cssH = canvas.getBoundingClientRect().height;
    canvas.width  = Math.round(cssW * dpr);
    canvas.height = Math.round(cssH * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }}
  resizeForDPR();
  window.addEventListener('resize', resizeForDPR);

  // --- Game constants ---
  const W = () => canvas.getBoundingClientRect().width;
  const H = () => canvas.getBoundingClientRect().height;

  const groundY = () => H() - 46;
  const baseSpeed = () => (220 + DIFFICULTY * 18) * SPEED_MULT; // px/s
  const gravity = () => 1600 * GRAVITY_MULT;                    // px/s^2
  const jumpVel = () => -560 - DIFFICULTY * 10;                 // px/s
  const fastDropVel = 900;

  // --- State ---
  let running = true;
  let tPrev = performance.now();
  let score = 0;
  let best = Number(localStorage.getItem("parkour_best") || "0");
  const scoreEl = document.getElementById('score');
  const bestEl = document.getElementById('best');
  const stateEl = document.getElementById('state');
  bestEl.textContent = best.toString();

  // Player
  const player = {{
    x: 120,
    y: groundY() - 34,
    w: 28,
    h: 34,
    vy: 0,
    onGround: false,
    onPlat: false,
    coyote: 0,
    jumpBuffer: 0
  }};

  // Platforms and obstacles arrays
  let platforms = [];
  let obstacles = [];

  function resetGame() {{
    running = true;
    score = 0;
    player.y = groundY() - player.h;
    player.vy = 0;
    player.onGround = false;
    player.onPlat = false;
    player.coyote = 0;
    player.jumpBuffer = 0;

    platforms = [];
    obstacles = [];

    // Seed a few platforms
    let x = 520;
    for (let i=0; i<4; i++) {{
      const p = makePlatform(x);
      platforms.push(p);
      x += p.w + rand(120, 260);
    }}

    // Seed obstacles
    let ox = 520;
    for (let i=0; i<3; i++) {{
      obstacles.push(makeObstacle(ox));
      ox += rand(240, 420);
    }}
  }}

  function rand(a,b) {{ return a + Math.random()*(b-a); }}

  function makePlatform(x) {{
    const h = rand(10, 16);
    const w = rand(110, 190);
    // Platform height: can be above ground a bit; difficulty increases variance
    const y = groundY() - rand(60, 150 + DIFFICULTY * 8);
    return {{
      x, y,
      w, h,
      // color-ish params
      glow: rand(0.2, 0.6)
    }};
  }}

  function makeObstacle(x) {{
    // Obstacles are on ground or on platform (rare)
    const w = rand(18, 32);
    const h = rand(24, 44) + DIFFICULTY * 2;
    const kind = Math.random() < (0.18 + DIFFICULTY*0.01) ? "tall" : "block";
    return {{
      x,
      y: groundY() - h,
      w, h,
      kind
    }};
  }}

  function spawnIfNeeded(dt) {{
    const speed = baseSpeed();

    // Platforms: keep a rolling set
    const rightEdge = W() + 260;
    while (platforms.length < 8) {{
      const last = platforms[platforms.length - 1];
      const nx = last ? last.x + last.w + rand(140, 280 - DIFFICULTY * 6) : rand(400, 700);
      platforms.push(makePlatform(nx));
    }}

    // Obstacles: density scales with difficulty
    const target = 6 + Math.floor(DIFFICULTY/2);
    while (obstacles.length < target) {{
      const last = obstacles[obstacles.length - 1];
      const minGap = Math.max(140, 320 - DIFFICULTY * 14);
      const nx = last ? last.x + rand(minGap, minGap + 260) : rand(460, 820);
      obstacles.push(makeObstacle(nx));
    }}

    // Cull off-screen
    platforms = platforms.filter(p => p.x + p.w > -120);
    obstacles = obstacles.filter(o => o.x + o.w > -120);
  }}

  // Input
  const keys = new Set();
  function pressJump() {{
    player.jumpBuffer = 0.12; // seconds
  }}
  window.addEventListener('keydown', (e) => {{
    if (e.code === 'Space' || e.code === 'ArrowUp') {{
      e.preventDefault();
      pressJump();
    }}
    if (e.code === 'KeyR') {{
      e.preventDefault();
      resetGame();
    }}
    keys.add(e.code);
  }});
  window.addEventListener('keyup', (e) => keys.delete(e.code));
  canvas.addEventListener('pointerdown', (e) => {{
    e.preventDefault();
    pressJump();
  }});

  // Collision helpers
  function aabb(ax, ay, aw, ah, bx, by, bw, bh) {{
    return ax < bx + bw && ax + aw > bx && ay < by + bh && ay + ah > by;
  }}

  function update(dt) {{
    if (!running) return;

    const speed = baseSpeed();

    // Score increases with time and difficulty
    score += dt * (10 + DIFFICULTY * 2.5);
    scoreEl.textContent = Math.floor(score).toString();

    // Scroll world
    for (const p of platforms) p.x -= speed * dt;
    for (const o of obstacles) o.x -= speed * dt;

    // Player physics
    player.jumpBuffer = Math.max(0, player.jumpBuffer - dt);

    // Ground / platform checks
    player.onGround = false;
    player.onPlat = false;

    // Apply gravity
    player.vy += gravity() * dt;

    // Fast drop if holding ArrowDown
    if (keys.has('ArrowDown') && player.vy < fastDropVel) {{
      player.vy += gravity() * dt * 1.5;
    }}

    // Integrate
    const yPrev = player.y;
    player.y += player.vy * dt;

    // Ground collision
    const gy = groundY();
    if (player.y + player.h >= gy) {{
      player.y = gy - player.h;
      player.vy = 0;
      player.onGround = true;
      player.coyote = 0.10;
    }}

    // Platform collision (landing only)
    // If falling and crosses platform top
    if (player.vy >= 0) {{
      for (const p of platforms) {{
        const top = p.y;
        const withinX = player.x + player.w > p.x && player.x < p.x + p.w;
        const crossed = (yPrev + player.h <= top) && (player.y + player.h >= top);
        if (withinX && crossed) {{
          player.y = top - player.h;
          player.vy = 0;
          player.onPlat = true;
          player.coyote = 0.10;
          break;
        }}
      }}
    }}

    // Coyote time (allow jump slightly after leaving ground/platform)
    player.coyote = Math.max(0, player.coyote - dt);

    // Jump consume
    const canJump = player.onGround || player.onPlat || player.coyote > 0;
    if (player.jumpBuffer > 0 && canJump) {{
      player.vy = jumpVel();
      player.jumpBuffer = 0;
      player.coyote = 0;
    }}

    // Obstacle collisions (any overlap = game over)
    for (const o of obstacles) {{
      if (aabb(player.x, player.y, player.w, player.h, o.x, o.y, o.w, o.h)) {{
        running = false;
        stateEl.textContent = "GAME OVER";
        if (Math.floor(score) > best) {{
          best = Math.floor(score);
          localStorage.setItem("parkour_best", String(best));
          bestEl.textContent = String(best);
        }}
        break;
      }}
    }}

    spawnIfNeeded(dt);
  }}

  function draw() {{
    const w = W(), h = H();
    ctx.clearRect(0, 0, w, h);

    // Background stars
    ctx.globalAlpha = 0.9;
    for (let i=0; i<40; i++) {{
      const sx = (i*97 % 800) - (score*0.4 % 800);
      const sy = (i*53 % 240) + 18;
      ctx.fillStyle = "rgba(232,238,252,0.12)";
      ctx.fillRect((sx + 800) % 800, sy, 2, 2);
    }}
    ctx.globalAlpha = 1;

    // Ground
    const gy = groundY();
    ctx.fillStyle = "rgba(255,255,255,0.06)";
    ctx.fillRect(0, gy, w, h - gy);
    ctx.strokeStyle = "rgba(255,255,255,0.12)";
    ctx.beginPath();
    ctx.moveTo(0, gy + 0.5);
    ctx.lineTo(w, gy + 0.5);
    ctx.stroke();

    // Platforms
    for (const p of platforms) {{
      ctx.fillStyle = "rgba(120,170,255,0.18)";
      ctx.fillRect(p.x, p.y, p.w, p.h);
      ctx.strokeStyle = "rgba(120,170,255,0.35)";
      ctx.strokeRect(p.x, p.y, p.w, p.h);
    }}

    // Obstacles
    for (const o of obstacles) {{
      ctx.fillStyle = "rgba(255,90,90,0.85)";
      ctx.fillRect(o.x, o.y, o.w, o.h);
      ctx.strokeStyle = "rgba(255,180,180,0.55)";
      ctx.strokeRect(o.x, o.y, o.w, o.h);
    }}

    // Player
    // Body
    ctx.fillStyle = running ? "rgba(210,255,170,0.95)" : "rgba(210,255,170,0.45)";
    ctx.fillRect(player.x, player.y, player.w, player.h);
    // Face
    ctx.fillStyle = "rgba(0,0,0,0.35)";
    ctx.fillRect(player.x + player.w - 9, player.y + 10, 4, 4);

    // Instruction overlay when dead
    if (!running) {{
      ctx.fillStyle = "rgba(0,0,0,0.45)";
      ctx.fillRect(0, 0, w, h);
      ctx.fillStyle = "rgba(255,255,255,0.95)";
      ctx.font = "700 28px system-ui, -apple-system, Segoe UI, Roboto, Arial";
      ctx.fillText("Game Over", w/2 - 78, h/2 - 8);
      ctx.font = "500 16px system-ui, -apple-system, Segoe UI, Roboto, Arial";
      ctx.fillText("Press R to restart (or use Reset button above)", w/2 - 175, h/2 + 22);
    }}
  }}

  function loop(now) {{
    const dt = Math.min(0.033, (now - tPrev) / 1000);
    tPrev = now;

    // Update HUD state
    stateEl.textContent = running ? "RUNNING" : "GAME OVER";

    update(dt);
    draw();
    requestAnimationFrame(loop);
  }}

  resetGame();
  requestAnimationFrame(loop);
}})();
</script>
</body>
</html>
"""

components.html(game_html, height=520, scrolling=False)
