/* ============================================================
   데이터 정의 — 무기 / 직업 / 2차 전직 / 스킬 / 몬스터 / 성장
   순수 데이터만 둔다. 실제 동작은 engine.js 가 해석한다.
   ============================================================ */

/* 속성별 이펙트 색 */
var EL_COLOR = {
  phys:'#efe7cf', fire:'#ff7b2a', ice:'#7fd8ff', lightning:'#ffe45c',
  holy:'#ffeaa8', poison:'#8ce35b', magic:'#c79bff', dark:'#a06bd8'
};

/* 무기별 기본공격(좌클릭) 정의
   atk: arc = 근접 부채꼴, proj = 투사체 */
var WEAPON_DB = {
  sword:      {name:'한손검', atk:'arc',  cd:0.42, coef:1.00, range:46, arc:1.5, base:'atk',  el:'phys'},
  greatsword: {name:'양손검', atk:'arc',  cd:0.68, coef:1.85, range:62, arc:2.0, base:'atk',  el:'phys'},
  longsword:  {name:'장검',   atk:'arc',  cd:0.48, coef:1.18, range:52, arc:1.4, base:'atk',  el:'magic'},
  staff:      {name:'스태프', atk:'proj', cd:0.54, coef:1.15, range:330, speed:270, base:'matk', el:'magic'},
  bow:        {name:'활',     atk:'proj', cd:0.44, coef:1.08, range:420, speed:430, base:'atk',  el:'phys'},
  dagger:     {name:'단검',   atk:'arc',  cd:0.26, coef:0.64, range:40, arc:1.2, base:'atk',  el:'poison'},
  mace:       {name:'메이스', atk:'arc',  cd:0.56, coef:1.55, range:48, arc:1.5, base:'atk',  el:'holy'},
  fist:       {name:'권법',   atk:'arc',  cd:0.23, coef:0.56, range:36, arc:1.3, base:'atk',  el:'phys'}
};

/* 1차 직업.
   base  : 1레벨 기준치
   grow  : 레벨당 상승치
   art   : assets/hero 스프라이트 (h = 화면상 높이, tint = 색조 변경)
   look  : 에셋이 없을 때 쓰는 도형 스프라이트 팔레트 */
var CLASS_DB = {
  knight: {
    name:'기사', weapon:'sword', desc:'한손검과 방패로 전선을 지탱하는 근접 직업. 체력과 방어가 높다.',
    base:{hp:220, mp:60,  atk:16, matk:4,  def:12, crit:5,  spd:100},
    grow:{hp:26,  mp:3,   atk:2.4, matk:0.3, def:1.5, crit:0.10},
    art:{sprite:'knight', h:104},
    look:{skin:'#f0c49b', hair:'#4b3a2a', main:'#5f7fa8', sub:'#c9d6e6', trim:'#e0c063', cape:'#9c3b3b'}
  },
  mage: {
    name:'마법사', weapon:'staff', desc:'스태프로 원거리 마법을 퍼붓는 직업. 화력은 최상이나 몸이 약하다.',
    base:{hp:140, mp:150, atk:6,  matk:20, def:6,  crit:5,  spd:96},
    grow:{hp:13,  mp:11,  atk:0.5, matk:3.1, def:0.7, crit:0.12},
    art:{sprite:'mage', h:100},
    look:{skin:'#f2cba6', hair:'#d8d2c0', main:'#5b4a9c', sub:'#8f7fd8', trim:'#ffd76a', cape:'#3b2f6b'}
  },
  archer: {
    name:'궁수', weapon:'bow', desc:'활로 거리를 유지하며 싸우는 직업. 이동이 빠르고 치명타가 높다.',
    base:{hp:165, mp:90,  atk:15, matk:6,  def:8,  crit:12, spd:114},
    grow:{hp:17,  mp:5,   atk:2.5, matk:0.5, def:0.9, crit:0.22},
    art:{sprite:'archer', h:104},
    look:{skin:'#eec49a', hair:'#8a5a2b', main:'#3f7a4a', sub:'#7ab06a', trim:'#c9a86a', cape:'#2f5a38'}
  },
  priest: {
    name:'사제', weapon:'mace', desc:'신성력으로 자신을 치유하며 버티는 직업. 균형이 잡혀 있다.',
    base:{hp:185, mp:120, atk:13, matk:15, def:10, crit:5,  spd:100},
    grow:{hp:20,  mp:8,   atk:2.0, matk:2.2, def:1.2, crit:0.12},
    art:{sprite:'priest', h:102},
    look:{skin:'#f3cda9', hair:'#e8dfae', main:'#e8e2d2', sub:'#d8cfae', trim:'#e5c04e', cape:'#c8b06a'}
  }
};

/* 2차 전직 (40레벨).
   add   : 전직 즉시 더해지는 보너스
   grow  : 전직 이후 레벨당 상승치(1차 성장치를 대체한다) */
