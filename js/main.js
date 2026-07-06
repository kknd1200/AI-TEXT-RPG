import { CLASS_DEFS, createHero, recruitCost, upgradeCost, defaultState, save, load, resetSave, recalcStats } from "./state.js";
import { resolveRound, simulateOffline } from "./combat.js";

const ROUND_MS = 1400;
const MAX_ACTIVE = 4;
const MAX_OFFLINE_SECONDS = 8 * 60 * 60; // cap offline gains at 8 hours

let state = load() || defaultState();

const el = (id) => document.getElementById(id);

function pushLog(lines) {
  for (const line of lines) state.log.unshift(line);
  state.log = state.log.slice(0, 40);
  el("log-box").textContent = state.log.slice(0, 20).join("\n");
}

function asciiBar(current, max, width = 10) {
  const filled = Math.max(0, Math.min(width, Math.round((current / max) * width)));
  return "[" + "#".repeat(filled) + ".".repeat(width - filled) + "]";
}

function heroLine(hero) {
  const tags = [];
  tags.push(hero.row === "front" ? "전열" : "후열");
  if (hero.bench) tags.push("대기");
  if (!hero.alive) tags.push("전투불능");
  return (
    `${hero.name} Lv.${hero.level} (${tags.join("/")})\n` +
    `  HP ${asciiBar(hero.hp, hero.maxHp)} ${hero.hp}/${hero.maxHp}` +
    `  MP ${asciiBar(hero.mp, hero.maxMp)} ${hero.mp}/${hero.maxMp}`
  );
}

function renderStatus() {
  const e = state.enemy;
  const lines = [
    `골드: ${state.gold}G | 스테이지: ${state.stage} | 모드: ${state.mode === "auto" ? "자동전투" : "수동전투"}`,
    ``,
    `<적> ${e.name}`,
    `  HP ${asciiBar(e.hp, e.maxHp, 20)} ${e.hp}/${e.maxHp}`,
    ``,
    `<파티>`,
    ...state.heroes.map(heroLine),
  ];
  el("status-box").textContent = lines.join("\n");
}

function activeCount() {
  return state.heroes.filter((h) => !h.bench).length;
}

function renderHeroControls() {
  const box = el("hero-controls");
  box.innerHTML = "";
  for (const hero of state.heroes) {
    const line = document.createElement("div");

    const label = document.createElement("span");
    label.textContent = `${hero.name} Lv.${hero.level}: `;
    line.appendChild(label);

    const rowBtn = document.createElement("button");
    rowBtn.textContent = hero.row === "front" ? "[후열로]" : "[전열로]";
    rowBtn.onclick = () => {
      hero.row = hero.row === "front" ? "back" : "front";
      renderAll();
      save(state);
    };
    line.appendChild(rowBtn);

    const benchBtn = document.createElement("button");
    benchBtn.textContent = hero.bench ? "[출전]" : "[대기]";
    benchBtn.onclick = () => {
      if (hero.bench && activeCount() >= MAX_ACTIVE) {
        pushLog([`출전 인원은 최대 ${MAX_ACTIVE}명입니다.`]);
        return;
      }
      hero.bench = !hero.bench;
      renderAll();
      save(state);
    };
    line.appendChild(benchBtn);

    const cost = upgradeCost(hero);
    const trainBtn = document.createElement("button");
    trainBtn.textContent = `[훈련 ${cost}G]`;
    trainBtn.disabled = state.gold < cost;
    trainBtn.onclick = () => {
      if (state.gold < cost) return;
      state.gold -= cost;
      hero.level += 1;
      recalcStats(hero);
      hero.hp = hero.maxHp;
      hero.mp = hero.maxMp;
      pushLog([`${hero.name}을(를) 훈련시켜 레벨 ${hero.level}이 되었습니다.`]);
      renderAll();
      save(state);
    };
    line.appendChild(trainBtn);

    box.appendChild(line);
  }
}

function renderTop() {
  el("manual-controls").style.display = state.mode === "manual" ? "inline" : "none";
  el("recruit-cost").textContent = recruitCost(state);
  el("recruit-btn").disabled = state.gold < recruitCost(state);
}

function renderAll() {
  renderStatus();
  renderTop();
  renderHeroControls();
}

function doRound(policy) {
  if (state.heroes.filter((h) => h.alive && !h.bench).length === 0) {
    pushLog(["전투에 참여할 파티원이 없습니다. 대기 중인 영웅을 출전시키세요."]);
    return;
  }
  const result = resolveRound(state, policy);
  pushLog(result.logs);
  renderAll();
  save(state);
}

el("mode-toggle-btn").onclick = () => {
  state.mode = state.mode === "auto" ? "manual" : "auto";
  pushLog([state.mode === "auto" ? "자동전투로 전환합니다." : "수동전투로 전환합니다. 매 턴 명령을 선택하세요."]);
  renderAll();
  save(state);
};

el("btn-attack").onclick = () => doRound("attack");
el("btn-skill").onclick = () => doRound("skill");
el("btn-guard").onclick = () => doRound("guard");
el("btn-rest").onclick = () => doRound("rest");

el("recruit-btn").onclick = () => {
  const cost = recruitCost(state);
  if (state.gold < cost) return;
  const classes = Object.keys(CLASS_DEFS);
  const cls = classes[Math.floor(Math.random() * classes.length)];
  state.gold -= cost;
  const hero = createHero(cls, 1);
  hero.bench = activeCount() >= MAX_ACTIVE;
  state.heroes.push(hero);
  pushLog([`${hero.name}이(가) 파티에 합류했습니다.${hero.bench ? " (대기)" : ""}`]);
  renderAll();
  save(state);
};

el("reset-btn").onclick = () => {
  if (!confirm("정말로 모든 진행 상황을 초기화하시겠습니까?")) return;
  resetSave();
  state = defaultState();
  renderAll();
  pushLog(["새로운 모험을 시작합니다."]);
  save(state);
};

function showOfflineProgress() {
  const elapsed = Math.max(0, (Date.now() - (state.lastSaved || Date.now())) / 1000);
  if (state.mode !== "auto" || elapsed < 20) return;
  const capped = Math.min(elapsed, MAX_OFFLINE_SECONDS);
  const summary = simulateOffline(state, capped, ROUND_MS / 1000);
  if (summary.rounds === 0) return;
  const mins = Math.floor(capped / 60);
  pushLog([
    `골드 +${summary.goldGained}, 처치 ${summary.kills}, 스테이지 진행 +${summary.stagesCleared}`,
    `== 자리를 비운 ${mins}분 동안 파티가 자동으로 전투했습니다 ==`,
  ]);
}

let acc = 0;
let last = performance.now();
function loop(ts) {
  acc += ts - last;
  last = ts;
  if (state.mode === "auto" && acc >= ROUND_MS) {
    acc = 0;
    if (state.heroes.filter((h) => h.alive && !h.bench).length > 0) {
      const result = resolveRound(state, "auto");
      pushLog(result.logs);
      renderAll();
    }
  }
  requestAnimationFrame(loop);
}

setInterval(() => save(state), 8000);
window.addEventListener("beforeunload", () => save(state));
document.addEventListener("visibilitychange", () => {
  if (document.hidden) save(state);
});

showOfflineProgress();
pushLog([]);
renderAll();
requestAnimationFrame(loop);
