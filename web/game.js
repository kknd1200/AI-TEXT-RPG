/* 엘리멘탈 테이머 — 파이썬판(tamer/)의 규칙을 그대로 옮긴 웹 구현.
   수치는 전부 D.balance 에서 읽으므로, 밸런스를 고치려면 data/rules/balance.json 만
   고치고 tools/build_web.py 로 다시 만들면 된다. */

(function () {
  "use strict";

  const B = D.balance;
  const SPECIES = D.roster.monsters;
  const GRADES = ["common", "uncommon", "rare", "special", "legend", "god"];
  const ELEMENTS = Object.keys(D.roster.elements);
  const STATS = ["str", "dex", "mstr", "int", "con", "spd"];
  const STAT_LABEL = {
    str: "STR 물리공격", dex: "DEX 물리방어", mstr: "MSTR 스킬공격",
    int: "INT 스킬방어", con: "CON 체력", spd: "SPD 속도",
  };

  const rnd = () => Math.random();
  const randInt = (lo, hi) => lo + Math.floor(rnd() * (hi - lo + 1));
  const pick = (list) => list[Math.floor(rnd() * list.length)];
  const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

  function weightedPick(list, weights) {
    let total = 0;
    for (const w of weights) total += w;
    let roll = rnd() * total;
    for (let i = 0; i < list.length; i++) {
      roll -= weights[i];
      if (roll <= 0) return list[i];
    }
    return list[list.length - 1];
  }

  const speciesOf = (m) => SPECIES[m.species];
  const gradeIndex = (sp) => GRADES.indexOf(sp.grade);
  const byName = (name) => SPECIES.findIndex((s) => s.name === name);
  const filterSpecies = (element, grade) =>
    SPECIES.filter((s) => (!element || s.element === element) && (!grade || s.grade === grade));

  /* ── 몬스터 ──────────────────────────────────────────────── */

  function makeMonster(speciesIndex, level) {
    const m = {
      species: speciesIndex, level: level || 1, brain: 0, feel: 0, food: 100,
      evolved: false, exp: 0, passives: [], hp: 0, sp: 0,
      guarding: false, rage: 0, endured: false,
    };
    m.hp = maxHp(m);
    m.sp = maxSp(m);
    return m;
  }

  function stat(m, key) {
    const sp = speciesOf(m);
    let value = sp.base_stats[key] +
      Math.floor(sp.growth[key] * (m.level - 1) / B.growth.growth_divisor);
    value += Math.floor(m.brain / 10);
    if (m.evolved) value = Math.floor(value * B.condition.evolution_bonus);
    if (m.food <= 0) value = Math.floor(value * B.condition.starving_penalty);
    return Math.max(1, value);
  }

  const maxHp = (m) =>
    B.vitals.hp_base + stat(m, "con") * B.vitals.hp_per_con + m.level * B.vitals.hp_per_level;
  const maxSp = (m) =>
    B.vitals.sp_base + stat(m, "int") * B.vitals.sp_per_int + m.level * B.vitals.sp_per_level;

  function baseSkillCost(m) {
    const c = B.skill_cost.base + Math.floor(m.level / 5) * B.skill_cost.per_five_levels;
    return m.evolved ? c * 2 : c;
  }

  const partyCost = (m) => B.party_cost[speciesOf(m).grade];
  const slotLimit = (m) => (m.evolved ? D.slots.evolved : D.slots.base);
  const alive = (m) => m.hp > 0;
  const monName = (m) => speciesOf(m).name;
  const monElement = (m) => speciesOf(m).element;

  function expToNext(m) { return B.experience.level_curve * m.level + 20; }

  function gainExp(m, amount, log) {
    m.exp += amount;
    while (m.level < B.experience.max_level && m.exp >= expToNext(m)) {
      m.exp -= expToNext(m);
      m.level += 1;
      m.hp = maxHp(m);
      m.sp = maxSp(m);
      log.push({ text: `${monName(m)}의 레벨이 ${m.level}이 되었다!`, kind: "gain" });
    }
  }

  function gainFeel(m, amount, log) {
    if (m.evolved) { m.feel = Math.min(B.condition.feel_max, m.feel + amount); return; }
    m.feel += amount;
    if (m.feel < B.condition.feel_max) return;
    m.feel = 0;
    m.evolved = true;
    m.hp = maxHp(m);
    log.push({
      text: `${monName(m)}의 교감도가 최대치에 달했다. 진화했다! (패시브 슬롯 ${slotLimit(m)}칸)`,
      kind: "gain",
    });
  }

  function restMonster(m) {
    m.hp = maxHp(m);
    m.sp = maxSp(m);
    m.guarding = false;
    m.rage = 0;
    m.endured = false;
  }

  /* ── 패시브 ──────────────────────────────────────────────── */

  const passiveById = (id) => D.passives.find((p) => p.id === id);

  function magnitude(m, kind) {
    let total = 0;
    for (const learned of m.passives) {
      const p = passiveById(learned.passive_id);
      if (p && p.kind === kind) total += p.levels[clamp(learned.level, 1, p.levels.length) - 1];
    }
    return total;
  }

  const hasKind = (m, kind) =>
    m.passives.some((l) => (passiveById(l.passive_id) || {}).kind === kind);

  function attackMultiplier(m, skill, advantaged) {
    let bonus = magnitude(m, skill ? "skill_up" : "physical_up");
    if (m.hp <= maxHp(m) * 0.3) bonus += magnitude(m, "desperate");
    bonus += magnitude(m, "rage") * Math.min(m.rage, 5);
    if (advantaged) bonus += magnitude(m, "affinity");
    return 1 + bonus;
  }

  const defenseMultiplier = (m, skill) =>
    Math.max(0.2, 1 - magnitude(m, skill ? "skill_guard" : "physical_guard"));
  const spCost = (m) =>
    Math.max(1, Math.round(baseSkillCost(m) * (1 - Math.min(0.7, magnitude(m, "sp_saver")))));
  const effectiveSpeed = (m) => stat(m, "spd") * (1 + magnitude(m, "speed_up"));
  const passiveLevel = (m, id) => {
    const found = m.passives.find((l) => l.passive_id === id);
    return found ? found.level : 0;
  };

  /* ── 규칙 ────────────────────────────────────────────────── */

  function elementMultiplier(attacker, defender) {
    const strong = B.element_chart.strong_against;
    if ((strong[attacker] || []).includes(defender)) return B.element_chart.advantage_multiplier;
    if ((strong[defender] || []).includes(attacker)) return B.element_chart.disadvantage_multiplier;
    return 1;
  }

  const physicalElementMultiplier = (a, d) =>
    1 + (elementMultiplier(a, d) - 1) * (B.element_chart.physical_weight || 0);

  function estimateDamage(attacker, defender, skill) {
    const s = B.damage;
    let attack, defense, multiplier;
    if (skill) {
      attack = stat(attacker, "mstr") * s.skill_attack_scale;
      defense = stat(defender, "int") * s.skill_defense_scale;
      multiplier = elementMultiplier(monElement(attacker), monElement(defender));
    } else {
      attack = stat(attacker, "str") * s.physical_attack_scale;
      defense = stat(defender, "dex") * s.physical_defense_scale;
      multiplier = physicalElementMultiplier(monElement(attacker), monElement(defender));
    }
    attack *= attackMultiplier(attacker, skill, multiplier > 1);
    defense *= 1 - Math.min(0.6, magnitude(attacker, "pierce"));
    let raw = (attack - defense) * multiplier;
    raw *= defenseMultiplier(defender, skill);
    return Math.max(s.minimum_damage, raw);
  }

  function rollDamage(attacker, defender, skill) {
    const s = B.damage;
    let attack, defense, multiplier;
    if (skill) {
      attack = stat(attacker, "mstr") * s.skill_attack_scale;
      defense = stat(defender, "int") * s.skill_defense_scale;
      multiplier = elementMultiplier(monElement(attacker), monElement(defender));
    } else {
      attack = stat(attacker, "str") * s.physical_attack_scale;
      defense = stat(defender, "dex") * s.physical_defense_scale;
      multiplier = physicalElementMultiplier(monElement(attacker), monElement(defender));
    }
    attack *= attackMultiplier(attacker, skill, multiplier > 1);
    defense *= 1 - Math.min(0.6, magnitude(attacker, "pierce"));

    let raw = (attack - defense) * multiplier;
    raw *= s.variance_min + rnd() * (s.variance_max - s.variance_min);
    const critical = rnd() < s.critical_chance + magnitude(attacker, "critical_up");
    if (critical) raw *= s.critical_multiplier;
    if (defender.guarding) {
      raw *= Math.max(0.1, 1 - (s.guard_reduction + magnitude(defender, "guard_master")));
    }
    raw *= defenseMultiplier(defender, skill);
    return { amount: Math.max(s.minimum_damage, Math.floor(raw)), critical, multiplier };
  }

  function fleeChance(runner, opponent) {
    const s = B.flee;
    const chance = s.base_chance +
      (effectiveSpeed(runner) - effectiveSpeed(opponent)) * s.speed_weight;
    return clamp(chance, s.min, s.max);
  }

  function captureChance(target, hero, ball, catcher) {
    const s = B.capture;
    if (target.level > hero.level) return 0;
    let chance = s.grade_base[speciesOf(target).grade];
    chance *= 1 - s.hp_weight * (target.hp / Math.max(1, maxHp(target)));
    chance *= (D.items[ball] || {}).capture_bonus || 1;
    if (monElement(target) === hero.element) chance *= s.same_element_bonus;
    if (catcher) chance *= 1 + magnitude(catcher, "hunter");
    return clamp(chance, 0, 0.95);
  }

  const expReward = (foe, auto) => {
    const s = B.experience;
    let amount = (s.base + s.per_level * foe.level) * s.grade_multiplier[speciesOf(foe).grade];
    if (auto) amount *= s.auto_battle_ratio;
    return Math.max(1, Math.floor(amount));
  };

  const goldReward = (foe) =>
    Math.max(1, Math.floor(foe.level * 3 * B.experience.grade_multiplier[speciesOf(foe).grade]));

  /* ── 주인공 ──────────────────────────────────────────────── */

  function makeHero(name, element) {
    return {
      name, element, level: 5, exp: 0, statPoints: 0, rankIndex: 0,
      gold: 500, guildRank: 99, rankPoints: 1000, wins: 0, losses: 0,
      islandLevel: 1, islandExp: 0, day: 1,
      lastGiftDay: 0, lastChestDay: 0, marketDay: 0, market: null,
      party: [], storage: [], items: { "포션": 5, "몬스터볼": 5, "에테르": 2 },
      seen: [], log: [],
    };
  }

  const rankName = (hero) => B.rank_party_points[hero.rankIndex].rank;

  function partyPoints(hero) {
    const extra = B.island.party_point_levels.filter((t) => hero.islandLevel >= t).length;
    return B.rank_party_points[hero.rankIndex].points + extra;
  }

  const usedPoints = (hero) => hero.party.reduce((sum, m) => sum + partyCost(m), 0);
  const alivePartyOf = (hero) => hero.party.filter(alive);
  const allMonsters = (hero) => hero.party.concat(hero.storage);

  function heroExpToNext(hero) { return B.experience.hero_level_curve * hero.level + 30; }

  function heroGainExp(hero, amount, log) {
    hero.exp += amount;
    while (hero.level < B.experience.max_level && hero.exp >= heroExpToNext(hero)) {
      hero.exp -= heroExpToNext(hero);
      hero.level += 1;
      hero.statPoints += 3;
      log.push({ text: `${hero.name}의 레벨이 ${hero.level}이 되었다!`, kind: "gain" });
    }
  }

  function promote(hero, log) {
    const target = Math.min(B.rank_party_points.length - 1, Math.floor((99 - hero.guildRank) / 9));
    while (hero.rankIndex < target) {
      hero.rankIndex += 1;
      log.push({
        text: `테이머 등급이 ${rankName(hero)}(으)로 올랐다. 파티 포인트 ${partyPoints(hero)}`,
        kind: "gain",
      });
    }
  }

  function catchMonster(hero, m) {
    if (!hero.seen.includes(monName(m))) hero.seen.push(monName(m));
    if (usedPoints(hero) + partyCost(m) <= partyPoints(hero)) {
      hero.party.push(m);
      return `${monName(m)}(이)가 파티에 합류했다.`;
    }
    hero.storage.push(m);
    return `${monName(m)}(은)는 파티 포인트가 모자라 보관함으로 갔다.`;
  }

  const addItem = (hero, name, count) => {
    hero.items[name] = (hero.items[name] || 0) + (count || 1);
  };

  function takeItem(hero, name, count) {
    count = count || 1;
    if ((hero.items[name] || 0) < count) return false;
    hero.items[name] -= count;
    if (hero.items[name] === 0) delete hero.items[name];
    return true;
  }

  /* ── 사냥터 ──────────────────────────────────────────────── */

  const AREAS = D.world.areas.map((a) => {
    const low = GRADES.indexOf(a.grades[0]);
    const high = GRADES.indexOf(a.grades[1]);
    let pool = SPECIES
      .map((s, i) => ({ s, i }))
      .filter(({ s }) => s.element === a.element &&
        gradeIndex(s) >= low && gradeIndex(s) <= high)
      .map(({ i }) => i);
    if (pool.length < 3) {
      pool = SPECIES.map((s, i) => ({ s, i }))
        .filter(({ s }) => gradeIndex(s) >= low && gradeIndex(s) <= high)
        .map(({ i }) => i);
    }
    return {
      name: a.name, element: a.element,
      minLevel: a.levels[0], maxLevel: a.levels[1],
      minGrade: low, maxGrade: high, pool, island: false,
    };
  });

  const ISLAND = {
    name: "미지의 섬", element: "전속성", minLevel: 1, maxLevel: 99,
    minGrade: 0, maxGrade: GRADES.length - 1,
    pool: SPECIES.map((_, i) => i), island: true,
  };

  function islandGradeCap(islandLevel) {
    let cap = GRADES.indexOf("rare");
    for (const [grade, level] of Object.entries(B.island.grade_unlock)) {
      if (islandLevel >= level) cap = Math.max(cap, GRADES.indexOf(grade));
    }
    return cap;
  }

  function spawn(area, hero, islandLevel) {
    let pool = area.pool, floor = area.minGrade, low, high;
    if (area.island) {
      const cap = islandGradeCap(islandLevel);
      floor = Math.max(0, cap - 2);
      pool = pool.filter((i) => gradeIndex(SPECIES[i]) <= cap &&
        gradeIndex(SPECIES[i]) >= floor);
      if (!pool.length) pool = area.pool;
      low = Math.max(1, hero.level - 2);
      high = hero.level + 2;
    } else {
      low = area.minLevel;
      high = area.maxLevel;
    }
    const weights = pool.map((i) => Math.max(1, 64 >> (Math.max(0, gradeIndex(SPECIES[i]) - floor) * 2)));
    // 적 수는 파티 규모를 넘지 않는다. 파티 한 마리에 2:1이면 선택의 여지가 없다.
    const partySize = alivePartyOf(hero).length;
    const count = partySize < 2 || rnd() < 0.7 ? 1 : 2;
    const foes = [];
    for (let i = 0; i < count; i++) {
      foes.push(makeMonster(weightedPick(pool, weights), randInt(low, high)));
    }
    return foes;
  }

  /* ── 전투 ────────────────────────────────────────────────── */

  function makeBattle(hero, foes, options) {
    options = options || {};
    return {
      hero, allies: alivePartyOf(hero), enemies: foes,
      turn: 0, log: [], result: null, captured: null,
      capturable: options.capturable !== false,
      mode: options.mode || null, rival: options.rival || null,
      auto: false, gold: 0, drops: {},
    };
  }

  const livingIn = (side) => side.filter(alive);
  const isAlly = (fight, m) => fight.allies.indexOf(m) >= 0;
  const foesOf = (fight, m) => (isAlly(fight, m) ? fight.enemies : fight.allies);

  function autoAction(fight, actor) {
    const targets = livingIn(foesOf(fight, actor));
    if (!targets.length) return { kind: "guard", actor };
    const target = targets.reduce((a, b) => (a.hp <= b.hp ? a : b));
    const physical = estimateDamage(actor, target, false);
    if (actor.sp < spCost(actor)) return { kind: "attack", actor, target };
    const skill = estimateDamage(actor, target, true);
    return { kind: skill > physical ? "skill" : "attack", actor, target };
  }

  function say(fight, text, kind, actor) {
    fight.log.push({
      text, kind: kind || "",
      side: actor ? (isAlly(fight, actor) ? "ally" : "foe") : "",
    });
  }

  function runRound(fight, allyActions) {
    if (fight.result) return;
    fight.turn += 1;

    const queue = allyActions.slice();
    for (const foe of livingIn(fight.enemies)) queue.push(autoAction(fight, foe));
    queue.sort((a, b) => {
      const speed = effectiveSpeed(b.actor) - effectiveSpeed(a.actor);
      if (speed) return speed;
      const priority = (hasKind(b.actor, "first_strike") ? 1 : 0) -
        (hasKind(a.actor, "first_strike") ? 1 : 0);
      return priority || rnd() - 0.5;
    });

    for (const m of fight.allies.concat(fight.enemies)) m.guarding = false;
    for (const action of queue) if (action.kind === "guard") action.actor.guarding = true;

    for (const action of queue) {
      if (fight.result || !alive(action.actor)) continue;
      resolve(fight, action);
      checkEnd(fight);
    }
    tickRegen(fight);
    checkEnd(fight);
  }

  function tickRegen(fight) {
    for (const m of livingIn(fight.allies).concat(livingIn(fight.enemies))) {
      const ratio = magnitude(m, "regen");
      if (ratio <= 0 || m.hp >= maxHp(m)) continue;
      const healed = Math.min(maxHp(m) - m.hp, Math.max(1, Math.floor(maxHp(m) * ratio)));
      m.hp += healed;
      say(fight, `${monName(m)}의 재생. HP ${healed} 회복`, "gain", m);
    }
  }

  function targetFor(fight, action) {
    if (action.target && alive(action.target)) return action.target;
    return livingIn(foesOf(fight, action.actor))[0] || null;
  }

  function applyDamage(fight, attacker, target, amount, physical) {
    if (amount >= target.hp && hasKind(target, "endure") && !target.endured) {
      amount = target.hp - 1;
      target.endured = true;
      say(fight, `${monName(target)}의 근성! HP 1로 버텼다.`, "", target);
    }
    target.hp = Math.max(0, target.hp - amount);
    target.rage += 1;

    const drain = magnitude(attacker, "drain");
    if (drain > 0 && alive(attacker)) {
      const healed = Math.min(maxHp(attacker) - attacker.hp, Math.max(1, Math.floor(amount * drain)));
      if (healed > 0) {
        attacker.hp += healed;
        say(fight, `${monName(attacker)}의 흡혈. HP ${healed} 회복`, "gain", attacker);
      }
    }

    if (!alive(target)) { say(fight, `${monName(target)}(은)는 쓰러졌다.`, "down", target); return; }
    if (physical && rnd() < magnitude(target, "counter")) {
      const back = rollDamage(target, attacker, false).amount;
      attacker.hp = Math.max(0, attacker.hp - back);
      say(fight, `${monName(target)}의 반격! ${monName(attacker)}에게 ${back}`, "", target);
      if (!alive(attacker)) say(fight, `${monName(attacker)}(은)는 쓰러졌다.`, "down", attacker);
    }
  }

  function resolve(fight, action) {
    const actor = action.actor;
    if (action.kind === "guard") { say(fight, `${monName(actor)}(은)는 방어했다.`, "", actor); return; }

    if (action.kind === "flee") {
      const foes = livingIn(fight.enemies);
      if (!foes.length) return;
      const fastest = foes.reduce((a, b) => (effectiveSpeed(a) >= effectiveSpeed(b) ? a : b));
      if (rnd() < fleeChance(actor, fastest)) { say(fight, "도망쳤다.", "", actor); fight.result = "fled"; }
      else say(fight, "도망치지 못했다.", "", actor);
      return;
    }

    if (action.kind === "item") {
      useItemInBattle(fight, actor, action.item);
      return;
    }

    if (action.kind === "capture") {
      const target = targetFor(fight, action);
      if (!target) return;
      if (!fight.capturable) { say(fight, "포획할 수 없는 전투다.", "", actor); return; }
      if (target.level > fight.hero.level) {
        say(fight, `내 레벨이 낮아 잡을 수 없다. (Lv${target.level} 필요)`, "", actor);
        return;
      }
      const ball = action.item || "몬스터볼";
      if (!takeItem(fight.hero, ball)) { say(fight, `${ball}(이)가 없다.`, "", actor); return; }
      if (rnd() < captureChance(target, fight.hero, ball, actor)) {
        say(fight, `포획 성공! ${monName(target)}(을)를 잡았다.`, "gain", actor);
        fight.captured = target;
        target.hp = 0;
        fight.result = "captured";
      } else say(fight, "포획 실패", "", actor);
      return;
    }

    const skill = action.kind === "skill";
    if (skill && actor.sp < spCost(actor)) {
      say(fight, `${monName(actor)}: SP가 모자라 물리 공격으로 바꿨다.`, "", actor);
      resolve(fight, { kind: "attack", actor, target: action.target });
      return;
    }
    const target = targetFor(fight, action);
    if (!target) return;
    if (skill) actor.sp -= spCost(actor);

    const roll = rollDamage(actor, target, skill);
    const move = skill ? speciesOf(actor).active_skill.name : "물리 공격";
    let text = `${monName(actor)}의 ${move}! ${monName(target)}에게 ${roll.amount}`;
    if (roll.critical) text += " 크리티컬!";
    if (skill && roll.multiplier > 1) text += " 효과가 굉장했다!";
    if (skill && roll.multiplier < 1) text += " 효과가 별로였다...";
    say(fight, text, roll.critical ? "crit" : "", actor);
    applyDamage(fight, actor, target, roll.amount, !skill);
  }

  function useItemInBattle(fight, actor, name) {
    const hero = fight.hero;
    const entry = D.items[name] || {};
    if (!entry.effect) { say(fight, `${name}(은)는 전투 중에 쓸 수 없다.`, "", actor); return; }
    if (!takeItem(hero, name)) { say(fight, `${name}(이)가 없다.`, "", actor); return; }
    const effect = entry.effect;
    if (effect.hp && alive(actor)) {
      const healed = Math.min(effect.hp, maxHp(actor) - actor.hp);
      actor.hp += healed;
      say(fight, `${name}으로 ${monName(actor)}의 HP ${healed} 회복`, "gain", actor);
    }
    if (effect.sp) {
      const healed = Math.min(effect.sp, maxSp(actor) - actor.sp);
      actor.sp += healed;
      say(fight, `${name}으로 ${monName(actor)}의 SP ${healed} 회복`, "gain", actor);
    }
  }

  function checkEnd(fight) {
    if (fight.result) return;
    if (!livingIn(fight.enemies).length) fight.result = "win";
    else if (!livingIn(fight.allies).length) fight.result = "lose";
  }

  function finishBattle(fight) {
    const hero = fight.hero;
    const out = [];
    const won = fight.result === "win" || fight.result === "captured";
    const survivors = livingIn(fight.allies);

    if (won) {
      let total = 0;
      for (const foe of fight.enemies) if (!alive(foe)) total += expReward(foe, fight.auto);
      if (survivors.length && total) {
        out.push({ text: `경험치 ${total} 획득`, kind: "gain" });
        // 경험치는 나눠 갖지 않는다. 나누면 파티를 늘린 플레이어가 벌을 받는다.
        for (const m of survivors) gainExp(m, total, out);
        // 쓰러진 몬스터도 절반은 받는다. 안 그러면 한 번 뒤처진 몬스터가 영영 못 큰다.
        for (const m of fight.allies) {
          if (!alive(m)) gainExp(m, Math.floor(total * B.experience.fallen_ratio), out);
        }
        heroGainExp(hero, total, out);
      }
      // 승리하면 조금 회복한다. 그래야 쉬지 않고 몇 판은 이어갈 수 있다.
      for (const m of survivors) {
        m.hp = Math.min(maxHp(m), m.hp + Math.floor(maxHp(m) * (B.condition.recover_after_win || 0)));
      }
      for (const foe of fight.enemies) {
        if (alive(foe)) continue;
        fight.gold += goldReward(foe);
        const candidates = D.drops[speciesOf(foe).grade] || [];
        if (candidates.length && rnd() < 0.45) {
          const item = pick(candidates);
          fight.drops[item] = (fight.drops[item] || 0) + 1;
        }
      }
      if (fight.gold) { hero.gold += fight.gold; out.push({ text: `골드 ${fight.gold} 획득`, kind: "gain" }); }
      for (const [item, count] of Object.entries(fight.drops)) {
        addItem(hero, item, count);
        out.push({ text: `${item} x${count} 획득`, kind: "gain" });
      }
    }

    for (const m of fight.allies) {
      const ratio = hasKind(m, "gourmet") ? 0.5 : 1;
      const before = m.food;
      m.food = Math.max(0, m.food - Math.max(1, Math.round(B.condition.food_per_battle * ratio)));
      if (before > 0 && m.food === 0) out.push({ text: `${monName(m)}의 허기도가 0이다. 능력치가 떨어졌다.` });
      if (alive(m)) gainFeel(m, Math.floor(B.condition.feel_per_battle * (1 + magnitude(m, "bond"))), out);
      else m.feel = Math.max(0, m.feel - B.condition.feel_loss_on_death);
      m.rage = 0;
      m.endured = false;
    }

    if (fight.captured) {
      const fresh = makeMonster(fight.captured.species, fight.captured.level);
      fresh.brain = fight.captured.brain;
      fresh.passives = fight.captured.passives.map((l) => ({ ...l }));
      out.push({ text: catchMonster(hero, fresh), kind: "gain" });
    }
    for (const foe of fight.enemies) if (!hero.seen.includes(monName(foe))) hero.seen.push(monName(foe));

    if (fight.mode) settleRanked(hero, fight, won, out);
    fight.log = fight.log.concat(out);
    return out;
  }

  /* ── 네트워크 (오프라인 흉내) ──────────────────────────────── */

  const TAMER_NAMES = ["하람", "노아", "제이", "린", "서우", "카이런", "미르", "타린", "유하", "벨",
    "이든", "소야", "라온", "테오", "나리", "쥰", "아린", "도윤", "세라", "훈"];
  const TITLES = ["떠돌이", "수집가", "추격자", "은둔", "폭풍", "새벽", "그림자", "불꽃", "고요", "질주"];
  const rivalName = () => `${pick(TITLES)} ${pick(TAMER_NAMES)}`;

  function makeRival(hero) {
    const points = Math.max(100, hero.rankPoints + randInt(-80, 80));
    const tier = clamp(Math.floor((points - 800) / 250), 0, GRADES.length - 1);
    const size = clamp(1 + Math.floor(partyPoints(hero) / 5), 1, 3);
    const party = [];
    for (let i = 0; i < size; i++) {
      const grade = GRADES[clamp(randInt(Math.max(0, tier - 1), tier), 0, GRADES.length - 1)];
      const pool = filterSpecies(null, grade);
      const sp = pick(pool);
      party.push(makeMonster(byName(sp.name), Math.max(1, hero.level + randInt(-3, 3))));
    }
    return { name: rivalName(), rankPoints: points, party };
  }

  function settleRanked(hero, fight, won, out) {
    const s = B.network;
    let delta = 0;
    if (fight.mode !== "친선배틀") {
      delta = won ? s.rank_point_win : -s.rank_point_loss;
      hero.rankPoints = Math.max(0, hero.rankPoints + delta);
      out.push({ text: `랭킹 포인트 ${delta > 0 ? "+" : ""}${delta} (${hero.rankPoints})`, kind: won ? "gain" : "" });
      // 파티 포인트가 늘어야 상위 등급을 파티에 넣을 수 있다. 이 경로가 없으면 common에 갇힌다.
      if (won && hero.guildRank > 1) {
        hero.guildRank -= 1;
        out.push({ text: `길드 랭킹 ${hero.guildRank}위`, kind: "gain" });
        promote(hero, out);
      }
    }
    if (won) hero.wins += 1; else hero.losses += 1;
    hero.log.unshift({
      day: hero.day, mode: fight.mode, opponent: fight.rival ? fight.rival.name : "?",
      result: won ? "승" : "패", delta,
    });
    hero.log = hero.log.slice(0, 20);
  }

  function marketPrice(m) {
    const s = B.network;
    let price = m.level * s.market_price_per_level * s.market_grade_multiplier[speciesOf(m).grade];
    price *= 1 + m.brain / 50;
    if (m.evolved) price *= 1.5;
    return Math.max(50, Math.floor(price));
  }

  function marketListings(hero) {
    if (hero.market && hero.marketDay === hero.day) return hero.market;
    const listings = [];
    for (let i = 0; i < 5; i++) {
      const tier = clamp(randInt(0, 1 + Math.floor(hero.islandLevel / 12)), 0, GRADES.length - 1);
      const sp = pick(filterSpecies(null, GRADES[tier]));
      const m = makeMonster(byName(sp.name), Math.max(1, hero.level + randInt(-4, 4)));
      m.brain = randInt(0, 5);
      listings.push({ monster: m, price: Math.floor(marketPrice(m) * (0.9 + rnd() * 0.5)), seller: rivalName() });
    }
    hero.market = listings;
    hero.marketDay = hero.day;
    return listings;
  }

  function islandGain(hero, amount, visiting) {
    const s = B.island;
    const out = [];
    if (visiting) amount = Math.floor(amount * s.visit_experience_bonus);
    hero.islandExp += amount;
    let need = s.experience_per_level * hero.islandLevel;
    while (hero.islandLevel < s.max_level && hero.islandExp >= need) {
      hero.islandExp -= need;
      hero.islandLevel += 1;
      out.push({ text: `미지의 섬 레벨 ${hero.islandLevel}`, kind: "gain" });
      if (s.party_point_levels.includes(hero.islandLevel)) {
        out.push({ text: `파티 포인트가 늘었다. (${partyPoints(hero)})`, kind: "gain" });
      }
      need = s.experience_per_level * hero.islandLevel;
    }
    return out;
  }

  /* ── 공방 ────────────────────────────────────────────────── */

  const fusionRate = (grade, catalyst) => {
    const rate = B.fusion.success_rate[grade];
    if (rate === undefined) return 0;
    return Math.min(0.95, rate + (catalyst ? D.items["조합촉매"].fuse_bonus : 0));
  };
  const fusionCost = (grade) => B.fusion.cost_gold[grade] || 0;

  function fuse(hero, first, second, catalyst) {
    if (first === second) return ["같은 몬스터를 두 번 넣을 수는 없다."];
    const grade = speciesOf(first).grade;
    if (grade !== speciesOf(second).grade) return ["조합은 같은 등급끼리만 된다."];
    if (grade === GRADES[GRADES.length - 1]) return ["god 등급은 더 위가 없다."];
    const cost = fusionCost(grade);
    if (hero.gold < cost) return [`골드가 모자란다. (${cost} 필요)`];
    if (catalyst && !(hero.items["조합촉매"] > 0)) return ["조합촉매가 없다."];

    hero.gold -= cost;
    if (catalyst) takeItem(hero, "조합촉매");

    const out = [];
    const success = rnd() < fusionRate(grade, catalyst);
    const index = GRADES.indexOf(grade);
    const nextGrade = GRADES[success ? index + 1 : Math.max(0, index - 1)];
    out.push(success ? "조합 성공!" : "조합 실패... 등급이 떨어졌다.");

    const element = pick([monElement(first), monElement(second)]);
    let pool = filterSpecies(element, nextGrade);
    if (!pool.length) pool = filterSpecies(null, nextGrade);
    const result = makeMonster(byName(pick(pool).name), Math.max(1, Math.floor((first.level + second.level) / 2)));
    result.brain = Math.floor((first.brain + second.brain) / 2);

    const inherited = [];
    for (const learned of first.passives.concat(second.passives)) {
      if (inherited.some((l) => l.passive_id === learned.passive_id)) continue;
      if (rnd() < B.fusion.inherit_passive_chance) inherited.push({ ...learned });
    }
    result.passives = inherited.slice(0, slotLimit(result));
    if (result.passives.length) {
      out.push("계승한 패시브: " + result.passives.map((l) => passiveById(l.passive_id).name).join(", "));
    }

    for (const material of [first, second]) {
      let at = hero.party.indexOf(material);
      if (at >= 0) hero.party.splice(at, 1);
      else { at = hero.storage.indexOf(material); if (at >= 0) hero.storage.splice(at, 1); }
    }
    out.push(catchMonster(hero, result));
    return out;
  }

  function enhanceRate(m, catalyst) {
    const s = B.enhance;
    let rate = s.base_rate - s.decay_per_point * m.brain;
    if (catalyst) rate += D.items["강화촉매"].enhance_bonus;
    return Math.min(0.95, Math.max(s.min_rate, rate));
  }
  const enhanceCost = (m) => B.enhance.cost_gold_per_point * (m.brain + 1);

  function enhance(hero, m, catalyst) {
    if (m.brain >= B.enhance.max_brain) return [`${monName(m)}의 지능은 이미 최대다.`];
    const cost = enhanceCost(m);
    if (hero.gold < cost) return [`골드가 모자란다. (${cost} 필요)`];
    if (catalyst && !(hero.items["강화촉매"] > 0)) return ["강화촉매가 없다."];
    hero.gold -= cost;
    if (catalyst) takeItem(hero, "강화촉매");
    const rate = enhanceRate(m, catalyst);
    if (rnd() < rate) { m.brain += 1; return [`강화 성공! BRAIN ${m.brain}`]; }
    return ["강화 실패..."];
  }

  function attachCost(m, id) {
    const p = passiveById(id);
    const s = B.skill_craft;
    const level = passiveLevel(m, id);
    let gold = s.attach_gold;
    let materials = { ...p.materials };
    if (level) {
      gold = Math.floor(gold * s.level_up_gold_multiplier * level);
      materials = Object.fromEntries(Object.entries(materials).map(([k, v]) => [k, v * (level + 1)]));
    }
    return { gold, materials };
  }

  function attachPassive(hero, m, id) {
    const p = passiveById(id);
    const level = passiveLevel(m, id);
    if (level === 0 && m.passives.length >= slotLimit(m)) {
      return [`패시브 슬롯이 찼다. (${slotLimit(m)}칸, 진화하면 늘어난다)`];
    }
    if (level >= p.levels.length) return [`${p.name}(은)는 이미 최대 레벨이다.`];
    const { gold, materials } = attachCost(m, id);
    if (hero.gold < gold) return [`골드가 모자란다. (${gold} 필요)`];
    const missing = Object.entries(materials)
      .filter(([name, count]) => (hero.items[name] || 0) < count)
      .map(([name, count]) => `${name} ${count - (hero.items[name] || 0)}개`);
    if (missing.length) return ["재료가 모자란다: " + missing.join(", ")];

    hero.gold -= gold;
    for (const [name, count] of Object.entries(materials)) takeItem(hero, name, count);
    if (level) {
      m.passives.find((l) => l.passive_id === id).level += 1;
      return [`${p.name} Lv${level + 1}`];
    }
    m.passives.push({ passive_id: id, level: 1 });
    return [`${monName(m)}(이)가 ${p.name}(을)를 익혔다.`];
  }

  /* ── 저장 ────────────────────────────────────────────────── */

  const SAVE_KEY = "elemental-tamer/save/v1";
  const saveGame = (hero) => {
    try { localStorage.setItem(SAVE_KEY, JSON.stringify(hero)); return true; }
    catch (e) { return false; }
  };
  const loadGame = () => {
    try {
      const raw = localStorage.getItem(SAVE_KEY);
      if (!raw) return null;
      const hero = JSON.parse(raw);
      for (const m of hero.party.concat(hero.storage)) {
        m.hp = Math.min(m.hp, maxHp(m));
        m.sp = Math.min(m.sp, maxSp(m));
      }
      return hero;
    } catch (e) { return null; }
  };
  const clearGame = () => { try { localStorage.removeItem(SAVE_KEY); } catch (e) { /* 무시 */ } };

  window.Game = {
    B, SPECIES, GRADES, ELEMENTS, STATS, STAT_LABEL, AREAS, ISLAND,
    makeMonster, speciesOf, gradeIndex, byName, filterSpecies,
    stat, maxHp, maxSp, spCost, partyCost, slotLimit, alive, monName, monElement,
    restMonster, passiveById, passiveLevel, magnitude, hasKind,
    elementMultiplier, physicalElementMultiplier, estimateDamage, rollDamage,
    captureChance, fleeChance, expReward, goldReward, expToNext,
    makeHero, rankName, partyPoints, usedPoints, alivePartyOf, allMonsters,
    catchMonster, addItem, takeItem, promote,
    spawn, makeBattle, autoAction, runRound, finishBattle, livingIn, isAlly,
    makeRival, marketPrice, marketListings, islandGain, islandGradeCap,
    fuse, fusionRate, fusionCost, enhance, enhanceRate, enhanceCost,
    attachPassive, attachCost,
    saveGame, loadGame, clearGame, pick, randInt, rnd,
  };
})();