var JOB2_DB = {
  /* ── 기사 ── */
  greatsword: {
    name:'대검전사', from:'knight', weapon:'greatsword',
    desc:'양손검으로 한 번에 크게 후려친다. 공격 범위와 한 방이 압도적이다.',
    add:{hp:220, atk:30, def:6}, grow:{hp:34, mp:3, atk:4.2, matk:0.3, def:1.6, crit:0.14},
    art:{sprite:'warrior', h:112},
    look:{skin:'#f0c49b', hair:'#3a2d20', main:'#7a4a3a', sub:'#c07a4a', trim:'#e0c063', cape:'#5a2222'}
  },
  magicknight: {
    name:'마검사', from:'knight', weapon:'longsword',
    desc:'장검에 마력을 실어 벤다. 물리와 마법을 함께 쓰는 근접 직업.',
    add:{hp:140, mp:90, atk:16, matk:22}, grow:{hp:24, mp:8, atk:2.6, matk:2.4, def:1.3, crit:0.16},
    art:{sprite:'knight', h:106, tint:'#7a5ad8', tintAmt:0.45},
    look:{skin:'#f0c49b', hair:'#6a5aa8', main:'#3a3a6a', sub:'#7f7fd0', trim:'#a8e0ff', cape:'#2a2a52'}
  },
  /* ── 마법사 ── */
  firemage: {
    name:'화염법사', from:'mage', weapon:'staff',
    desc:'광역 폭발과 화상으로 지속 피해를 누적시킨다.',
    add:{mp:120, matk:40}, grow:{hp:14, mp:12, atk:0.5, matk:4.3, def:0.8, crit:0.14},
    art:{sprite:'mage', h:102, tint:'#ff5a1a', tintAmt:0.42},
    look:{skin:'#f2cba6', hair:'#e06a2a', main:'#8a2f2f', sub:'#e0602a', trim:'#ffc04a', cape:'#5a1a1a'}
  },
  icemage: {
    name:'냉기법사', from:'mage', weapon:'staff',
    desc:'둔화와 빙결로 적을 묶는다. 생존력이 가장 높은 마법사.',
    add:{hp:90, mp:110, matk:32, def:6}, grow:{hp:18, mp:11, atk:0.5, matk:3.8, def:1.2, crit:0.14},
    art:{sprite:'ice_mage', h:112},
    look:{skin:'#f2cba6', hair:'#bfe8ff', main:'#2f5a8a', sub:'#7fd8ff', trim:'#e8f8ff', cape:'#1e3a5a'}
  },
  boltmage: {
    name:'전격법사', from:'mage', weapon:'staff',
    desc:'연쇄 번개로 무리를 한 번에 쓸어담는다. 시전이 가장 빠르다.',
    add:{mp:110, matk:34, crit:8}, grow:{hp:14, mp:11, atk:0.5, matk:4.0, def:0.8, crit:0.30},
    art:{sprite:'mage', h:102, tint:'#ffd23a', tintAmt:0.42},
    look:{skin:'#f2cba6', hair:'#ffe45c', main:'#4a3a8a', sub:'#ffe45c', trim:'#fff7c0', cape:'#2a2050'}
  },
  /* ── 궁수 ── */
  ranger: {
    name:'신궁', from:'archer', weapon:'bow',
    desc:'관통과 폭우로 화면 끝에서 적을 정리한다. 사거리가 가장 길다.',
    add:{atk:34, crit:10}, grow:{hp:19, mp:5, atk:4.0, matk:0.5, def:1.0, crit:0.30},
    art:{sprite:'archer', h:106, tint:'#ffd76a', tintAmt:0.42},
    look:{skin:'#eec49a', hair:'#e8d8a0', main:'#2f6a5a', sub:'#7ac0a0', trim:'#ffe08a', cape:'#1e4a3a'}
  },
  venom: {
    name:'베놈', from:'archer', weapon:'dagger',
    desc:'단검을 들고 파고들어 맹독을 쌓는다. 공격 속도가 가장 빠르다.',
    add:{hp:110, atk:28, crit:14, spd:8}, grow:{hp:23, mp:6, atk:3.6, matk:0.6, def:1.1, crit:0.34},
    art:{sprite:'assassin', h:106},
    look:{skin:'#e8bf95', hair:'#3a2a3a', main:'#3a2f4a', sub:'#6ac05a', trim:'#8ce35b', cape:'#241d30'}
  },
  /* ── 사제 ── */
  crusader: {
    name:'크루세이더', from:'priest', weapon:'mace',
    desc:'메이스를 휘두르며 때릴수록 회복한다. 사제 계열 최전방.',
    add:{hp:230, atk:26, def:10}, grow:{hp:32, mp:6, atk:3.4, matk:1.6, def:1.9, crit:0.16},
    art:{sprite:'lancer', h:114},
    look:{skin:'#f3cda9', hair:'#d8c890', main:'#d0d4dc', sub:'#e8e2d2', trim:'#e5c04e', cape:'#b03a3a'}
  },
  cleric: {
    name:'클레릭', from:'priest', weapon:'staff',
    desc:'스태프로 성역을 펼친다. 회복량과 광역 신성 피해가 뛰어나다.',
    add:{hp:110, mp:150, matk:32}, grow:{hp:21, mp:12, atk:1.2, matk:3.6, def:1.3, crit:0.14},
    art:{sprite:'priest', h:104, tint:'#7fd8ff', tintAmt:0.4},
    look:{skin:'#f3cda9', hair:'#f2ecc8', main:'#f4f0e2', sub:'#ffe9a8', trim:'#e5c04e', cape:'#e0d08a'}
  },
  monk: {
    name:'수도승', from:'priest', weapon:'fist',
    desc:'맨손 연타로 몰아친다. 타격 횟수가 많아 흡혈과 궁합이 좋다.',
    add:{hp:180, mp:80, atk:24, spd:12}, grow:{hp:28, mp:7, atk:3.2, matk:1.4, def:1.5, crit:0.26},
    art:{sprite:'summoner', h:106, tint:'#ff9a3a', tintAmt:0.35},
    look:{skin:'#eec49a', hair:'#2a2018', main:'#c86a3a', sub:'#e8a068', trim:'#f0e0c0', cape:'#8a3a20'}
  }
};

/* 2차 전직 선택지 (1차 직업 → 후보 목록) */
var JOB2_CHOICES = {
  knight:['greatsword','magicknight'],
  mage:['firemage','icemage','boltmage'],
  archer:['ranger','venom'],
  priest:['crusader','cleric','monk']
};

var JOB2_LEVEL = 40;   /* 2차 전직 레벨 */

