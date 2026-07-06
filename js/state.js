// Game data: hero classes, enemy templates, save/load, and cost formulas.

export const STORAGE_KEY = "pixel-strategy-idle-save-v1";

export const CLASS_DEFS = {
  warrior: {
    name: "전사",
    row: "front",
    base: { hp: 42, mp: 8, atk: 7, def: 6, spd: 5 },
    growth: { hp: 8, mp: 1, atk: 1.4, def: 1.3, spd: 0.6 },
    skillName: "강타",
    skillCost: 4,
    skillMult: 2.2,
  },
  archer: {
    name: "궁수",
    row: "back",
    base: { hp: 28, mp: 12, atk: 9, def: 3, spd: 8 },
    growth: { hp: 5, mp: 1.5, atk: 1.7, def: 0.6, spd: 1 },
    skillName: "연사",
    skillCost: 5,
    skillMult: 1.5,
    hits: 2,
  },
  mage: {
    name: "마법사",
    row: "back",
    base: { hp: 22, mp: 20, atk: 11, def: 2, spd: 6 },
    growth: { hp: 4, mp: 2.5, atk: 2, def: 0.4, spd: 0.7 },
    skillName: "파이어볼",
    skillCost: 8,
    skillMult: 2.8,
  },
  healer: {
    name: "힐러",
    row: "back",
    base: { hp: 24, mp: 18, atk: 4, def: 3, spd: 6 },
    growth: { hp: 5, mp: 2, atk: 0.6, def: 0.5, spd: 0.7 },
    skillName: "치유",
    skillCost: 6,
    heal: true,
    healMult: 3.2,
  },
};

export const ENEMY_CYCLE = ["slime", "goblin", "bat", "skeleton"];

export const ENEMY_DEFS = {
  slime: { name: "슬라임", hp: 18, atk: 4, def: 1, spd: 3, gold: 6, exp: 4 },
  goblin: { name: "고블린", hp: 26, atk: 6, def: 3, spd: 5, gold: 9, exp: 6 },
  bat: { name: "박쥐", hp: 16, atk: 5, def: 1, spd: 9, gold: 8, exp: 5 },
  skeleton: { name: "스켈레톤", hp: 34, atk: 7, def: 4, spd: 4, gold: 12, exp: 8 },
  dragon: { name: "레서 드래곤", hp: 120, atk: 14, def: 8, spd: 6, gold: 60, exp: 40 },
};

let uid = 1;
export function createHero(cls, level = 1) {
  const def = CLASS_DEFS[cls];
  const stat = (k) => Math.round(def.base[k] + def.growth[k] * (level - 1));
  return {
    id: uid++,
    cls,
    name: def.name,
    level,
    exp: 0,
    expNeeded: 10 + level * 8,
    maxHp: stat("hp"),
    hp: stat("hp"),
    maxMp: stat("mp"),
    mp: stat("mp"),
    atk: stat("atk"),
    def: stat("def"),
    spd: stat("spd"),
    row: def.row,
    bench: false,
    alive: true,
  };
}

export function recalcStats(hero) {
  const def = CLASS_DEFS[hero.cls];
  const stat = (k) => Math.round(def.base[k] + def.growth[k] * (hero.level - 1));
  const hpRatio = hero.hp / hero.maxHp;
  const mpRatio = hero.mp / hero.maxMp;
  hero.maxHp = stat("hp");
  hero.maxMp = stat("mp");
  hero.atk = stat("atk");
  hero.def = stat("def");
  hero.spd = stat("spd");
  hero.hp = Math.round(hero.maxHp * hpRatio);
  hero.mp = Math.round(hero.maxMp * mpRatio);
}

export function rollEnemy(stage) {
  const isBoss = stage % 10 === 0;
  const kind = isBoss ? "dragon" : ENEMY_CYCLE[(stage - 1) % ENEMY_CYCLE.length];
  const def = ENEMY_DEFS[kind];
  const scale = 1 + (stage - 1) * 0.16;
  const bossMult = isBoss ? 1 + Math.floor(stage / 10) * 0.35 : 1;
  return {
    kind,
    name: isBoss ? `${def.name} (보스)` : def.name,
    isBoss,
    maxHp: Math.round(def.hp * scale * bossMult),
    hp: Math.round(def.hp * scale * bossMult),
    atk: Math.round(def.atk * scale * bossMult),
    def: Math.round(def.def * scale),
    spd: def.spd,
    goldReward: Math.round(def.gold * scale * bossMult),
    expReward: Math.round(def.exp * scale * bossMult),
  };
}

export function recruitCost(state) {
  return Math.round(50 * Math.pow(1.55, state.heroes.length - 2));
}

export function upgradeCost(hero) {
  return Math.round(20 * Math.pow(1.35, hero.level - 1));
}

export function defaultState() {
  const warrior = createHero("warrior", 1);
  const archer = createHero("archer", 1);
  return {
    gold: 30,
    stage: 1,
    mode: "auto",
    heroes: [warrior, archer],
    enemy: rollEnemy(1),
    log: ["전략/방치형 픽셀 던전에 오신 것을 환영합니다."],
    lastSaved: Date.now(),
    totalKills: 0,
    totalPlaySeconds: 0,
  };
}

export function save(state) {
  state.lastSaved = Date.now();
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch (e) {
    // storage unavailable (private mode, quota) - ignore, game still runs in-memory
  }
}

export function load() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const state = JSON.parse(raw);
    if (!state.heroes || !state.enemy) return null;
    uid = Math.max(uid, ...state.heroes.map((h) => h.id + 1));
    return state;
  } catch (e) {
    return null;
  }
}

export function resetSave() {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch (e) {
    // ignore
  }
}
