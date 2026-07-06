import { CLASS_DEFS, rollEnemy, recalcStats } from "./state.js";

function activeParty(state) {
  return state.heroes.filter((h) => h.alive && !h.bench);
}

function pickTarget(state) {
  const party = activeParty(state);
  const front = party.filter((h) => h.row === "front");
  const pool = front.length ? front : party;
  return pool[Math.floor(Math.random() * pool.length)];
}

function dmgRoll(atk, def, mult = 1) {
  const raw = atk * mult - def * 0.5;
  return Math.max(1, Math.round(raw + (Math.random() * 2 - 0.5)));
}

function grantExp(state, hero, exp, logs) {
  hero.exp += exp;
  while (hero.exp >= hero.expNeeded) {
    hero.exp -= hero.expNeeded;
    hero.level += 1;
    hero.expNeeded = 10 + hero.level * 8;
    recalcStats(hero);
    hero.hp = hero.maxHp;
    hero.mp = hero.maxMp;
    logs.push(`${hero.name}의 레벨이 ${hero.level}(으)로 올랐습니다!`);
  }
}

function heroAction(state, hero, policy, logs) {
  const def = CLASS_DEFS[hero.cls];
  const enemy = state.enemy;
  const wantsSkill = policy === "skill" || (policy === "auto" && hero.mp >= def.skillCost && Math.random() < 0.55);

  if (def.heal && wantsSkill && hero.mp >= def.skillCost) {
    const party = activeParty(state);
    const lowest = party.reduce((a, b) => (b.hp / b.maxHp < a.hp / a.maxHp ? b : a), party[0]);
    if (lowest && lowest.hp < lowest.maxHp) {
      hero.mp -= def.skillCost;
      const healAmt = Math.round(hero.atk * def.healMult);
      lowest.hp = Math.min(lowest.maxHp, lowest.hp + healAmt);
      logs.push(`${hero.name}의 ${def.skillName}! ${lowest.name}의 체력을 ${healAmt} 회복.`);
      return;
    }
  }

  if (!def.heal && wantsSkill && hero.mp >= def.skillCost) {
    hero.mp -= def.skillCost;
    const hits = def.hits || 1;
    let total = 0;
    for (let i = 0; i < hits; i++) {
      const dmg = dmgRoll(hero.atk, enemy.def, def.skillMult);
      enemy.hp = Math.max(0, enemy.hp - dmg);
      total += dmg;
      if (enemy.hp <= 0) break;
    }
    logs.push(`${hero.name}의 ${def.skillName}! ${enemy.name}에게 ${total}의 피해.`);
    return;
  }

  if (def.heal) {
    // healer with no mp / nobody hurt: chip damage
    const dmg = dmgRoll(hero.atk, enemy.def, 0.7);
    enemy.hp = Math.max(0, enemy.hp - dmg);
    logs.push(`${hero.name}의 공격! ${enemy.name}에게 ${dmg}의 피해.`);
    return;
  }

  const dmg = dmgRoll(hero.atk, enemy.def, 1);
  enemy.hp = Math.max(0, enemy.hp - dmg);
  logs.push(`${hero.name}의 공격! ${enemy.name}에게 ${dmg}의 피해.`);
}

export function resolveRound(state, policy = "auto") {
  const logs = [];
  const result = { logs, victory: false, wipe: false, levelUp: false };
  const party = activeParty(state);
  if (party.length === 0) return result;

  if (policy === "rest") {
    for (const hero of party) {
      hero.hp = Math.min(hero.maxHp, hero.hp + Math.round(hero.maxHp * 0.08));
      hero.mp = Math.min(hero.maxMp, hero.mp + Math.round(hero.maxMp * 0.2));
    }
    logs.push("파티가 휴식을 취하며 체력과 마나를 회복합니다.");
  } else if (policy === "guard") {
    for (const hero of party) {
      hero.mp = Math.min(hero.maxMp, hero.mp + Math.round(hero.maxMp * 0.1));
    }
    logs.push("파티가 방어 태세를 갖춥니다.");
  } else {
    const order = [...party].sort((a, b) => b.spd - a.spd);
    for (const hero of order) {
      if (state.enemy.hp <= 0) break;
      heroAction(state, hero, policy, logs);
    }
  }

  if (state.enemy.hp <= 0) {
    logs.push(`${state.enemy.name}을(를) 쓰러뜨렸습니다!`);
    state.gold += state.enemy.goldReward;
    state.totalKills += 1;
    for (const hero of party) grantExp(state, hero, state.enemy.expReward, logs);
    state.stage += 1;
    state.enemy = rollEnemy(state.stage);
    result.victory = true;
    return result;
  }

  const target = pickTarget(state);
  if (target) {
    const guardMult = policy === "guard" ? 0.5 : 1;
    const dmg = Math.max(1, Math.round(dmgRoll(state.enemy.atk, target.def, 1) * guardMult));
    target.hp = Math.max(0, target.hp - dmg);
    logs.push(`${state.enemy.name}의 공격! ${target.name}이(가) ${dmg}의 피해를 입었습니다.`);
    if (target.hp <= 0) {
      target.alive = false;
      logs.push(`${target.name}이(가) 쓰러졌습니다!`);
    }
  }

  if (activeParty(state).length === 0) {
    logs.push("파티가 전멸했습니다... 마을로 후퇴하여 회복합니다.");
    for (const hero of state.heroes) {
      hero.alive = true;
      hero.hp = hero.maxHp;
      hero.mp = hero.maxMp;
    }
    state.gold = Math.max(0, Math.round(state.gold * 0.9));
    result.wipe = true;
  }

  return result;
}

// Fast-forwards battles to approximate offline/idle progress without full per-round animation.
export function simulateOffline(state, seconds, roundSeconds) {
  const maxRounds = Math.min(Math.floor(seconds / roundSeconds), 60 * 60 * 4); // hard safety cap
  const startGold = state.gold;
  const startStage = state.stage;
  const startKills = state.totalKills;
  let rounds = 0;
  for (; rounds < maxRounds; rounds++) {
    resolveRound(state, "auto");
  }
  return {
    rounds,
    goldGained: state.gold - startGold,
    stagesCleared: state.stage - startStage,
    kills: state.totalKills - startKills,
  };
}