/* ============================================================
   스킬 DB
   type — arc(부채꼴) proj(투사체) nova(자기중심 원) ground(커서 지점)
          dash(돌진) beam(관통 직선) chain(연쇄) buff(자기강화)
          heal(즉시회복) aura(따라다니는 장판)
   coef — base 스탯 대비 계수. base: 'atk' | 'matk'
   ============================================================ */
var SKILL_DB = [
/* ── 기사 1차 ───────────────────────────────────────────── */
{id:'kn_smash', job:'knight', name:'강타', lv:1, mp:8, cd:3, type:'arc', coef:2.2, base:'atk', el:'phys',
 range:62, arc:1.6, icon:'💥', desc:'전방을 크게 내려친다.'},
{id:'kn_charge', job:'knight', name:'방패 돌진', lv:5, mp:14, cd:7, type:'dash', coef:1.8, base:'atk', el:'phys',
 dist:170, width:34, stun:0.8, icon:'🛡️', desc:'앞으로 돌진하며 경로의 적을 밀치고 기절시킨다.'},
{id:'kn_whirl', job:'knight', name:'회전 베기', lv:12, mp:18, cd:6, type:'nova', coef:1.9, base:'atk', el:'phys',
 radius:78, icon:'🌀', desc:'몸을 회전시켜 주변 전체를 벤다.'},
{id:'kn_shout', job:'knight', name:'수호의 함성', lv:20, mp:26, cd:20, type:'buff', base:'atk', el:'holy',
 dur:10, buff:{def:0.5, atk:0.2}, icon:'📢', desc:'10초간 방어력 50%, 공격력 20% 증가.'},
{id:'kn_quake', job:'knight', name:'대지 가르기', lv:30, mp:34, cd:11, type:'ground', coef:3.0, base:'atk', el:'phys',
 radius:92, castRange:210, delay:0.35, icon:'⛰️', desc:'지정 지점을 갈라 광역 피해를 준다.'},

/* ── 마법사 1차 ─────────────────────────────────────────── */
{id:'mg_missile', job:'mage', name:'매직 미사일', lv:1, mp:7, cd:1.6, type:'proj', coef:1.7, base:'matk', el:'magic',
 count:3, spread:0.22, speed:330, range:360, icon:'✨', desc:'마력탄 3발을 부채꼴로 발사한다.'},
{id:'mg_fireball', job:'mage', name:'파이어볼', lv:5, mp:16, cd:4, type:'proj', coef:2.4, base:'matk', el:'fire',
 speed:260, range:380, radius:62, dot:{el:'fire', dps:0.35, dur:4}, icon:'🔥', desc:'착탄 시 폭발하고 화상을 남긴다.'},
{id:'mg_nova', job:'mage', name:'프로스트 노바', lv:12, mp:20, cd:8, type:'nova', coef:1.6, base:'matk', el:'ice',
 radius:96, slow:{amt:0.55, dur:3}, icon:'❄️', desc:'주변을 얼려 3초간 55% 둔화시킨다.'},
{id:'mg_blink', job:'mage', name:'텔레포트', lv:18, mp:14, cd:6, type:'dash', coef:0, base:'matk', el:'magic',
 dist:240, blink:true, invuln:0.35, icon:'🌀', desc:'커서 방향으로 순간이동한다.'},
{id:'mg_orb', job:'mage', name:'아케인 오브', lv:30, mp:38, cd:10, type:'proj', coef:3.4, base:'matk', el:'magic',
 speed:150, range:420, pierce:99, radius:46, icon:'🔮', desc:'느리게 나아가며 관통하는 거대한 마력구.'},

/* ── 궁수 1차 ───────────────────────────────────────────── */
{id:'ar_power', job:'archer', name:'파워샷', lv:1, mp:8, cd:2.4, type:'beam', coef:2.6, base:'atk', el:'phys',
 length:340, width:26, icon:'🏹', desc:'직선상의 적을 모두 관통하는 강화 사격.'},
{id:'ar_multi', job:'archer', name:'다중 사격', lv:5, mp:14, cd:4.5, type:'proj', coef:1.35, base:'atk', el:'phys',
 count:5, spread:0.34, speed:420, range:380, icon:'🎯', desc:'화살 5발을 넓게 퍼뜨린다.'},
{id:'ar_roll', job:'archer', name:'회피 구르기', lv:12, mp:10, cd:5, type:'dash', coef:0, base:'atk', el:'phys',
 dist:190, invuln:0.45, icon:'💨', desc:'구르며 회피한다. 구르는 동안 무적.'},
{id:'ar_poison', job:'archer', name:'독화살', lv:18, mp:16, cd:6, type:'proj', coef:1.8, base:'atk', el:'poison',
 speed:400, range:400, pierce:2, dot:{el:'poison', dps:0.5, dur:6}, icon:'🧪', desc:'맞은 적에게 6초 맹독을 건다.'},
{id:'ar_rain', job:'archer', name:'화살비', lv:30, mp:34, cd:12, type:'ground', coef:0.55, base:'atk', el:'phys',
 radius:110, castRange:300, ticks:10, tickRate:0.25, icon:'🌧️', desc:'지정 지역에 화살을 10회 퍼붓는다.'},

/* ── 사제 1차 ───────────────────────────────────────────── */
{id:'pr_strike', job:'priest', name:'성스러운 일격', lv:1, mp:8, cd:2.6, type:'arc', coef:2.0, base:'matk', el:'holy',
 range:58, arc:1.7, lifesteal:0.25, icon:'✝️', desc:'신성 피해를 주고 피해량의 25%를 회복한다.'},
{id:'pr_heal', job:'priest', name:'치유', lv:5, mp:24, cd:8, type:'heal', coef:2.2, base:'matk', el:'holy',
 icon:'💚', desc:'즉시 체력을 회복한다.'},
{id:'pr_wave', job:'priest', name:'신성한 파동', lv:12, mp:22, cd:7, type:'nova', coef:1.7, base:'matk', el:'holy',
 radius:100, healOnHit:0.18, icon:'🔆', desc:'주변에 신성 파동을 터뜨리고 맞힌 수만큼 회복한다.'},
{id:'pr_bless', job:'priest', name:'축복', lv:20, mp:28, cd:22, type:'buff', base:'matk', el:'holy',
 dur:12, buff:{atk:0.3, matk:0.3, regen:0.02}, icon:'🙏', desc:'12초간 공격력·마력 30% 증가, 초당 체력 2% 회복.'},
{id:'pr_judge', job:'priest', name:'심판의 빛', lv:30, mp:36, cd:11, type:'ground', coef:3.2, base:'matk', el:'holy',
 radius:86, castRange:230, delay:0.4, icon:'🌟', desc:'지정 지점에 빛기둥을 내린다.'},

/* ── 대검전사 ───────────────────────────────────────────── */
{id:'gs_cleave', job:'greatsword', name:'광폭 베기', lv:40, mp:18, cd:3.5, type:'arc', coef:3.4, base:'atk', el:'phys',
 range:86, arc:2.2, icon:'⚔️', desc:'전방을 넓게 후려친다.'},
{id:'gs_shock', job:'greatsword', name:'대지 강타', lv:42, mp:26, cd:7, type:'nova', coef:3.0, base:'atk', el:'phys',
 radius:110, stun:0.7, icon:'💢', desc:'땅을 내리쳐 주변을 기절시킨다.'},
{id:'gs_spin', job:'greatsword', name:'회오리 참', lv:46, mp:32, cd:9, type:'aura', coef:1.1, base:'atk', el:'phys',
 radius:92, dur:3, tickRate:0.3, moveMul:0.6, icon:'🌪️', desc:'3초간 회전하며 주변을 계속 벤다.'},
{id:'gs_rage', job:'greatsword', name:'광전사의 분노', lv:50, mp:30, cd:24, type:'buff', base:'atk', el:'fire',
 dur:12, buff:{atk:0.55, spd:0.2, lifesteal:0.15}, icon:'🩸', desc:'12초간 공격력 55%, 이동속도 20% 증가, 흡혈 15%.'},
{id:'gs_exec', job:'greatsword', name:'참수', lv:55, mp:34, cd:12, type:'arc', coef:5.0, base:'atk', el:'phys',
 range:74, arc:1.2, execute:0.35, icon:'🪓', desc:'체력 35% 이하의 적에게 피해가 2배로 들어간다.'},

/* ── 마검사 ─────────────────────────────────────────────── */
{id:'mk_wave', job:'magicknight', name:'마력 검기', lv:40, mp:14, cd:2.6, type:'proj', coef:2.2, base:'matk', el:'magic',
 speed:380, range:300, pierce:3, icon:'🗡️', desc:'검기를 날려 관통시킨다.'},
{id:'mk_burst', job:'magicknight', name:'검기 폭발', lv:42, mp:24, cd:7, type:'nova', coef:2.6, base:'matk', el:'magic',
 radius:96, icon:'💠', desc:'주변에 응축한 마력을 터뜨린다.'},
{id:'mk_step', job:'magicknight', name:'순보', lv:46, mp:18, cd:5, type:'dash', coef:2.4, base:'atk', el:'magic',
 dist:210, width:40, blink:true, invuln:0.3, icon:'⚡', desc:'적을 꿰뚫으며 순간이동한다.'},
{id:'mk_awake', job:'magicknight', name:'마검 각성', lv:50, mp:32, cd:22, type:'buff', base:'matk', el:'magic',
 dur:12, buff:{atk:0.3, matk:0.4, aspd:0.25}, icon:'🌌', desc:'12초간 공격력·마력·공격속도가 크게 오른다.'},
{id:'mk_rune', job:'magicknight', name:'룬 참격', lv:55, mp:36, cd:11, type:'ground', coef:4.0, base:'matk', el:'magic',
 radius:96, castRange:240, delay:0.3, icon:'🔷', desc:'지정 지점에 룬을 새겨 폭발시킨다.'},

/* ── 화염법사 ───────────────────────────────────────────── */
{id:'fm_blast', job:'firemage', name:'화염 폭발', lv:40, mp:18, cd:3, type:'ground', coef:2.6, base:'matk', el:'fire',
 radius:80, castRange:300, dot:{el:'fire', dps:0.3, dur:4}, icon:'💥', desc:'지정 지점을 폭파하고 화상을 남긴다.'},
{id:'fm_pillar', job:'firemage', name:'불기둥', lv:42, mp:22, cd:6, type:'ground', coef:1.0, base:'matk', el:'fire',
 radius:64, castRange:320, ticks:8, tickRate:0.3, icon:'🔥', desc:'불기둥이 솟아 지속적으로 태운다.'},
{id:'fm_inferno', job:'firemage', name:'인페르노', lv:46, mp:30, cd:10, type:'aura', coef:0.8, base:'matk', el:'fire',
 radius:104, dur:6, tickRate:0.4, icon:'♨️', desc:'6초간 몸에서 화염을 뿜어 주변을 태운다.'},
{id:'fm_dash', job:'firemage', name:'화염 질주', lv:50, mp:20, cd:6, type:'dash', coef:2.0, base:'matk', el:'fire',
 dist:230, width:44, invuln:0.3, dot:{el:'fire', dps:0.25, dur:3}, icon:'💨', desc:'불길을 남기며 돌진한다.'},
{id:'fm_meteor', job:'firemage', name:'메테오', lv:55, mp:48, cd:14, type:'ground', coef:6.0, base:'matk', el:'fire',
 radius:130, castRange:340, delay:1.1, dot:{el:'fire', dps:0.4, dur:5}, icon:'☄️', desc:'거대한 운석을 떨어뜨린다.'},

/* ── 냉기법사 ───────────────────────────────────────────── */
{id:'im_spear', job:'icemage', name:'얼음 창', lv:40, mp:14, cd:2.4, type:'proj', coef:2.6, base:'matk', el:'ice',
 speed:340, range:380, pierce:4, slow:{amt:0.4, dur:2.5}, icon:'🧊', desc:'관통하며 둔화시키는 얼음 창.'},
{id:'im_field', job:'icemage', name:'빙결의 대지', lv:42, mp:26, cd:8, type:'ground', coef:1.9, base:'matk', el:'ice',
 radius:104, castRange:300, freeze:1.4, icon:'🌨️', desc:'지면을 얼려 적을 1.4초간 빙결시킨다.'},
{id:'im_blizzard', job:'icemage', name:'눈보라', lv:46, mp:34, cd:11, type:'ground', coef:0.9, base:'matk', el:'ice',
 radius:130, castRange:300, ticks:12, tickRate:0.25, slow:{amt:0.35, dur:1.5}, icon:'🌬️', desc:'넓은 지역에 눈보라를 몰아친다.'},
{id:'im_armor', job:'icemage', name:'서리 갑옷', lv:50, mp:28, cd:20, type:'buff', base:'matk', el:'ice',
 dur:12, buff:{def:0.6, shield:3.0, thorns:0.4}, icon:'🛡️', desc:'보호막을 두르고 접촉한 적을 얼린다.'},
{id:'im_zero', job:'icemage', name:'절대 영도', lv:55, mp:46, cd:15, type:'nova', coef:4.4, base:'matk', el:'ice',
 radius:150, freeze:2.2, icon:'❄️', desc:'주변 전체를 얼려붙인다.'},

/* ── 전격법사 ───────────────────────────────────────────── */
{id:'bm_bolt', job:'boltmage', name:'라이트닝 볼트', lv:40, mp:10, cd:1.2, type:'proj', coef:2.0, base:'matk', el:'lightning',
 speed:620, range:420, pierce:2, icon:'⚡', desc:'매우 빠른 번개 탄환.'},
{id:'bm_chain', job:'boltmage', name:'연쇄 번개', lv:42, mp:22, cd:5, type:'chain', coef:2.4, base:'matk', el:'lightning',
 jumps:6, jumpRange:130, castRange:300, falloff:0.85, icon:'🔗', desc:'번개가 최대 6명에게 튄다.'},
{id:'bm_strike', job:'boltmage', name:'천둥 낙뢰', lv:46, mp:26, cd:6, type:'ground', coef:3.4, base:'matk', el:'lightning',
 radius:76, castRange:340, delay:0.25, icon:'🌩️', desc:'지정 지점에 벼락을 내리친다.'},
{id:'bm_dash', job:'boltmage', name:'전격 질주', lv:50, mp:18, cd:5, type:'dash', coef:2.2, base:'matk', el:'lightning',
 dist:250, width:44, blink:true, invuln:0.3, icon:'💫', desc:'번개가 되어 적을 감전시키며 이동한다.'},
{id:'bm_storm', job:'boltmage', name:'폭풍의 눈', lv:55, mp:44, cd:13, type:'aura', coef:1.2, base:'matk', el:'lightning',
 radius:140, dur:6, tickRate:0.35, icon:'🌀', desc:'6초간 몸 주위에 뇌우를 두른다.'},

/* ── 신궁 ───────────────────────────────────────────────── */
{id:'rg_pierce', job:'ranger', name:'관통 사격', lv:40, mp:16, cd:2.6, type:'beam', coef:3.6, base:'atk', el:'phys',
 length:460, width:30, icon:'➶', desc:'화면 끝까지 뻗는 관통 화살.'},
{id:'rg_storm', job:'ranger', name:'폭우 화살', lv:42, mp:30, cd:9, type:'ground', coef:0.7, base:'atk', el:'phys',
 radius:130, castRange:360, ticks:14, tickRate:0.2, icon:'🌧️', desc:'넓은 지역에 화살을 퍼붓는다.'},
{id:'rg_eye', job:'ranger', name:'매의 눈', lv:46, mp:26, cd:20, type:'buff', base:'atk', el:'phys',
 dur:12, buff:{crit:30, atk:0.25}, icon:'🦅', desc:'12초간 치명타 확률 +30%, 공격력 25% 증가.'},
{id:'rg_rapid', job:'ranger', name:'연사', lv:50, mp:24, cd:7, type:'proj', coef:1.1, base:'atk', el:'phys',
 count:8, spread:0.1, burst:0.07, speed:520, range:420, icon:'🎯', desc:'화살 8발을 연달아 쏟아붓는다.'},
{id:'rg_snipe', job:'ranger', name:'필중의 화살', lv:55, mp:34, cd:11, type:'proj', coef:6.5, base:'atk', el:'phys',
 speed:340, range:520, homing:true, radius:52, icon:'🏹', desc:'적을 추적해 반드시 명중하는 일격.'},

/* ── 베놈 ───────────────────────────────────────────────── */
{id:'vn_flurry', job:'venom', name:'독날 난무', lv:40, mp:14, cd:2.2, type:'arc', coef:0.9, base:'atk', el:'poison',
 range:52, arc:1.6, hits:4, hitRate:0.08, dot:{el:'poison', dps:0.3, dur:5}, icon:'🗡️', desc:'단검을 4번 휘둘러 독을 쌓는다.'},
{id:'vn_shadow', job:'venom', name:'그림자 이동', lv:42, mp:16, cd:5, type:'dash', coef:1.6, base:'atk', el:'dark',
 dist:220, width:36, blink:true, invuln:0.4, icon:'🌑', desc:'그림자를 타고 순간이동한다.'},
{id:'vn_cloud', job:'venom', name:'맹독 살포', lv:46, mp:26, cd:8, type:'ground', coef:0.6, base:'atk', el:'poison',
 radius:110, castRange:220, ticks:12, tickRate:0.4, slow:{amt:0.3, dur:1}, icon:'☠️', desc:'맹독 구름을 퍼뜨린다.'},
{id:'vn_assassin', job:'venom', name:'암살', lv:50, mp:28, cd:10, type:'arc', coef:4.6, base:'atk', el:'dark',
 range:56, arc:1.0, critBonus:60, icon:'🔪', desc:'치명타 확률이 60% 추가되는 급소 찌르기.'},
{id:'vn_toxin', job:'venom', name:'독 강화', lv:55, mp:30, cd:22, type:'buff', base:'atk', el:'poison',
 dur:14, buff:{atk:0.35, aspd:0.4, lifesteal:0.12}, icon:'🧪', desc:'14초간 공격속도 40%, 공격력 35% 증가.'},

/* ── 크루세이더 ─────────────────────────────────────────── */
{id:'cr_smite', job:'crusader', name:'성스러운 강타', lv:40, mp:16, cd:2.8, type:'arc', coef:3.0, base:'atk', el:'holy',
 range:66, arc:1.8, lifesteal:0.3, icon:'🔨', desc:'신성 피해를 주고 30%를 회복한다.'},
{id:'cr_hammer', job:'crusader', name:'심판의 망치', lv:42, mp:26, cd:7, type:'ground', coef:3.2, base:'atk', el:'holy',
 radius:96, castRange:220, delay:0.3, stun:0.6, icon:'⚒️', desc:'망치를 내던져 광역 기절시킨다.'},
{id:'cr_shield', job:'crusader', name:'신성 보호막', lv:46, mp:28, cd:18, type:'buff', base:'matk', el:'holy',
 dur:10, buff:{shield:4.0, def:0.4}, icon:'🛡️', desc:'큰 보호막을 두른다.'},
{id:'cr_charge', job:'crusader', name:'정의의 돌진', lv:50, mp:22, cd:6, type:'dash', coef:2.8, base:'atk', el:'holy',
 dist:220, width:44, stun:0.6, icon:'🐎', desc:'적을 밀어내며 돌진한다.'},
{id:'cr_wrath', job:'crusader', name:'천벌', lv:55, mp:40, cd:12, type:'nova', coef:4.6, base:'atk', el:'holy',
 radius:140, lifesteal:0.2, icon:'⚡', desc:'주변 전체에 신의 분노를 내린다.'},

/* ── 클레릭 ─────────────────────────────────────────────── */
{id:'cl_greatheal', job:'cleric', name:'대치유', lv:40, mp:30, cd:7, type:'heal', coef:4.0, base:'matk', el:'holy',
 icon:'💚', desc:'많은 양의 체력을 즉시 회복한다.'},
{id:'cl_light', job:'cleric', name:'신성한 빛', lv:42, mp:14, cd:2, type:'proj', coef:2.3, base:'matk', el:'holy',
 count:2, spread:0.18, speed:300, range:360, homing:true, icon:'🔆', desc:'적을 따라가는 빛 구슬 2개.'},
{id:'cl_regen', job:'cleric', name:'부활의 기운', lv:46, mp:26, cd:18, type:'buff', base:'matk', el:'holy',
 dur:14, buff:{regen:0.035, def:0.25}, icon:'🌿', desc:'14초간 초당 체력 3.5%를 회복한다.'},
{id:'cl_purify', job:'cleric', name:'정화의 파동', lv:50, mp:28, cd:8, type:'nova', coef:2.6, base:'matk', el:'holy',
 radius:120, healSelf:0.6, icon:'🔔', desc:'파동으로 적을 태우고 자신을 치유한다.'},
{id:'cl_sanct', job:'cleric', name:'성역', lv:55, mp:42, cd:14, type:'aura', coef:1.0, base:'matk', el:'holy',
 radius:130, dur:8, tickRate:0.4, healTick:0.02, icon:'⛪', desc:'8초간 성역을 펼쳐 적을 태우고 자신을 회복한다.'},

/* ── 수도승 ─────────────────────────────────────────────── */
{id:'mo_combo', job:'monk', name:'연환권', lv:40, mp:12, cd:1.8, type:'arc', coef:0.85, base:'atk', el:'phys',
 range:46, arc:1.5, hits:5, hitRate:0.07, icon:'👊', desc:'주먹을 5연타로 내지른다.'},
{id:'mo_uppercut', job:'monk', name:'승룡각', lv:42, mp:20, cd:6, type:'nova', coef:2.8, base:'atk', el:'phys',
 radius:78, stun:0.9, icon:'🐉', desc:'솟구쳐 오르며 주변을 띄운다.'},
{id:'mo_chi', job:'monk', name:'기공파', lv:46, mp:18, cd:3.5, type:'proj', coef:2.6, base:'atk', el:'magic',
 speed:400, range:340, pierce:3, radius:44, icon:'🌀', desc:'기를 모아 쏘아 보낸다.'},
{id:'mo_med', job:'monk', name:'명상', lv:50, mp:0, cd:16, type:'buff', base:'atk', el:'holy',
 dur:8, buff:{regen:0.04, mpregen:0.06, aspd:0.3}, icon:'🧘', desc:'8초간 체력·마나를 빠르게 회복하고 공격속도가 오른다.'},
{id:'mo_storm', job:'monk', name:'폭풍의 권', lv:55, mp:36, cd:12, type:'aura', coef:0.9, base:'atk', el:'phys',
 radius:88, dur:4, tickRate:0.15, moveMul:0.8, lifesteal:0.12, icon:'🥊', desc:'4초간 주변을 난타한다.'}
];

