/* ============================================================
   게임 엔진 — 월드 / 플레이어 / 몬스터 / 스킬 / 웨이브
   좌표는 전부 "월드 단위"(평면 좌표). 아이소메트릭 변환은 render.js 담당.
   ============================================================ */
var Engine = (function(){
  'use strict';

  var TILE = 64;                 /* 타일 1칸 = 월드 64단위 (스프라이트 원본 크기 기준) */
  var MAP_W = 46, MAP_H = 46;
  var WORLD_W = MAP_W * TILE, WORLD_H = MAP_H * TILE;

  var W = null;                  /* 월드 상태 */

  /* ---------- 유틸 ---------------------------------------- */
  function rnd(a, b){ return a + Math.random() * (b - a); }
  function clamp(v, a, b){ return v < a ? a : v > b ? b : v; }
  function dist2(ax, ay, bx, by){ var dx = ax-bx, dy = ay-by; return dx*dx + dy*dy; }
  function angDiff(a, b){
    var d = (a - b) % (Math.PI*2);
    if(d > Math.PI) d -= Math.PI*2;
    if(d < -Math.PI) d += Math.PI*2;
    return d;
  }

  /* ---------- 맵 생성 -------------------------------------- */
  function genMap(){
    var tiles = new Array(MAP_W * MAP_H), props = [];
    var i, tx, ty;
    for(ty = 0; ty < MAP_H; ty++){
      for(tx = 0; tx < MAP_W; tx++){
        var n = Math.sin(tx*0.7)*Math.cos(ty*0.55) + Math.sin((tx+ty)*0.31);
        var kind = 'grass';
        if(n > 1.15) kind = 'dirt';
        else if(n < -1.2) kind = 'dark';
        var edge = (tx < 2 || ty < 2 || tx > MAP_W-3 || ty > MAP_H-3);
        if(edge) kind = 'stone';
        tiles[ty*MAP_W + tx] = { kind: kind, v: (tx*31 + ty*17) % 97 };
      }
    }
    /* 중앙 광장은 돌바닥 */
    var cx = MAP_W>>1, cy = MAP_H>>1;
    for(ty = cy-4; ty <= cy+4; ty++)
      for(tx = cx-4; tx <= cx+4; tx++)
        if(Math.abs(tx-cx) + Math.abs(ty-cy) <= 6) tiles[ty*MAP_W+tx].kind = 'stone';

    /* 지형지물 배치 (전투 방해 없이 장식만) */
    var kinds = ['tree','tree','tree','tree','rock','rock','bush','bush','crystal'];
    for(i = 0; i < 150; i++){
      var px = rnd(TILE*3, WORLD_W - TILE*3), py = rnd(TILE*3, WORLD_H - TILE*3);
      if(dist2(px, py, WORLD_W/2, WORLD_H/2) < (TILE*7)*(TILE*7)) continue;
      props.push({ x: px, y: py, kind: kinds[(Math.random()*kinds.length)|0] });
    }
    /* 광장 둘레의 횃불 */
    for(i = 0; i < 8; i++){
      var a = i / 8 * Math.PI * 2;
      props.push({ x: WORLD_W/2 + Math.cos(a)*TILE*5.5, y: WORLD_H/2 + Math.sin(a)*TILE*5.5, kind: 'torch' });
    }
    return { tiles: tiles, props: props };
  }

  /* ---------- 플레이어 ------------------------------------- */
  function jobOf(p){ return p.job2 || p.cls; }
  function weaponOf(p){ return p.job2 ? JOB2_DB[p.job2].weapon : CLASS_DB[p.cls].weapon; }
  function lookOf(p){ return p.job2 ? JOB2_DB[p.job2].look : CLASS_DB[p.cls].look; }
  function artOf(p){ return p.job2 ? JOB2_DB[p.job2].art : CLASS_DB[p.cls].art; }
  function jobName(p){ return p.job2 ? JOB2_DB[p.job2].name : CLASS_DB[p.cls].name; }

  /* 레벨/전직을 반영한 스탯 재계산 */
  function recalc(p){
    var C = CLASS_DB[p.cls], J = p.job2 ? JOB2_DB[p.job2] : null;
    var s = { hp:0, mp:0, atk:0, matk:0, def:0, crit:0, spd:C.base.spd };
    var k;
    for(k in C.base) if(k !== 'spd') s[k] = C.base[k];

    var l1 = Math.min(p.level, JOB2_LEVEL) - 1;          /* 1차 성장 구간 */
    var l2 = Math.max(0, p.level - JOB2_LEVEL);          /* 2차 성장 구간 */
    for(k in C.grow) s[k] += C.grow[k] * l1;

    var g2 = J ? J.grow : C.grow;
    for(k in g2) s[k] += g2[k] * l2;

    if(J){
      for(k in J.add) s[k] = (s[k] || 0) + J.add[k];
      if(J.add.spd) s.spd = C.base.spd + J.add.spd;
    }

    p.max = {
      hp: Math.round(s.hp), mp: Math.round(s.mp),
      atk: Math.round(s.atk), matk: Math.round(s.matk),
      def: Math.round(s.def), crit: s.crit, spd: s.spd
    };
    p.hp = Math.min(p.hp || p.max.hp, p.max.hp);
    p.mp = Math.min(p.mp === undefined ? p.max.mp : p.mp, p.max.mp);
  }

  /* 버프 합산치 */
  function mods(p){
    var m = { atk:0, matk:0, def:0, spd:0, aspd:0, crit:0, lifesteal:0, regen:0, mpregen:0, thorns:0 };
    for(var i = 0; i < p.buffs.length; i++){
      var b = p.buffs[i].mod;
      for(var k in b) if(m[k] !== undefined) m[k] += b[k];
    }
    return m;
  }

  /* 실효 스탯 */
  function stat(p, key){
    var m = mods(p);
    if(key === 'atk')  return p.max.atk  * (1 + m.atk);
    if(key === 'matk') return p.max.matk * (1 + m.matk);
    if(key === 'def')  return p.max.def  * (1 + m.def);
    if(key === 'spd')  return p.max.spd  * (1 + m.spd);
    if(key === 'crit') return p.max.crit + m.crit;
    return p.max[key] || 0;
  }

  /* 배울 수 있는 스킬(레벨 충족) */
  function learned(p){
    var out = [], list = skillsOfJob(jobOf(p));
    for(var i = 0; i < list.length; i++) if(p.level >= list[i].lv) out.push(list[i]);
    return out;
  }

  function makePlayer(cls){
    var p = {
      cls: cls, job2: null, level: 1, xp: 0,
      x: WORLD_W/2, y: WORLD_H/2, vx: 0, vy: 0,
      r: 22, aim: 0, faceDir: 's', flip: false,
      anim: 'idle', frame: 0, animT: 0,
      hp: 1, mp: 1, shield: 0,
      buffs: [], cds: {}, atkCd: 0,
      slots: { 1:null, 2:null, 3:null, 4:null, R:null },
      dash: null, invuln: 0, hitFlash: 0, dead: false,
      kills: 0
    };
    recalc(p);
    p.hp = p.max.hp; p.mp = p.max.mp;
    autoBind(p);
    return p;
  }

  /* 빈 슬롯에 새 스킬 자동 등록 */
  function autoBind(p){
    var ls = learned(p), order = ['R', 1, 2, 3, 4], i, j;
    for(i = 0; i < ls.length; i++){
      var id = ls[i].id, used = false;
      for(j = 0; j < order.length; j++) if(p.slots[order[j]] === id) used = true;
      if(used) continue;
      for(j = 0; j < order.length; j++){
        if(!p.slots[order[j]]){ p.slots[order[j]] = id; break; }
      }
    }
  }

  function bindSkill(slot, id){
    var p = W.player, k;
    for(k in p.slots) if(p.slots[k] === id) p.slots[k] = null;   /* 중복 등록 방지 */
    p.slots[slot] = id;
  }

  /* ---------- 초기화 --------------------------------------- */
  function init(cls){
    var map = genMap();
    W = {
      tiles: map.tiles, props: map.props,
      mapW: MAP_W, mapH: MAP_H, tile: TILE, worldW: WORLD_W, worldH: WORLD_H,
      player: makePlayer(cls),
      mobs: [], shots: [], zones: [], fx: [], texts: [], orbs: [], timers: [], corpses: [],
      wave: 0, waveState: 'ready', waveT: 2.5, spawnQueue: [], spawnT: 0,
      time: 0, paused: false, boss: null, msg: null, msgT: 0
    };
    return W;
  }

  function loadPlayer(data){
    var p = makePlayer(data.cls);
    p.job2 = data.job2 || null;
    p.level = data.level || 1;
    p.xp = data.xp || 0;
    p.kills = data.kills || 0;
    recalc(p);
    p.hp = p.max.hp; p.mp = p.max.mp;
    p.slots = { 1:null, 2:null, 3:null, 4:null, R:null };
    if(data.slots){
      var ls = learned(p), ok = {}, i;
      for(i = 0; i < ls.length; i++) ok[ls[i].id] = true;
      for(var k in data.slots) if(data.slots[k] && ok[data.slots[k]]) p.slots[k] = data.slots[k];
    }
    autoBind(p);
    W.player = p;
    W.wave = Math.max(0, (data.wave || 1) - 1);
    return p;
  }

  /* ---------- 메시지 / 이펙트 ------------------------------ */
  function say(text, dur){ W.msg = text; W.msgT = dur || 2.2; }

  function fx(o){ o.t = 0; o.dur = o.dur || 0.3; W.fx.push(o); return o; }

  function dmgText(x, y, val, kind){
    W.texts.push({ x: x, y: y, v: val, kind: kind || 'dmg', t: 0, dur: 0.85, vy: -30 - Math.random()*14, vx: rnd(-14, 14) });
  }

  function timer(delay, fn){ W.timers.push({ t: delay, fn: fn }); }

  /* 스프라이트 이펙트 한 장 재생 (assets/fx 의 8프레임 시트) */
  function artFx(sheet, x, y, size, dur){
    if(!sheet) return;
    W.fx.push({ type:'art', sheet: sheet, x: x, y: y, size: size || 160,
                t: 0, dur: dur || 0.42, seed: Math.random() });
  }

  /* ---------- 전투 ----------------------------------------- */
  function hitMob(m, dmg, opt){
    opt = opt || {};
    if(m.dead) return 0;
    var p = W.player;
    var mit = 1 - m.def / (m.def + 180);
    var crit = false;
    var cc = stat(p, 'crit') + (opt.critBonus || 0);
    if(Math.random() * 100 < cc){ crit = true; dmg *= 1.75; }
    if(opt.execute && m.hp / m.maxhp <= opt.execute) dmg *= 2;
    var out = Math.max(1, Math.round(dmg * mit * rnd(0.94, 1.06)));

    m.hp -= out;
    m.flash = 0.13;
    m.hitDir = Math.atan2(m.y - p.y, m.x - p.x);   /* 맞은 방향 = 밀려나는 방향 */
    m.hitPush = 1;
    m.aggro = 6;
    dmgText(m.x, m.y - m.r - 6, out, crit ? 'crit' : 'dmg');
    fx({ type:'hit', x: m.x, y: m.y - m.r*0.4, col: EL_COLOR[opt.el] || '#fff', dur: 0.22 });

    /* 상태이상 */
    if(opt.dot) m.dots.push({ el: opt.dot.el, dps: out * opt.dot.dps, t: opt.dot.dur, tick: 0 });
    if(opt.slow) m.slow = { amt: opt.slow.amt, t: Math.max(m.slow ? m.slow.t : 0, opt.slow.dur) };
    if(opt.stun) m.stun = Math.max(m.stun, opt.stun);
    if(opt.freeze){ m.freeze = Math.max(m.freeze, opt.freeze); m.stun = Math.max(m.stun, opt.freeze); }
    if(opt.knock){
      var a = Math.atan2(m.y - p.y, m.x - p.x);
      m.kx = Math.cos(a) * opt.knock; m.ky = Math.sin(a) * opt.knock;
    }

    /* 흡혈 */
    var ls = mods(p).lifesteal + (opt.lifesteal || 0);
    if(ls > 0) healPlayer(out * ls);

    if(m.hp <= 0) killMob(m);
    return out;
  }

  function killMob(m){
    if(m.dead) return;
    m.dead = true;
    var p = W.player;
    p.kills++;
    addXp(Math.round(m.xp));
    W.corpses.push({ art: m.art, h: m.h, x: m.x, y: m.y, flip: m.flip,
                     dir: m.hitDir === undefined ? 0 : m.hitDir, t: 0, dur: 0.5, boss: m.boss });
    fx({ type:'death', x: m.x, y: m.y, col:'#e8e2d0', size: m.r, dur: 0.45 });
    /* 회복 구슬 드랍 */
    if(Math.random() < (m.boss ? 1 : 0.14)){
      var n = m.boss ? 6 : 1;
      for(var i = 0; i < n; i++)
        W.orbs.push({ x: m.x + rnd(-28,28), y: m.y + rnd(-28,28), kind: Math.random()<0.5?'hp':'mp', t: 0 });
    }
  }

  function healPlayer(v){
    var p = W.player;
    if(v <= 0 || p.dead) return;
    var before = p.hp;
    p.hp = Math.min(p.max.hp, p.hp + v);
    var real = p.hp - before;
    if(real >= 1) dmgText(p.x, p.y - 26, Math.round(real), 'heal');
  }

  function hurtPlayer(v, src){
    var p = W.player;
    if(p.dead || p.invuln > 0) return;
    var mit = 1 - stat(p, 'def') / (stat(p, 'def') + 180);
    var out = Math.max(1, Math.round(v * mit));
    if(p.shield > 0){
      var absorbed = Math.min(p.shield, out);
      p.shield -= absorbed; out -= absorbed;
      dmgText(p.x, p.y - 30, Math.round(absorbed), 'shield');
    }
    if(out > 0){
      p.hp -= out;
      dmgText(p.x, p.y - 26, out, 'taken');
      p.hitFlash = 0.2;
      p.invuln = 0.32;
    }
    /* 가시 반격 */
    var th = mods(p).thorns;
    if(th > 0 && src && !src.dead) hitMob(src, stat(p, 'matk') * th, { el:'ice', freeze:0.6 });
    if(p.hp <= 0) diePlayer();
  }

  function diePlayer(){
    var p = W.player;
    p.hp = 0; p.dead = true;
    fx({ type:'death', x: p.x, y: p.y, col:'#ff5a5a', size: 16, dur: 0.6 });
    say('쓰러졌다…', 3);
  }

  function revive(){
    var p = W.player;
    p.dead = false;
    p.hp = p.max.hp; p.mp = p.max.mp;
    p.shield = 0; p.buffs.length = 0; p.invuln = 2;
    p.x = WORLD_W/2; p.y = WORLD_H/2;
    p.xp = Math.max(0, Math.round(p.xp * 0.9));
    W.mobs.length = 0; W.shots.length = 0; W.zones.length = 0; W.corpses.length = 0;
    W.wave = Math.max(0, W.wave - 1);
    W.waveState = 'ready'; W.waveT = 3;
    say('부활했다. 웨이브를 다시 시작한다.', 2.5);
  }

  /* ---------- 경험치 / 레벨 -------------------------------- */
  function addXp(v){
    var p = W.player;
    if(p.level >= MAX_LEVEL) return;
    p.xp += v;
    while(p.level < MAX_LEVEL && p.xp >= xpNeed(p.level)){
      p.xp -= xpNeed(p.level);
      p.level++;
      var oldMax = p.max.hp;
      recalc(p);
      p.hp += (p.max.hp - oldMax);
      p.hp = p.max.hp; p.mp = p.max.mp;
      autoBind(p);
      fx({ type:'levelup', x: p.x, y: p.y, dur: 0.9 });
      say('레벨 ' + p.level + ' 달성!', 2);
      if(p.level >= JOB2_LEVEL && !p.job2 && W.onJob2) W.onJob2();
    }
  }

  function chooseJob2(id){
    var p = W.player;
    var J = JOB2_DB[id];
    if(!J || J.from !== p.cls) return false;
    p.job2 = id;
    recalc(p);
    p.hp = p.max.hp; p.mp = p.max.mp;
    /* 1차 스킬은 전부 사라지므로 슬롯을 비우고 2차 스킬로 다시 채운다 */
    p.slots = { 1:null, 2:null, 3:null, 4:null, R:null };
    p.cds = {};
    p.buffs.length = 0;
    autoBind(p);
    fx({ type:'levelup', x: p.x, y: p.y, dur: 1.4 });
    say(J.name + '(으)로 전직했다!', 3);
    return true;
  }

  /* ---------- 스킬 시전 ------------------------------------ */
  function baseStat(p, s){ return s.base === 'matk' ? stat(p, 'matk') : stat(p, 'atk'); }

  function skillReady(p, s){
    if(!s) return false;
    return (p.cds[s.id] || 0) <= 0 && p.mp >= (s.mp || 0);
  }

  function cast(id, ax, ay){
    var p = W.player, s = SKILL_BY_ID[id];
    if(!s || p.dead) return false;
    if((p.cds[s.id] || 0) > 0) return false;
    if(p.mp < (s.mp || 0)){ say('마나가 부족하다', 0.8); return false; }

    p.mp -= (s.mp || 0);
    p.cds[s.id] = s.cd;
    var ang = Math.atan2(ay - p.y, ax - p.x);
    p.aim = ang;
    var dmg = baseStat(p, s) * (s.coef || 0);
    var opt = {
      el: s.el, dot: s.dot, slow: s.slow, stun: s.stun, freeze: s.freeze,
      lifesteal: s.lifesteal, execute: s.execute, critBonus: s.critBonus, knock: s.knock
    };

    switch(s.type){
      case 'arc':      castArc(p, s, ang, dmg, opt); break;
      case 'proj':     castProj(p, s, ang, ax, ay, dmg, opt); break;
      case 'nova':     castNova(p, s, dmg, opt); break;
      case 'ground':   castGround(p, s, ax, ay, dmg, opt); break;
      case 'dash':     castDash(p, s, ang, ax, ay, dmg, opt); break;
      case 'beam':     castBeam(p, s, ang, dmg, opt); break;
      case 'chain':    castChain(p, s, ax, ay, dmg, opt); break;
      case 'buff':     castBuff(p, s); break;
      case 'heal':     healPlayer(dmg); fx({ type:'heal', x:p.x, y:p.y, follow:p, dur:0.6 });
                       artFx(s.fx, p.x, p.y, 190, 0.5); break;
      case 'aura':     castAura(p, s, dmg, opt); break;
    }
    p.anim = 'atk'; p.animT = 0; p.frame = 0;
    return true;
  }

  function castArc(p, s, ang, dmg, opt){
    var hits = s.hits || 1, i;
    for(i = 0; i < hits; i++){
      (function(n){
        var run = function(){
          arcHit(p, ang, s.range, s.arc, dmg, opt);
          fx({ type:'slash', x:p.x, y:p.y, ang:ang, range:s.range, arc:s.arc,
               col: EL_COLOR[s.el], dur: 0.2, follow: p });
          artFx(s.fx, p.x + Math.cos(ang)*s.range*0.55, p.y + Math.sin(ang)*s.range*0.55,
                s.range * 1.7, 0.34);
        };
        if(n === 0) run(); else timer(n * (s.hitRate || 0.08), run);
      })(i);
    }
  }

  function arcHit(p, ang, range, arc, dmg, opt){
    for(var i = 0; i < W.mobs.length; i++){
      var m = W.mobs[i];
      if(m.dead) continue;
      var d = Math.sqrt(dist2(p.x, p.y, m.x, m.y));
      if(d > range + m.r) continue;
      var a = Math.atan2(m.y - p.y, m.x - p.x);
      if(Math.abs(angDiff(a, ang)) > arc / 2) continue;
      hitMob(m, dmg, opt);
    }
  }

  function spawnShot(p, s, ang, dmg, opt, extra){
    var sp = s.speed || 300;
    var sh = {
      x: p.x, y: p.y - 2, vx: Math.cos(ang)*sp, vy: Math.sin(ang)*sp,
      r: s.radius ? Math.max(14, s.radius*0.28) : 14,
      life: (s.range || 320) / sp, dmg: dmg, opt: opt, el: s.el,
      pierce: s.pierce || 0, hitIds: [], radius: s.radius || 0,
      homing: !!s.homing, target: null, owner: 'p', size: s.radius ? 2 : 1, ang: ang,
      fx: s.fx
    };
    if(extra) for(var k in extra) sh[k] = extra[k];
    W.shots.push(sh);
  }

  function castProj(p, s, ang, ax, ay, dmg, opt){
    var n = s.count || 1, i;
    for(i = 0; i < n; i++){
      var off = (n === 1) ? 0 : (i - (n-1)/2) * (s.spread || 0.2);
      (function(a, k){
        var run = function(){ spawnShot(p, s, a, dmg, opt); };
        if(s.burst) timer(k * s.burst, run); else run();
      })(ang + off, i);
    }
  }

  function castNova(p, s, dmg, opt){
    fx({ type:'nova', x:p.x, y:p.y, radius:s.radius, col: EL_COLOR[s.el], dur: 0.42 });
    artFx(s.fx, p.x, p.y, s.radius * 1.9);
    for(var i = 0; i < W.mobs.length; i++){
      var m = W.mobs[i];
      if(m.dead) continue;
      if(dist2(p.x, p.y, m.x, m.y) <= (s.radius + m.r) * (s.radius + m.r)) hitMob(m, dmg, opt);
    }
    if(s.healSelf) healPlayer(baseStat(p, s) * s.healSelf);
    if(s.healOnHit){
      var cnt = 0;
      for(var j = 0; j < W.mobs.length; j++)
        if(!W.mobs[j].dead && dist2(p.x,p.y,W.mobs[j].x,W.mobs[j].y) <= s.radius*s.radius) cnt++;
      if(cnt) healPlayer(baseStat(p, s) * s.healOnHit * cnt);
    }
  }

  function castGround(p, s, ax, ay, dmg, opt){
    /* 시전 거리 제한 */
    var d = Math.sqrt(dist2(p.x, p.y, ax, ay)), max = s.castRange || 520;
    if(d > max){
      var a = Math.atan2(ay - p.y, ax - p.x);
      ax = p.x + Math.cos(a) * max; ay = p.y + Math.sin(a) * max;
    }
    if(s.ticks){
      W.zones.push({ x: ax, y: ay, r: s.radius, dmg: dmg, opt: opt, el: s.el, fx: s.fx,
                     left: s.ticks, rate: s.tickRate || 0.3, t: 0, kind: 'ground' });
      fx({ type:'zone', x: ax, y: ay, radius: s.radius, col: EL_COLOR[s.el],
           dur: s.ticks * (s.tickRate || 0.3) });
    }else{
      var delay = s.delay || 0;
      fx({ type:'mark', x: ax, y: ay, radius: s.radius, col: EL_COLOR[s.el], dur: Math.max(0.12, delay) });
      timer(delay, function(){
        fx({ type:'boom', x: ax, y: ay, radius: s.radius, col: EL_COLOR[s.el], dur: 0.4 });
        artFx(s.fx, ax, ay, s.radius * 2.1);
        for(var i = 0; i < W.mobs.length; i++){
          var m = W.mobs[i];
          if(m.dead) continue;
          if(dist2(ax, ay, m.x, m.y) <= (s.radius + m.r) * (s.radius + m.r)) hitMob(m, dmg, opt);
        }
      });
    }
  }

  function castDash(p, s, ang, ax, ay, dmg, opt){
    var d = s.dist;
    if(s.blink){
      var want = Math.min(d, Math.sqrt(dist2(p.x, p.y, ax, ay)));
      var nx = clamp(p.x + Math.cos(ang)*want, TILE*2, WORLD_W - TILE*2);
      var ny = clamp(p.y + Math.sin(ang)*want, TILE*2, WORLD_H - TILE*2);
      fx({ type:'blink', x:p.x, y:p.y, col: EL_COLOR[s.el], dur: 0.3 });
      if(dmg > 0) lineHit(p.x, p.y, nx, ny, s.width || 72, dmg, opt);
      if(s.dot || s.el === 'fire')
        fx({ type:'trail', x:p.x, y:p.y, x2:nx, y2:ny, col: EL_COLOR[s.el], dur: 0.5 });
      p.x = nx; p.y = ny;
      fx({ type:'blink', x:nx, y:ny, col: EL_COLOR[s.el], dur: 0.3 });
      if(dmg > 0) artFx(s.fx, nx, ny, (s.width || 72) * 2.4, 0.36);
      p.invuln = Math.max(p.invuln, s.invuln || 0);
    }else{
      p.dash = { ang: ang, left: d, speed: d / 0.22, hit: [], dmg: dmg, opt: opt,
                 width: s.width || 68, el: s.el, fx: s.fx };
      p.invuln = Math.max(p.invuln, s.invuln || 0.22);
    }
  }

  function lineHit(x0, y0, x1, y1, width, dmg, opt){
    var dx = x1-x0, dy = y1-y0, len = Math.sqrt(dx*dx+dy*dy) || 1;
    var ux = dx/len, uy = dy/len;
    for(var i = 0; i < W.mobs.length; i++){
      var m = W.mobs[i];
      if(m.dead) continue;
      var t = ((m.x-x0)*ux + (m.y-y0)*uy);
      if(t < -m.r || t > len + m.r) continue;
      var px = x0 + ux*clamp(t, 0, len), py = y0 + uy*clamp(t, 0, len);
      if(dist2(px, py, m.x, m.y) <= (width/2 + m.r)*(width/2 + m.r)) hitMob(m, dmg, opt);
    }
  }

  function castBeam(p, s, ang, dmg, opt){
    var x1 = p.x + Math.cos(ang)*s.length, y1 = p.y + Math.sin(ang)*s.length;
    fx({ type:'beam', x:p.x, y:p.y, x2:x1, y2:y1, col: EL_COLOR[s.el], width: s.width, dur: 0.28 });
    lineHit(p.x, p.y, x1, y1, s.width, dmg, opt);
    for(var q = 1; q <= 3; q++)
      artFx(s.fx, p.x + Math.cos(ang)*s.length*q/3.5, p.y + Math.sin(ang)*s.length*q/3.5,
            s.width * 3.4, 0.3);
  }

  function castChain(p, s, ax, ay, dmg, opt){
    var first = null, best = 1e12, i;
    for(i = 0; i < W.mobs.length; i++){
      var m = W.mobs[i];
      if(m.dead) continue;
      var d = dist2(ax, ay, m.x, m.y);
      if(d < best && dist2(p.x, p.y, m.x, m.y) < (s.castRange||300)*(s.castRange||300)){ best = d; first = m; }
    }
    if(!first){ say('대상이 없다', 0.7); return; }
    var cur = first, from = { x: p.x, y: p.y }, used = {}, cd = dmg;
    for(i = 0; i < (s.jumps || 4); i++){
      if(!cur) break;
      used[cur.uid] = true;
      fx({ type:'bolt', x: from.x, y: from.y, x2: cur.x, y2: cur.y, col: EL_COLOR[s.el], dur: 0.22 });
      artFx(s.fx, cur.x, cur.y, 130, 0.3);
      hitMob(cur, cd, opt);
      cd *= (s.falloff || 0.85);
      from = { x: cur.x, y: cur.y };
      var nx = null, nb = (s.jumpRange||130) * (s.jumpRange||130);
      for(var j = 0; j < W.mobs.length; j++){
        var t = W.mobs[j];
        if(t.dead || used[t.uid]) continue;
        var dd = dist2(from.x, from.y, t.x, t.y);
        if(dd < nb){ nb = dd; nx = t; }
      }
      cur = nx;
    }
  }

  function castBuff(p, s){
    var b = s.buff || {}, mod = {}, k;
    for(k in b) if(k !== 'shield') mod[k] = b[k];
    /* 같은 스킬 버프는 갱신 */
    for(var i = p.buffs.length - 1; i >= 0; i--) if(p.buffs[i].id === s.id) p.buffs.splice(i, 1);
    p.buffs.push({ id: s.id, name: s.name, icon: s.icon, t: s.dur, dur: s.dur, mod: mod, el: s.el });
    if(b.shield) p.shield = Math.max(p.shield, baseStat(p, s) * b.shield);
    fx({ type:'buff', x: p.x, y: p.y, col: EL_COLOR[s.el], follow: p, dur: 0.7 });
    artFx(s.fx, p.x, p.y, 190, 0.5);
  }

  function castAura(p, s, dmg, opt){
    W.zones.push({ follow: p, x: p.x, y: p.y, r: s.radius, dmg: dmg, opt: opt, el: s.el, fx: s.fx,
                   left: Math.ceil(s.dur / (s.tickRate || 0.3)), rate: s.tickRate || 0.3, t: 0,
                   kind: 'aura', moveMul: s.moveMul || 1, healTick: s.healTick || 0,
                   lifesteal: s.lifesteal || 0 });
  }

  /* ---------- 몬스터 --------------------------------------- */
  var uidSeq = 1;

  function spawnMob(def, x, y, boss){
    /* 난이도는 "플레이어 레벨"을 주축으로, 웨이브는 추가 압박으로만 쓴다.
       레벨만 올려서 무한정 쉬워지거나, 반대로 웨이브만 밀려 감당 못하는 걸 막는다. */
    var wv = W.wave, lv = W.player.level - 1;
    var hpMul  = (1 + lv * 0.130) * (1 + wv * 0.022);
    var atkMul = (1 + lv * 0.080) * (1 + wv * 0.022);
    var defMul = (1 + lv * 0.060) * (1 + wv * 0.015);
    var xpMul  = 1 + lv * 0.10 + wv * 0.06;
    var m = {
      uid: uidSeq++, def: def, name: def.name, art: def.art, h: def.h, ai: def.ai,
      x: x, y: y, vx: 0, vy: 0,
      maxhp: Math.round(def.hp * hpMul), hp: 0,
      atk: def.atk * atkMul, def: def.def * defMul,
      spd: def.spd, r: def.r,
      xp: def.xp * xpMul,
      atkCd: rnd(0.3, 1.2), proj: def.proj, boss: !!boss,
      dots: [], slow: null, stun: 0, freeze: 0, flash: 0,
      anim: 'walk', frame: 0, animT: rnd(0, 1), dir: 's', flip: false,
      kx: 0, ky: 0, aggro: 0, dead: false, chargeT: 0
    };
    m.hp = m.maxhp;
    W.mobs.push(m);
    return m;
  }

  function updateMob(m, dt){
    var p = W.player;
    /* 상태이상 */
    if(m.stun > 0) m.stun -= dt;
    if(m.freeze > 0) m.freeze -= dt;
    if(m.flash > 0) m.flash -= dt;
    if(m.hitPush > 0) m.hitPush = Math.max(0, m.hitPush - dt * 6);
    if(m.slow){ m.slow.t -= dt; if(m.slow.t <= 0) m.slow = null; }
    for(var i = m.dots.length - 1; i >= 0; i--){
      var d = m.dots[i];
      d.t -= dt; d.tick -= dt;
      if(d.tick <= 0){
        d.tick = 0.5;
        var out = Math.max(1, Math.round(d.dps * 0.5));
        m.hp -= out;
        dmgText(m.x + rnd(-6,6), m.y - m.r - 10, out, d.el === 'poison' ? 'poison' : 'burn');
        if(m.hp <= 0){ killMob(m); return; }
      }
      if(d.t <= 0) m.dots.splice(i, 1);
    }

    /* 넉백 */
    if(m.kx || m.ky){
      m.x += m.kx * dt; m.y += m.ky * dt;
      m.kx *= 0.86; m.ky *= 0.86;
      if(Math.abs(m.kx) < 4) m.kx = 0;
      if(Math.abs(m.ky) < 4) m.ky = 0;
    }

    if(m.stun > 0 || m.freeze > 0){ m.anim = 'idle'; return; }

    var dx = p.x - m.x, dy = p.y - m.y;
    var d = Math.sqrt(dx*dx + dy*dy) || 1;
    var spd = m.spd * (m.slow ? (1 - m.slow.amt) : 1);
    var wantRange = m.ai === 'ranged' ? (m.proj ? m.proj.range * 0.65 : 400) : (m.r + p.r + 8);
    var moving = false;

    if(m.ai === 'charger' && m.chargeT <= 0 && d < 520 && d > 140 && !p.dead){
      m.chargeT = 0.55;
      m.vx = dx/d * spd * 3.1; m.vy = dy/d * spd * 3.1;
    }

    if(m.chargeT > 0){
      m.chargeT -= dt;
      m.x += m.vx * dt; m.y += m.vy * dt;
      moving = true;
    }else if(!p.dead){
      if(m.ai === 'ranged'){
        if(d > wantRange + 60){ m.x += dx/d * spd * dt; m.y += dy/d * spd * dt; moving = true; }
        else if(d < wantRange - 80){ m.x -= dx/d * spd * 0.7 * dt; m.y -= dy/d * spd * 0.7 * dt; moving = true; }
      }else if(d > wantRange){
        m.x += dx/d * spd * dt; m.y += dy/d * spd * dt; moving = true;
      }
    }

    /* 공격 */
    m.atkCd -= dt;
    if(!p.dead && m.atkCd <= 0){
      if(m.ai === 'ranged' && m.proj){
        if(d < m.proj.range){
          m.atkCd = m.proj.cd;
          var a = Math.atan2(dy, dx);
          W.shots.push({ x: m.x, y: m.y - m.r*0.5, vx: Math.cos(a)*m.proj.speed, vy: Math.sin(a)*m.proj.speed,
                         r: 14, life: m.proj.range / m.proj.speed, dmg: m.atk, el: m.proj.el, owner: 'm', ang: a, size: 1 });
        }
      }else if(d <= wantRange + 20){
        m.atkCd = 1.25;
        hurtPlayer(m.atk, m);
        fx({ type:'hit', x: p.x, y: p.y - 12, col:'#ff8a8a', dur: 0.2 });
      }
    }

    /* 몬스터끼리 겹침 방지 */
    m.anim = moving ? 'walk' : 'idle';
    m.animT += dt * (moving ? 6 : 3);
    m.frame = Math.floor(m.animT) % 4;

    /* 방향 (스크린 기준) */
    setFacing(m, dx, dy);
    m.x = clamp(m.x, TILE*2, WORLD_W - TILE*2);
    m.y = clamp(m.y, TILE*2, WORLD_H - TILE*2);
  }

  /* 월드 방향 → 화면상의 8방향 스프라이트 선택 */
  function setFacing(e, dx, dy){
    var sx = dx - dy, sy = (dx + dy) * 0.5;
    if(Math.abs(sx) > Math.abs(sy) * 1.15){
      e.dir = 'e'; e.flip = sx < 0;
    }else{
      e.dir = sy > 0 ? 's' : 'n'; e.flip = sx < 0;
    }
  }

  function separate(){
    for(var i = 0; i < W.mobs.length; i++){
      var a = W.mobs[i];
      if(a.dead) continue;
      for(var j = i+1; j < W.mobs.length; j++){
        var b = W.mobs[j];
        if(b.dead) continue;
        var dx = b.x-a.x, dy = b.y-a.y, rr = a.r + b.r;
        var d2 = dx*dx + dy*dy;
        if(d2 > 0.01 && d2 < rr*rr){
          var d = Math.sqrt(d2), push = (rr - d) * 0.5;
          var ux = dx/d, uy = dy/d;
          var wa = a.boss ? 0.2 : 1, wb = b.boss ? 0.2 : 1;
          a.x -= ux*push*wa; a.y -= uy*push*wa;
          b.x += ux*push*wb; b.y += uy*push*wb;
        }
      }
    }
  }

  /* ---------- 웨이브 --------------------------------------- */
  function startWave(){
    W.wave++;
    var wv = W.wave;
    W.spawnQueue = [];
    var isBoss = (wv % 5 === 0);
    var pool = [];
    for(var i = 0; i < MONSTER_DB.length; i++) if(MONSTER_DB[i].minWave <= wv) pool.push(MONSTER_DB[i]);
    var count = Math.min(22, 4 + Math.floor(wv * 1.25));
    for(i = 0; i < count; i++) W.spawnQueue.push({ def: pool[(Math.random()*pool.length)|0], boss: false });
    if(isBoss){
      var b = BOSS_DB[Math.min(BOSS_DB.length-1, Math.floor((wv/5 - 1) % BOSS_DB.length))];
      W.spawnQueue.push({ def: b, boss: true });
    }
    W.spawnT = 0;
    W.waveState = 'fight';
    say('웨이브 ' + wv + (isBoss ? ' — 보스 출현!' : ' 시작'), 2.2);
  }

  function spawnPos(){
    var p = W.player, a = Math.random() * Math.PI * 2, d = rnd(560, 820);
    return {
      x: clamp(p.x + Math.cos(a)*d, TILE*2.5, WORLD_W - TILE*2.5),
      y: clamp(p.y + Math.sin(a)*d, TILE*2.5, WORLD_H - TILE*2.5)
    };
  }

  function updateWave(dt){
    if(W.waveState === 'ready'){
      W.waveT -= dt;
      if(W.waveT <= 0) startWave();
      return;
    }
    /* 스폰 */
    if(W.spawnQueue.length){
      W.spawnT -= dt;
      if(W.spawnT <= 0){
        W.spawnT = 0.35;
        var e = W.spawnQueue.shift(), pos = spawnPos();
        var m = spawnMob(e.def, pos.x, pos.y, e.boss);
        fx({ type:'spawn', x: pos.x, y: pos.y, col:'#8a5ac0', dur: 0.4 });
        if(e.boss) W.boss = m;
      }
    }else{
      var alive = 0;
      for(var i = 0; i < W.mobs.length; i++) if(!W.mobs[i].dead) alive++;
      if(alive === 0){
        W.waveState = 'ready';
        W.waveT = 4;
        W.boss = null;
        say('웨이브 ' + W.wave + ' 클리어! 잠시 후 다음 웨이브', 3);
        addXp(Math.round(25 * W.wave * (1 + W.player.level * 0.06)));
        healPlayer(W.player.max.hp * 0.25);
        W.player.mp = Math.min(W.player.max.mp, W.player.mp + W.player.max.mp * 0.3);
      }
    }
  }

  /* ---------- 플레이어 갱신 -------------------------------- */
  function updatePlayer(dt, aim, wantAttack, wantSkills){
    var p = W.player;
    if(p.invuln > 0) p.invuln -= dt;
    if(p.hitFlash > 0) p.hitFlash -= dt;
    if(p.atkCd > 0) p.atkCd -= dt;
    for(var k in p.cds) if(p.cds[k] > 0) p.cds[k] -= dt;

    /* 버프 만료 / 지속효과 */
    var m = mods(p);
    if(m.regen) healPlayer(p.max.hp * m.regen * dt);
    if(m.mpregen) p.mp = Math.min(p.max.mp, p.mp + p.max.mp * m.mpregen * dt);
    for(var i = p.buffs.length - 1; i >= 0; i--){
      p.buffs[i].t -= dt;
      if(p.buffs[i].t <= 0) p.buffs.splice(i, 1);
    }
    /* 기본 회복 */
    p.mp = Math.min(p.max.mp, p.mp + p.max.mp * 0.022 * dt);
    p.hp = Math.min(p.max.hp, p.hp + p.max.hp * 0.006 * dt);

    if(p.dead) return;

    p.aim = Math.atan2(aim.y - p.y, aim.x - p.x);

    /* 돌진 중 이동 */
    if(p.dash){
      var step = Math.min(p.dash.left, p.dash.speed * dt);
      var nx = clamp(p.x + Math.cos(p.dash.ang)*step, TILE*2, WORLD_W - TILE*2);
      var ny = clamp(p.y + Math.sin(p.dash.ang)*step, TILE*2, WORLD_H - TILE*2);
      if(p.dash.dmg > 0){
        lineHit(p.x, p.y, nx, ny, p.dash.width, p.dash.dmg, p.dash.opt);
        if(Math.random() < 0.5) artFx(p.dash.fx, nx, ny, p.dash.width * 2.6, 0.3);
      }
      fx({ type:'trail', x:p.x, y:p.y, x2:nx, y2:ny, col: EL_COLOR[p.dash.el] || '#fff', dur: 0.3 });
      p.x = nx; p.y = ny;
      p.dash.left -= step;
      if(p.dash.left <= 0.5) p.dash = null;
      p.anim = 'walk';
      return;
    }

    /* 이동 — 화면 기준 WASD를 월드 좌표로 변환 (쿼터뷰) */
    var mv = Input.moveVector();
    var wx = 0, wy = 0;
    if(mv.x || mv.y){
      /* 화면 오른쪽 = 월드 (+1,-1), 화면 아래 = 월드 (+1,+1) */
      wx = mv.x + mv.y;
      wy = mv.y - mv.x;
      var len = Math.sqrt(wx*wx + wy*wy) || 1;
      wx /= len; wy /= len;
    }
    var spd = stat(p, 'spd');
    /* 장판 스킬 시전 중 이동 감속 */
    for(i = 0; i < W.zones.length; i++)
      if(W.zones[i].follow === p && W.zones[i].moveMul) spd *= W.zones[i].moveMul;

    p.x = clamp(p.x + wx * spd * dt, TILE*2, WORLD_W - TILE*2);
    p.y = clamp(p.y + wy * spd * dt, TILE*2, WORLD_H - TILE*2);

    var moving = !!(wx || wy);
    if(p.anim === 'atk'){
      p.animT += dt;
      p.frame = p.animT < 0.09 ? 0 : 1;
      if(p.animT > 0.24) p.anim = moving ? 'walk' : 'idle';
    }else{
      p.anim = moving ? 'walk' : 'idle';
      p.animT += dt * (moving ? 7 : 3);
      p.frame = Math.floor(p.animT) % 4;
    }
    setFacing(p, Math.cos(p.aim), Math.sin(p.aim));

    /* 기본 공격 */
    if(wantAttack && p.atkCd <= 0) basicAttack(aim);

    /* 스킬 */
    for(i = 0; i < wantSkills.length; i++){
      var id = p.slots[wantSkills[i]];
      if(id) cast(id, aim.x, aim.y);
    }
  }

  function basicAttack(aim){
    var p = W.player, w = WEAPON_DB[weaponOf(p)];
    var aspd = 1 + mods(p).aspd;
    p.atkCd = w.cd / aspd;
    p.anim = 'atk'; p.animT = 0; p.frame = 0;
    var ang = Math.atan2(aim.y - p.y, aim.x - p.x);
    p.aim = ang;
    var dmg = (w.base === 'matk' ? stat(p, 'matk') : stat(p, 'atk')) * w.coef;
    var opt = { el: w.el };
    if(w.atk === 'arc'){
      arcHit(p, ang, w.range, w.arc, dmg, opt);
      fx({ type:'slash', x:p.x, y:p.y, ang:ang, range:w.range, arc:w.arc, col: EL_COLOR[w.el], dur:0.16, follow:p });
      artFx(WEAPON_FX[weaponOf(p)], p.x + Math.cos(ang)*w.range*0.6, p.y + Math.sin(ang)*w.range*0.6,
            w.range * 1.7, 0.26);
    }else{
      spawnShot(p, { speed: w.speed, range: w.range, el: w.el }, ang, dmg, opt, { basic: true });
    }
  }

  /* ---------- 투사체 / 장판 / 이펙트 ----------------------- */
  function updateShots(dt){
    var p = W.player;
    for(var i = W.shots.length - 1; i >= 0; i--){
      var s = W.shots[i];
      if(s.homing && s.owner === 'p'){
        if(!s.target || s.target.dead){
          var best = 1e12, t = null;
          for(var j = 0; j < W.mobs.length; j++){
            var mm = W.mobs[j];
            if(mm.dead) continue;
            var d = dist2(s.x, s.y, mm.x, mm.y);
            if(d < best){ best = d; t = mm; }
          }
          s.target = t;
        }
        if(s.target){
          var want = Math.atan2(s.target.y - s.y, s.target.x - s.x);
          var cur = Math.atan2(s.vy, s.vx);
          var sp = Math.sqrt(s.vx*s.vx + s.vy*s.vy);
          var na = cur + clamp(angDiff(want, cur), -4*dt, 4*dt);
          s.vx = Math.cos(na)*sp; s.vy = Math.sin(na)*sp; s.ang = na;
        }
      }
      s.x += s.vx * dt; s.y += s.vy * dt;
      s.life -= dt;
      var gone = s.life <= 0 || s.x < TILE || s.y < TILE || s.x > WORLD_W-TILE || s.y > WORLD_H-TILE;

      if(s.owner === 'p'){
        for(var k = 0; k < W.mobs.length; k++){
          var m = W.mobs[k];
          if(m.dead || s.hitIds.indexOf(m.uid) >= 0) continue;
          if(dist2(s.x, s.y, m.x, m.y) <= (s.r + m.r)*(s.r + m.r)){
            s.hitIds.push(m.uid);
            if(s.radius){    /* 폭발형 */
              fx({ type:'boom', x:s.x, y:s.y, radius:s.radius, col: EL_COLOR[s.el], dur:0.35 });
              artFx(s.fx || EL_FX[s.el], s.x, s.y, s.radius * 2.1);
              for(var q = 0; q < W.mobs.length; q++){
                var m2 = W.mobs[q];
                if(m2.dead) continue;
                if(dist2(s.x, s.y, m2.x, m2.y) <= (s.radius + m2.r)*(s.radius + m2.r)) hitMob(m2, s.dmg, s.opt);
              }
              if(!s.pierce) gone = true;
            }else{
              hitMob(m, s.dmg, s.opt);
              artFx(s.fx || EL_FX[s.el], s.x, s.y, 110, 0.3);
              if(s.pierce > 0) s.pierce--; else gone = true;
            }
            break;
          }
        }
      }else{
        if(!p.dead && dist2(s.x, s.y, p.x, p.y) <= (s.r + p.r)*(s.r + p.r)){
          hurtPlayer(s.dmg, null);
          gone = true;
        }
      }
      if(gone) W.shots.splice(i, 1);
    }
  }

  function updateZones(dt){
    var p = W.player;
    for(var i = W.zones.length - 1; i >= 0; i--){
      var z = W.zones[i];
      if(z.follow){ z.x = z.follow.x; z.y = z.follow.y; }
      z.t -= dt;
      if(z.t <= 0){
        z.t = z.rate; z.left--;
        for(var j = 0; j < W.mobs.length; j++){
          var m = W.mobs[j];
          if(m.dead) continue;
          if(dist2(z.x, z.y, m.x, m.y) <= (z.r + m.r)*(z.r + m.r)){
            var out = hitMob(m, z.dmg, z.opt);
            if(z.lifesteal) healPlayer(out * z.lifesteal);
          }
        }
        if(z.healTick) healPlayer(p.max.hp * z.healTick);
        fx({ type:'zonetick', x: z.x, y: z.y, radius: z.r, col: EL_COLOR[z.el], dur: z.rate });
        var za = Math.random() * 6.2832, zd = Math.sqrt(Math.random()) * z.r * 0.7;
        artFx(z.fx, z.x + Math.cos(za)*zd, z.y + Math.sin(za)*zd, z.r * 1.15, 0.36);
      }
      if(z.left <= 0) W.zones.splice(i, 1);
    }
  }

  function updateOrbs(dt){
    var p = W.player;
    for(var i = W.orbs.length - 1; i >= 0; i--){
      var o = W.orbs[i];
      o.t += dt;
      var d = Math.sqrt(dist2(o.x, o.y, p.x, p.y));
      if(d < 240){
        var a = Math.atan2(p.y - o.y, p.x - o.x);
        var sp = 120 + (240 - d) * 2.4;
        o.x += Math.cos(a)*sp*dt; o.y += Math.sin(a)*sp*dt;
      }
      if(d < 36){
        if(o.kind === 'hp') healPlayer(p.max.hp * 0.12);
        else { p.mp = Math.min(p.max.mp, p.mp + p.max.mp * 0.18); dmgText(p.x, p.y - 30, '+MP', 'mp'); }
        W.orbs.splice(i, 1);
        continue;
      }
      if(o.t > 25) W.orbs.splice(i, 1);
    }
  }

  function updateFx(dt){
    var i;
    for(i = W.fx.length - 1; i >= 0; i--){
      var f = W.fx[i];
      f.t += dt;
      if(f.follow){ f.x = f.follow.x; f.y = f.follow.y; }
      if(f.t >= f.dur) W.fx.splice(i, 1);
    }
    for(i = W.texts.length - 1; i >= 0; i--){
      var t = W.texts[i];
      t.t += dt;
      t.x += t.vx * dt; t.y += t.vy * dt;
      t.vy += 40 * dt;
      if(t.t >= t.dur) W.texts.splice(i, 1);
    }
    for(i = W.corpses.length - 1; i >= 0; i--){
      W.corpses[i].t += dt;
      if(W.corpses[i].t >= W.corpses[i].dur) W.corpses.splice(i, 1);
    }
    for(i = W.timers.length - 1; i >= 0; i--){
      W.timers[i].t -= dt;
      if(W.timers[i].t <= 0){ var fn = W.timers[i].fn; W.timers.splice(i, 1); fn(); }
    }
    if(W.msgT > 0){ W.msgT -= dt; if(W.msgT <= 0) W.msg = null; }
  }

  /* ---------- 메인 업데이트 -------------------------------- */
  function update(dt, aim, wantAttack, wantSkills){
    W.time += dt;
    updatePlayer(dt, aim, wantAttack, wantSkills);
    for(var i = 0; i < W.mobs.length; i++) if(!W.mobs[i].dead) updateMob(W.mobs[i], dt);
    separate();
    updateShots(dt);
    updateZones(dt);
    updateOrbs(dt);
    updateFx(dt);
    updateWave(dt);
    /* 죽은 몬스터 정리 */
    for(i = W.mobs.length - 1; i >= 0; i--) if(W.mobs[i].dead) W.mobs.splice(i, 1);
  }

  return {
    init: init, update: update, loadPlayer: loadPlayer,
    get state(){ return W; },
    TILE: TILE,
    cast: cast, bindSkill: bindSkill, chooseJob2: chooseJob2, revive: revive,
    learned: learned, recalc: recalc, stat: stat, mods: mods, skillReady: skillReady,
    jobOf: jobOf, weaponOf: weaponOf, lookOf: lookOf, artOf: artOf, jobName: jobName,
    addXp: addXp, say: say
  };
})();
