/* 원작 복원 필드 런타임.
   tools/build_classic.py 가 만든 bundle.json 과 PNG를 읽어 320x240 화면을 그린다.

   좌표 규칙: 타일 8px, 화면은 화면 단위로 나뉘어 있고 한 화면이 곧 한 맵이다.
   화면 사이의 연결 정보(.mif)는 아직 해독하지 못해서, 지금은 화면 버튼으로 넘긴다. */

(function () {
  "use strict";

  const TILE = 8;
  const VIEW_W = 320, VIEW_H = 240;
  const ENCOUNTER_MIN = 8, ENCOUNTER_MAX = 24;

  const canvas = document.getElementById("screen");
  const ctx = canvas.getContext("2d");
  ctx.imageSmoothingEnabled = false;
  const hud = document.getElementById("hud");
  const notice = document.getElementById("notice");

  let bundle = null;
  let tilesImage = null;
  const spriteCache = new Map();

  const state = {
    screen: 0,
    px: 5, py: 5,            // 타일 좌표
    fx: 5, fy: 5,            // 그리는 좌표(부드러운 이동용)
    dir: "down",
    moving: false,
    steps: 0,
    nextEncounter: roll(ENCOUNTER_MIN, ENCOUNTER_MAX),
    battle: null,
    frame: 0,
  };

  const held = new Set();

  function roll(lo, hi) { return lo + Math.floor(Math.random() * (hi - lo + 1)); }

  function loadImage(src) {
    if (spriteCache.has(src)) return spriteCache.get(src);
    const promise = new Promise((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve(image);
      image.onerror = () => reject(new Error(src + " 를 불러오지 못했다"));
      image.src = src;
    });
    spriteCache.set(src, promise);
    return promise;
  }

  /* ── 데이터 ─────────────────────────────────────────────── */

  const currentScreen = () => bundle.map.screens[state.screen];

  function tileSource(index) {
    /* 타일 번호를 아틀라스 좌표로. 시트마다 번호가 0부터 다시 시작한다. */
    const sheets = bundle.map.tileset.sheets;
    for (const sheet of sheets) {
      const count = sheet.cols * sheet.rows;
      if (index < count) {
        return {
          sx: (index % sheet.cols) * TILE,
          sy: sheet.top + Math.floor(index / sheet.cols) * TILE,
        };
      }
    }
    return null;
  }

  function blocked(x, y) {
    const screen = currentScreen();
    if (x < 0 || y < 0 || x >= screen.w || y >= screen.h) return true;
    return screen.collision[y * screen.w + x] === 1;
  }

  /* ── 그리기 ─────────────────────────────────────────────── */

  function camera() {
    const screen = currentScreen();
    const maxX = Math.max(0, screen.w * TILE - VIEW_W);
    const maxY = Math.max(0, screen.h * TILE - VIEW_H);
    const cx = state.fx * TILE + TILE / 2 - VIEW_W / 2;
    const cy = state.fy * TILE + TILE / 2 - VIEW_H / 2;
    return {
      x: Math.round(Math.min(maxX, Math.max(0, cx))),
      y: Math.round(Math.min(maxY, Math.max(0, cy))),
    };
  }

  function drawField() {
    const screen = currentScreen();
    const cam = camera();
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, VIEW_W, VIEW_H);

    const firstX = Math.floor(cam.x / TILE), firstY = Math.floor(cam.y / TILE);
    const lastX = Math.min(screen.w - 1, firstX + VIEW_W / TILE);
    const lastY = Math.min(screen.h - 1, firstY + VIEW_H / TILE);

    for (const layer of screen.layers) {
      for (let ty = firstY; ty <= lastY; ty++) {
        for (let tx = firstX; tx <= lastX; tx++) {
          const index = layer[ty * screen.w + tx];
          if (index === 255) continue;
          const src = tileSource(index);
          if (!src) continue;
          ctx.drawImage(tilesImage, src.sx, src.sy, TILE, TILE,
            tx * TILE - cam.x, ty * TILE - cam.y, TILE, TILE);
        }
      }
    }
    drawHero(cam);
  }

  let heroSheet = null, heroFrames = null;

  function drawHero(cam) {
    if (!heroSheet || !heroFrames || !heroFrames.length) {
      ctx.fillStyle = "#f4f8ee";
      ctx.fillRect(Math.round(state.fx * TILE) - cam.x, Math.round(state.fy * TILE) - cam.y, TILE, TILE);
      return;
    }
    // .ani(프레임 조립 규칙)를 아직 못 읽어서, 온전한 몸 프레임만 골라 번갈아 쓴다.
    const pose = heroFrames[(state.moving ? Math.floor(state.frame / 8) : 0) % heroFrames.length];
    const x = Math.round(state.fx * TILE) - cam.x + TILE / 2 - pose.ax;
    const y = Math.round(state.fy * TILE) - cam.y + TILE - pose.ay;
    ctx.drawImage(heroSheet, pose.x, pose.y, pose.w, pose.h, x, y, pose.w, pose.h);
  }

  function drawBattle() {
    const battle = state.battle;
    ctx.fillStyle = "#0a0c08";
    ctx.fillRect(0, 0, VIEW_W, VIEW_H);
    ctx.fillStyle = "#16200f";
    ctx.fillRect(0, 150, VIEW_W, 90);

    if (battle.sheet && battle.pose) {
      const p = battle.pose;
      ctx.drawImage(battle.sheet, p.x, p.y, p.w, p.h,
        Math.round(VIEW_W / 2 - p.w / 2), Math.round(120 - p.h), p.w, p.h);
    }

    ctx.fillStyle = "#d8e2cf";
    ctx.font = "10px monospace";
    ctx.fillText(`야생 ${battle.name}`, 10, 56);          // 상단 HUD와 겹치지 않게
    ctx.fillText(`HP ${battle.hp}/${battle.maxHp}`, 10, 70);
    ctx.fillRect(10, 76, Math.round(120 * battle.hp / battle.maxHp), 4);

    let y = 172;
    for (const line of battle.log.slice(-4)) {
      ctx.fillText(line, 10, y);
      y += 14;
    }
    ctx.fillText("A: 공격    화면 버튼: 도망", 10, 230);
  }

  function draw() {
    if (state.battle) drawBattle();
    else drawField();
    const screen = currentScreen();
    hud.textContent =
      `${bundle.map.name} ${state.screen + 1}/${bundle.map.screens.length}` +
      `  ${screen.w}x${screen.h}\n` +
      (state.battle ? "전투 중" : `위치 ${state.px},${state.py}  걸음 ${state.steps}`);
  }

  /* ── 이동 ───────────────────────────────────────────────── */

  const DIRS = { up: [0, -1], down: [0, 1], left: [-1, 0], right: [1, 0] };

  function step() {
    state.frame++;
    if (state.battle) { draw(); return; }

    if (!state.moving) {
      for (const dir of ["up", "down", "left", "right"]) {
        if (!held.has(dir)) continue;
        state.dir = dir;
        const [dx, dy] = DIRS[dir];
        const nx = state.px + dx, ny = state.py + dy;
        if (!blocked(nx, ny)) {
          state.px = nx; state.py = ny;
          state.moving = true;
          state.steps++;
          if (state.steps >= state.nextEncounter) startBattle();
        }
        break;
      }
    }

    // 부드럽게 따라가기
    const speed = 0.25;
    if (Math.abs(state.fx - state.px) > 0.01 || Math.abs(state.fy - state.py) > 0.01) {
      state.fx += Math.sign(state.px - state.fx) * Math.min(speed, Math.abs(state.px - state.fx));
      state.fy += Math.sign(state.py - state.fy) * Math.min(speed, Math.abs(state.py - state.fy));
    } else {
      state.fx = state.px; state.fy = state.py;
      state.moving = false;
    }
    draw();
  }

  /* ── 전투 ───────────────────────────────────────────────── */

  async function startBattle() {
    state.steps = 0;
    state.nextEncounter = roll(ENCOUNTER_MIN, ENCOUNTER_MAX);
    const keys = Object.keys(bundle.battle);
    if (!keys.length) return;
    const key = keys[Math.floor(Math.random() * keys.length)];
    const entry = bundle.battle[key];
    const maxHp = roll(40, 120);
    state.battle = {
      name: key.replace("m_b_", "").replace("_1", ""),
      hp: maxHp, maxHp, log: ["야생 몬스터가 나타났다!"], sheet: null, pose: null,
    };
    draw();
    try {
      const sheet = await loadImage(entry.image);
      // 가장 큰 프레임이 온전한 몸이다. 조각 프레임은 .ani 가 있어야 조립된다.
      const pose = entry.frames.reduce((a, b) => (a.w * a.h >= b.w * b.h ? a : b));
      state.battle.sheet = sheet;
      state.battle.pose = pose;
      draw();
    } catch (error) {
      state.battle.log.push("(스프라이트를 불러오지 못했다)");
    }
  }

  function attack() {
    const battle = state.battle;
    if (!battle) return;
    const damage = roll(8, 22);
    battle.hp = Math.max(0, battle.hp - damage);
    battle.log.push(`공격! ${damage}의 피해`);
    if (battle.hp === 0) {
      battle.log.push("쓰러뜨렸다!");
      setTimeout(() => { state.battle = null; draw(); }, 700);
    }
    draw();
  }

  /* ── 입력 ───────────────────────────────────────────────── */

  const KEYS = {
    ArrowUp: "up", ArrowDown: "down", ArrowLeft: "left", ArrowRight: "right",
    w: "up", s: "down", a: "left", d: "right",
  };

  addEventListener("keydown", (event) => {
    const dir = KEYS[event.key];
    if (dir) { held.add(dir); event.preventDefault(); }
    if (event.key === "Enter" || event.key === " ") { attack(); event.preventDefault(); }
  });
  addEventListener("keyup", (event) => {
    const dir = KEYS[event.key];
    if (dir) held.delete(dir);
  });

  for (const button of document.querySelectorAll("#dpad button")) {
    const dir = button.dataset.dir;
    const press = (event) => { event.preventDefault(); held.add(dir); };
    const release = (event) => { event.preventDefault(); held.delete(dir); };
    button.addEventListener("pointerdown", press);
    button.addEventListener("pointerup", release);
    button.addEventListener("pointercancel", release);
    button.addEventListener("pointerleave", release);
  }

  document.getElementById("btnA").addEventListener("click", attack);
  document.getElementById("btnPrev").addEventListener("click", () => changeScreen(-1));
  document.getElementById("btnNext").addEventListener("click", () => changeScreen(1));

  function changeScreen(delta) {
    if (state.battle) { state.battle = null; draw(); return; }
    const count = bundle.map.screens.length;
    state.screen = (state.screen + delta + count) % count;
    const spot = spawnPoint(currentScreen());
    state.px = state.fx = spot.x;
    state.py = state.fy = spot.y;
    draw();
  }

  function spawnPoint(screen) {
    /* 가장 넓게 이어진 통행 구역의 한가운데에 내려놓는다.
       처음 만나는 빈 칸에 두면 한 칸짜리 웅덩이에 갇혀 움직일 수 없다. */
    const seen = new Int32Array(screen.w * screen.h).fill(-1);
    let best = null, region = 0;
    for (let start = 0; start < seen.length; start++) {
      if (seen[start] >= 0 || screen.collision[start] === 1) continue;
      const queue = [start];
      const cells = [];
      seen[start] = region;
      while (queue.length) {
        const at = queue.pop();
        cells.push(at);
        const x = at % screen.w, y = (at / screen.w) | 0;
        for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
          const nx = x + dx, ny = y + dy;
          if (nx < 0 || ny < 0 || nx >= screen.w || ny >= screen.h) continue;
          const next = ny * screen.w + nx;
          if (seen[next] >= 0 || screen.collision[next] === 1) continue;
          seen[next] = region;
          queue.push(next);
        }
      }
      if (!best || cells.length > best.length) best = cells;
      region++;
    }
    if (!best || !best.length) return { x: 1, y: 1 };
    let sx = 0, sy = 0;
    for (const at of best) { sx += at % screen.w; sy += (at / screen.w) | 0; }
    const cx = sx / best.length, cy = sy / best.length;
    let pick = best[0], bestDist = Infinity;
    for (const at of best) {
      const x = at % screen.w, y = (at / screen.w) | 0;
      const dist = (x - cx) ** 2 + (y - cy) ** 2;
      if (dist < bestDist) { bestDist = dist; pick = at; }
    }
    return { x: pick % screen.w, y: (pick / screen.w) | 0 };
  }

  /* ── 화면 크기 ──────────────────────────────────────────── */

  function resize() {
    const padHeight = 210;
    const scale = Math.max(1, Math.min(
      Math.floor((innerWidth - 20) / VIEW_W),
      Math.floor((innerHeight - padHeight) / VIEW_H),
    ));
    canvas.style.width = VIEW_W * scale + "px";
    canvas.style.height = VIEW_H * scale + "px";
  }
  addEventListener("resize", resize);

  /* ── 시작 ───────────────────────────────────────────────── */

  async function boot() {
    try {
      bundle = await (await fetch("./bundle.json")).json();
    } catch (error) {
      notice.textContent =
        "bundle.json 을 읽지 못했다. tools/build_classic.py 로 에셋을 먼저 굽고, " +
        "file:// 이 아니라 로컬 서버로 열어야 한다. (python3 -m http.server)";
      return;
    }
    tilesImage = await loadImage(bundle.map.tileset.image);
    const heroKey = Object.keys(bundle.hero)[0];
    if (heroKey) {
      const entry = bundle.hero[heroKey];
      heroSheet = await loadImage(entry.image);
      const biggest = entry.frames.reduce((a, b) => (a.w * a.h >= b.w * b.h ? a : b));
      heroFrames = entry.frames.filter((f) => f.w * f.h >= biggest.w * biggest.h * 0.6);
    }
    // 시작 위치를 갈 수 있는 칸으로
    changeScreen(0);
    notice.textContent =
      `${bundle.map.name} · 화면 ${bundle.map.screens.length}장. ` +
      "방향키/WASD 또는 화면 버튼으로 이동, 걷다 보면 전투가 난다. " +
      "화면 연결은 아직 해독하지 못해 '화면' 버튼으로 넘긴다.";
    const clearNotice = () => { notice.textContent = ""; draw(); };
    setTimeout(clearNotice, 5000);
    addEventListener("keydown", clearNotice, { once: true });
    document.getElementById("pad").addEventListener("pointerdown", clearNotice, { once: true });
    resize();
    setInterval(step, 33);
  }

  boot();
})();