/* id → 스킬 */
var SKILL_BY_ID = (function(){ var m={}; for(var i=0;i<SKILL_DB.length;i++) m[SKILL_DB[i].id]=SKILL_DB[i]; return m; })();

/* 직업(1차 또는 2차)이 배울 수 있는 스킬 목록 */
function skillsOfJob(job){
  var out=[];
  for(var i=0;i<SKILL_DB.length;i++) if(SKILL_DB[i].job===job) out.push(SKILL_DB[i]);
  return out;
}

/* ============================================================
   몬스터
   art : assets/mob 의 스프라이트 이름, h = 화면상 높이(px)
   ai  : melee(접근 후 타격) / ranged(거리 유지 후 사격) / charger(돌진)
   ============================================================ */
var MONSTER_DB = [
{id:'slime',        name:'슬라임',        art:'slime',         h:64,  ai:'melee',  minWave:1,  hp:34,  atk:7,  def:2,  spd:44, r:13, xp:9},
{id:'goblin',       name:'고블린',        art:'goblin',        h:82,  ai:'melee',  minWave:2,  hp:52,  atk:11, def:4,  spd:66, r:14, xp:16},
{id:'slime_poison', name:'독 슬라임',     art:'slime_poison',  h:66,  ai:'melee',  minWave:4,  hp:48,  atk:10, def:3,  spd:48, r:13, xp:15},
{id:'goblin_archer',name:'고블린 궁수',   art:'goblin_archer', h:82,  ai:'ranged', minWave:5,  hp:44,  atk:12, def:3,  spd:60, r:13, xp:20,
 proj:{speed:250, range:280, cd:2.2, el:'phys'}},
{id:'zombie',       name:'좀비',          art:'zombie',        h:88,  ai:'melee',  minWave:6,  hp:110, atk:14, def:5,  spd:38, r:15, xp:26},
{id:'goblin_knight',name:'고블린 기사',   art:'goblin_knight', h:86,  ai:'melee',  minWave:7,  hp:96,  atk:15, def:9,  spd:62, r:15, xp:30},
{id:'skeleton',     name:'해골 병사',     art:'skeleton',      h:90,  ai:'melee',  minWave:8,  hp:78,  atk:16, def:7,  spd:72, r:14, xp:28},
{id:'ghoul',        name:'구울',          art:'ghoul',         h:88,  ai:'charger',minWave:10, hp:92,  atk:19, def:6,  spd:84, r:14, xp:36},
{id:'lizard',       name:'리자드맨',      art:'lizard',        h:94,  ai:'melee',  minWave:11, hp:130, atk:21, def:10, spd:68, r:15, xp:44},
{id:'lizard_archer',name:'리자드 궁수',   art:'lizard_archer', h:92,  ai:'ranged', minWave:12, hp:104, atk:22, def:8,  spd:64, r:15, xp:48,
 proj:{speed:290, range:320, cd:2.0, el:'phys'}},
{id:'spirit_dark',  name:'어둠 정령',     art:'spirit_dark',   h:92,  ai:'ranged', minWave:13, hp:96,  atk:24, def:6,  spd:80, r:14, xp:52,
 proj:{speed:210, range:300, cd:2.4, el:'dark'}},
{id:'orc',          name:'오크',          art:'orc',           h:100, ai:'melee',  minWave:14, hp:170, atk:25, def:12, spd:62, r:17, xp:58},
{id:'orc_warrior',  name:'오크 전사',     art:'orc_warrior',   h:106, ai:'melee',  minWave:16, hp:230, atk:31, def:15, spd:64, r:18, xp:72},
{id:'orc_mage',     name:'오크 주술사',   art:'orc_mage',      h:100, ai:'ranged', minWave:17, hp:150, atk:30, def:10, spd:58, r:16, xp:76,
 proj:{speed:240, range:330, cd:1.9, el:'fire'}},
{id:'darkelf',      name:'다크엘프',      art:'darkelf',       h:96,  ai:'charger',minWave:18, hp:190, atk:34, def:12, spd:90, r:16, xp:84},
{id:'darkelf_mage', name:'다크엘프 마법사',art:'darkelf_mage', h:96,  ai:'ranged', minWave:19, hp:160, atk:35, def:11, spd:66, r:16, xp:90,
 proj:{speed:260, range:340, cd:1.7, el:'dark'}},
{id:'succubus',     name:'서큐버스',      art:'succubus',      h:98,  ai:'charger',minWave:21, hp:210, atk:38, def:13, spd:96, r:16, xp:100},
{id:'darkelf_knight',name:'다크엘프 기사',art:'darkelf_knight',h:100, ai:'charger',minWave:23, hp:280, atk:42, def:20, spd:86, r:17, xp:118},
{id:'golem',        name:'석상 골렘',     art:'golem',         h:116, ai:'charger',minWave:25, hp:420, atk:46, def:28, spd:52, r:21, xp:150}
];

