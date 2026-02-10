game_html = f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <style>
    body {{ margin: 0; padding: 0; background: #0b1020; font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial; }}
    .wrap {{ width: 760px; max-width: 100%; margin: 0 auto; padding: 8px 0 0 0; color: #e8eefc; }}
    .hud {{
      display:flex; justify-content:space-between; align-items:center;
      padding: 8px 10px; margin: 6px 0 10px 0;
      background: rgba(255,255,255,0.06);
      border: 1px solid rgba(255,255,255,0.10);
      border-radius: 14px; backdrop-filter: blur(6px);
      gap: 10px;
    }}
    .hud b {{ font-size: 18px; }}
    .pill {{
      display:inline-block; padding:2px 8px; border-radius:999px;
      background: rgba(255,255,255,0.08); border:1px solid rgba(255,255,255,0.10);
      font-size: 12px;
    }}
    .bar {{ width: 140px; height: 10px; border-radius: 999px; background: rgba(255,255,255,0.10); overflow:hidden; border:1px solid rgba(255,255,255,0.10); }}
    .bar > div {{ height: 100%; width: 0%; background: rgba(120,170,255,0.85); }}
    canvas {{
      width: 760px; max-width: 100%;
      aspect-ratio: 19 / 9;
      background: linear-gradient(180deg, #0b1020 0%, #111a33 50%, #121b2e 100%);
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 18px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.35);
      touch-action: manipulation;
      outline: none; /* we’ll draw focus cue ourselves */
    }}
    .help {{ opacity: 0.85; font-size: 13px; padding: 8px 6px 12px 6px; }}
  </style>
</head>
<body>
  <div class="wrap" id="wrap-{reset_key}">
    <div class="hud">
      <div><b id="score">0</b> <span class="pill">score</span> <span class="pill">x<span id="combo">1</span></span></div>
      <div>Coins: <span id="coins">0</span> <span class="pill">+50</span></div>
      <div style="display:flex;align-items:center;gap:8px;">
        <span class="pill">Dash</span>
        <div class="bar"><div id="dashbar"></div></div>
      </div>
      <div>Best: <span id="best">0</span> <span class="pill">local</span></div>
      <div id="state" class="pill">RUNNING</div>
    </div>

    <!-- tabindex enables keyboard focus -->
    <canvas id="c" width="760" height="360" tabindex="0"></canvas>

    <div class="help">
      Jump: <b>Space</b>/<b>↑</b> (double-jump), Dash: <b>Shift</b>, Fast drop: <b>↓</b>, Restart: <b>R</b>.
      Click canvas once if Space doesn’t respond (focus).
    </div>
  </div>

<script>
(() => {{
  const DIFFICULTY0 = {difficulty};  // 1..10
  const SPEED_MULT = {speed_mult};   // 1.0..3.0
  const GRAVITY_MULT = {gravity};    // 0.6..2.4

  const canvas = document.getElementById('c');
  const ctx = canvas.getContext('2d');

  // Focus for Space to work reliably inside Streamlit embed
  function focusCanvas() {{ canvas.focus(); }}
  setTimeout(focusCanvas, 30);
  canvas.addEventListener('pointerdown', () => focusCanvas());

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

  const W = () => canvas.getBoundingClientRect().width;
  const H = () => canvas.getBoundingClientRect().height;
  const groundY = () => H() - 46;

  // Dynamic difficulty ramps with score
  const diff = () => Math.min(14, DIFFICULTY0 + score / 800);

  const baseSpeed = () => (220 + diff() * 18) * SPEED_MULT;
  const gravity = () => 1600 * GRAVITY_MULT;
  const jumpVel = () => -560 - diff() * 9;
  const fastDropVel = 950;

  let running = true;
  let tPrev = performance.now();
  let score = 0;
  let coins = 0;
  let combo = 1;
  let comboTimer = 0;

  let best = Number(localStorage.getItem("parkour_best") || "0");
  const scoreEl = document.getElementById('score');
  const bestEl = document.getElementById('best');
  const stateEl = document.getElementById('state');
  const coinsEl = document.getElementById('coins');
  const comboEl = document.getElementById('combo');
  const dashBar = document.getElementById('dashbar');
  bestEl.textContent = best.toString();

  const keys = new Set();
  function onKeyDown(e) {{
    // prevent Space scrolling the page
    if (e.code === 'Space' || e.code === 'ArrowUp' || e.code === 'ArrowDown') e.preventDefault();
    keys.add(e.code);

    if (e.code === 'Space' || e.code === 'ArrowUp') pressJump();
    if (e.code === 'ShiftLeft' || e.code === 'ShiftRight') pressDash();
    if (e.code === 'KeyR') resetGame();
  }}
  function onKeyUp(e) {{ keys.delete(e.code); }}

  // Attach listeners to canvas so they work when focused
  canvas.addEventListener('keydown', onKeyDown);
  canvas.addEventListener('keyup', onKeyUp);

  // Mobile / mouse jump
  canvas.addEventListener('pointerdown', (e) => {{
    e.preventDefault();
    pressJump();
  }});

  function rand(a,b) {{ return a + Math.random()*(b-a); }}

  // Player
  const player = {{
    x: 120, y: groundY() - 34,
    w: 28, h: 34,
    vy: 0,
    jumpsLeft: 2,
    coyote: 0,
    jumpBuffer: 0,
    dashT: 0,
    dashCD: 0,
  }};

  let platforms = [];
  let obstacles = [];
  let coinDrops = [];

  function makePlatform(x) {{
    const h = rand(10, 16);
    const w = rand(110, 200);
    const y = groundY() - rand(70, 160 + diff()*6);

    // moving platforms become more common with difficulty
    const moving = Math.random() < (0.10 + diff()*0.015);
    const amp = moving ? rand(12, 28 + diff()*2) : 0;
    const spd = moving ? rand(1.2, 2.6) : 0;
    const phase = rand(0, Math.PI*2);

    return {{ x, y, w, h, moving, amp, spd, phase }};
  }}

  function makeObstacle(x) {{
    const w = rand(18, 34);
    const h = rand(24, 44) + diff()*2;
    return {{ x, y: groundY() - h, w, h }};
  }}

  function makeCoin(x) {{
    const r = 7;
    const y = groundY() - rand(90, 190 + diff()*5);
    return {{ x, y, r, taken:false }};
  }}

  function resetGame() {{
    running = true;
    score = 0;
    coins = 0;
    combo = 1;
    comboTimer = 0;

    player.y = groundY() - player.h;
    player.vy = 0;
    player.jumpsLeft = 2;
    player.coyote = 0;
    player.jumpBuffer = 0;
    player.dashT = 0;
    player.dashCD = 0;

    platforms = [];
    obstacles = [];
    coinDrops = [];

    let x = 520;
    for (let i=0; i<5; i++) {{
      const p = makePlatform(x);
      platforms.push(p);
      x += p.w + rand(110, 250);
      if (Math.random() < 0.6) coinDrops.push(makeCoin(x - rand(40, 120)));
    }}

    let ox = 520;
    for (let i=0; i<3; i++) {{
      obstacles.push(makeObstacle(ox));
      ox += rand(220, 420);
    }}
  }}

  function pressJump() {{
    player.jumpBuffer = 0.12; // seconds
  }}

  function pressDash() {{
    if (!running) return;
    if (player.dashCD <= 0) {{
      player.dashT = 0.14;   // dash duration
      player.dashCD = 0.9;   // cooldown
    }}
  }}

  function aabb(ax, ay, aw, ah, bx, by, bw, bh) {{
    return ax < bx + bw && ax + aw > bx && ay < by + bh && ay + ah > by;
  }}

  function circleHitRect(cx, cy, r, rx, ry, rw, rh) {{
    const px = Math.max(rx, Math.min(cx, rx + rw));
    const py = Math.max(ry, Math.min(cy, ry + rh));
    const dx = cx - px, dy = cy - py;
    return dx*dx + dy*dy <= r*r;
  }}

  function spawnIfNeeded(dt) {{
    while (platforms.length < 9) {{
      const last = platforms[platforms.length - 1];
      const gap = Math.max(120, 270 - diff()*10);
      const nx = last ? last.x + last.w + rand(gap, gap + 260) : rand(420, 740);
      platforms.push(makePlatform(nx));
      if (Math.random() < (0.55 + diff()*0.01)) coinDrops.push(makeCoin(nx + rand(20, 110)));
    }}

    const targetObs = 6 + Math.floor(diff()/2);
    while (obstacles.length < targetObs) {{
      const last = obstacles[obstacles.length - 1];
      const minGap = Math.max(130, 320 - diff()*16);
      const nx = last ? last.x + rand(minGap, minGap + 260) : rand(460, 820);
      obstacles.push(makeObstacle(nx));
    }}

    platforms = platforms.filter(p => p.x + p.w > -140);
    obstacles = obstacles.filter(o => o.x + o.w > -140);
    coinDrops = coinDrops.filter(c => c.x + c.r > -140 && !c.taken);
  }}

  function update(dt) {{
    if (!running) return;

    score += dt * (10 + diff() * 2.8);
    scoreEl.textContent = Math.floor(score).toString();
    coinsEl.textContent = coins.toString();
    comboEl.textContent = combo.toString();

    // combo decay
    if (comboTimer > 0) comboTimer -= dt;
    else combo = 1;

    // dash cooldown
    player.dashCD = Math.max(0, player.dashCD - dt);
    dashBar.style.width = String(100 * (1 - (player.dashCD / 0.9))) + "%";

    // world scroll (dash increases speed briefly)
    const dashBoost = player.dashT > 0 ? 1.9 : 1.0;
    const speed = baseSpeed() * dashBoost;

    // move platforms (vertical)
    const t = score * 0.01;
    for (const p of platforms) {{
      if (p.moving) {{
        p.y += Math.sin(t * p.spd + p.phase) * p.amp * dt;
      }}
      p.x -= speed * dt;
    }}
    for (const o of obstacles) o.x -= speed * dt;
    for (const c of coinDrops) c.x -= speed * dt;

    if (player.dashT > 0) player.dashT = Math.max(0, player.dashT - dt);

    // player buffers
    player.jumpBuffer = Math.max(0, player.jumpBuffer - dt);

    // gravity
    player.vy += gravity() * dt;

    // fast drop
    if (keys.has('ArrowDown') && player.vy < fastDropVel) {{
      player.vy += gravity() * dt * 1.4;
    }}

    // integrate
    const yPrev = player.y;
    player.y += player.vy * dt;

    // landing flags
    let landed = false;

    // ground
    const gy = groundY();
    if (player.y + player.h >= gy) {{
      player.y = gy - player.h;
      player.vy = 0;
      landed = true;
    }}

    // platforms (landing only)
    if (player.vy >= 0) {{
      for (const p of platforms) {{
        const top = p.y;
        const withinX = player.x + player.w > p.x && player.x < p.x + p.w;
        const crossed = (yPrev + player.h <= top) && (player.y + player.h >= top);
        if (withinX && crossed) {{
          player.y = top - player.h;
          player.vy = 0;
          landed = true;
          break;
        }}
      }}
    }}

    if (landed) {{
      player.jumpsLeft = 2;        // reset double jump
      player.coyote = 0.10;
    }} else {{
      player.coyote = Math.max(0, player.coyote - dt);
    }}

    // jump logic: allow jump with buffer, and allow coyote for first jump
    const canJumpNow = (player.jumpsLeft > 0) && (landed || player.coyote > 0 || player.jumpsLeft < 2);
    if (player.jumpBuffer > 0 && canJumpNow) {{
      player.vy = jumpVel();
      player.jumpBuffer = 0;
      player.jumpsLeft -= 1;
      player.coyote = 0;
    }}

    // coins
    for (const c of coinDrops) {{
      if (!c.taken && circleHitRect(c.x, c.y, c.r, player.x, player.y, player.w, player.h)) {{
        c.taken = true;
        coins += 1;
        combo += 1;
        comboTimer = 1.2; // seconds to keep chaining
        score += 50 * combo;
      }}
    }}

    // obstacle collision
    for (const o of obstacles) {{
      if (aabb(player.x, player.y, player.w, player.h, o.x, o.y, o.w, o.h)) {{
        running = false;
        stateEl.textContent = "GAME OVER";
        const s = Math.floor(score);
        if (s > best) {{
          best = s;
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

    // subtle focus cue
    if (document.activeElement === canvas) {{
      ctx.strokeStyle = "rgba(120,170,255,0.55)";
      ctx.lineWidth = 2;
      ctx.strokeRect(3, 3, w-6, h-6);
    }}

    // stars
    ctx.globalAlpha = 0.9;
    for (let i=0; i<42; i++) {{
      const sx = (i*97 % 800) - (score*0.45 % 800);
      const sy = (i*53*