/* 보스 (5웨이브마다 등장) */
var BOSS_DB = [
{id:'b_slime',  name:'슬라임 킹',     art:'slime_king',    h:150, ai:'melee',  hp:760,  atk:34, def:14, spd:44, r:28, xp:460},
{id:'b_goblin', name:'고블린 군주',   art:'goblin_lord',   h:150, ai:'melee',  hp:900,  atk:40, def:16, spd:62, r:26, xp:540},
{id:'b_orc',    name:'오크 군주',     art:'orc_lord',      h:165, ai:'melee',  hp:1250, atk:48, def:22, spd:58, r:30, xp:660},
{id:'b_lich',   name:'리치',          art:'lich',          h:160, ai:'ranged', hp:1000, atk:52, def:16, spd:64, r:26, xp:720,
 proj:{speed:250, range:360, cd:1.3, el:'dark'}},
{id:'b_queen',  name:'다크엘프 여왕', art:'darkelf_queen', h:158, ai:'ranged', hp:1150, atk:56, def:18, spd:74, r:26, xp:800,
 proj:{speed:290, range:360, cd:1.1, el:'dark'}},
{id:'b_chaos',  name:'혼돈의 군주',   art:'chaos_lord',    h:180, ai:'charger',hp:1700, atk:64, def:26, spd:78, r:32, xp:960},
{id:'b_demon',  name:'마왕',          art:'demon_lord',    h:200, ai:'charger',hp:2400, atk:74, def:32, spd:72, r:36, xp:1250}
];

/* 레벨업 필요 경험치 — 40레벨(2차 전직)까지 대략 20~30분 */
function xpNeed(lv){
  return Math.floor(22 * Math.pow(lv, 1.5) + 24 * lv);
}
var MAX_LEVEL = 60;

/* ============================================================
   이펙트 시트 배정 (assets/fx, 8프레임)
   ============================================================ */
var WEAPON_FX = {
  sword:'slash_dust', greatsword:'slash_cross', longsword:'slash_arcane',
  dagger:'slash_claw', mace:'slash_gold', fist:'burst_white',
  staff:'burst_white', bow:'dust_ground'
};
var EL_FX = {
  phys:'slash_dust', fire:'burst_flame', ice:'ice_burst', lightning:'holy_burst',
  holy:'holy_burst', poison:'poison_splash', magic:'burst_white', dark:'slash_dark'
};
var SKILL_FX = {
  /* 기사 */
  kn_smash:'slash_dust', kn_charge:'dust_ground', kn_whirl:'slash_cross',
  kn_shout:'rune_circle', kn_quake:'dust_ground',
  /* 마법사 */
  mg_missile:'burst_white', mg_fireball:'boom_red', mg_nova:'nova_arcane',
  mg_blink:'nova_arcane', mg_orb:'slash_arcane',
  /* 궁수 */
  ar_power:'ice_shard', ar_multi:'dust_ground', ar_roll:'dust_ground',
  ar_poison:'poison_splash', ar_rain:'arrow_rain',
  /* 사제 */
  pr_strike:'slash_gold', pr_heal:'heal_burst', pr_wave:'holy_burst',
  pr_bless:'rune_circle', pr_judge:'holy_pillar',
  /* 대검전사 */
  gs_cleave:'slash_cross', gs_shock:'dust_ground', gs_spin:'slash_cross',
  gs_rage:'burst_flame', gs_exec:'slash_claw',
  /* 마검사 */
  mk_wave:'slash_arcane', mk_burst:'nova_arcane', mk_step:'slash_arcane',
  mk_awake:'rune_circle', mk_rune:'boom_crimson',
  /* 화염법사 */
  fm_blast:'boom_red', fm_pillar:'pillar_fire', fm_inferno:'burst_flame',
  fm_dash:'burst_flame', fm_meteor:'meteor',
  /* 냉기법사 */
  im_spear:'ice_shard', im_field:'water_burst', im_blizzard:'ice_burst',
  im_armor:'dome_white', im_zero:'ice_burst',
  /* 전격법사 */
  bm_bolt:'burst_white', bm_chain:'holy_burst', bm_strike:'holy_pillar',
  bm_dash:'burst_white', bm_storm:'holy_burst',
  /* 신궁 */
  rg_pierce:'ice_shard', rg_storm:'arrow_rain', rg_eye:'rune_circle',
  rg_rapid:'dust_ground', rg_snipe:'burst_white',
  /* 베놈 */
  vn_flurry:'slash_claw', vn_shadow:'slash_dark', vn_cloud:'poison_splash',
  vn_assassin:'slash_dark', vn_toxin:'rune_circle',
  /* 크루세이더 */
  cr_smite:'slash_gold', cr_hammer:'holy_burst', cr_shield:'dome_white',
  cr_charge:'crescent_gold', cr_wrath:'holy_burst',
  /* 클레릭 */
  cl_greatheal:'heal_burst', cl_light:'holy_burst', cl_regen:'heal_burst',
  cl_purify:'dome_white', cl_sanct:'holy_pillar',
  /* 수도승 */
  mo_combo:'burst_white', mo_uppercut:'dust_ground', mo_chi:'nova_arcane',
  mo_med:'rune_circle', mo_storm:'slash_cross'
};

/* ============================================================
   월드 스케일 — 스프라이트를 원본 픽셀 크기로 그리기 때문에
   거리/속도 값도 같은 배율로 키운다. 위쪽 데이터는 읽기 좋은
   기준값(1배)으로 두고 여기서 한 번에 환산한다.
   ============================================================ */
var WORLD_SCALE = 2;
(function(U){
  var DIST = ['range','speed','radius','dist','castRange','length','width','jumpRange'];
  function scale(o){
    for(var i = 0; i < DIST.length; i++)
      if(typeof o[DIST[i]] === 'number') o[DIST[i]] *= U;
  }
  var k, i;
  for(k in WEAPON_DB) scale(WEAPON_DB[k]);
  for(i = 0; i < SKILL_DB.length; i++){
    scale(SKILL_DB[i]);
    SKILL_DB[i].fx = SKILL_FX[SKILL_DB[i].id] || EL_FX[SKILL_DB[i].el] || 'burst_white';
  }
  for(k in CLASS_DB) CLASS_DB[k].base.spd *= U;
  for(k in JOB2_DB) if(JOB2_DB[k].add.spd) JOB2_DB[k].add.spd *= U;
  function mob(m){ m.spd *= U; m.r *= U; if(m.proj) scale(m.proj); }
  for(i = 0; i < MONSTER_DB.length; i++) mob(MONSTER_DB[i]);
  for(i = 0; i < BOSS_DB.length; i++) mob(BOSS_DB[i]);
})(WORLD_SCALE);
