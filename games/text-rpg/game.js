/* ==========================================================================
   잊혀진 탑 — 게임 엔진
   ========================================================================== */

(function () {
  'use strict';

  var D = window.GAME_DATA;
  var SAVE_KEY = 'forgotten-tower:save';
  var RECORD_KEY = 'forgotten-tower:records';

  /* --- 작은 도구들 -------------------------------------------------------- */

  function $(id) { return document.getElementById(id); }
  function randInt(a, b) { return a + Math.floor(Math.random() * (b - a + 1)); }
  function pick(arr) { return arr[Math.floor(Math.random() * arr.length)]; }
  function chance(p) { return Math.random() < p; }
  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  // 한글 받침 여부에 따라 조사만 고릅니다. josaOf('검','을를') -> '을'
  function josaOf(word, pair) {
    var str = String(word);
    var last = str.charCodeAt(str.length - 1);
    var hasJong = (last >= 0xac00 && last <= 0xd7a3) && ((last - 0xac00) % 28 !== 0);
    return hasJong ? pair[0] : pair[1];
  }

  // 단어에 조사를 붙여 돌려줍니다. josa('검','을를') -> '검을'
  function josa(word, pair) { return word + josaOf(word, pair); }

  /* --- 상태 -------------------------------------------------------------- */

  var S = null;   // 플레이어 / 진행 상태
  var C = null;   // 전투 상태

  function classOf(id) {
    for (var i = 0; i < D.CLASSES.length; i++) {
      if (D.CLASSES[i].id === id) { return D.CLASSES[i]; }
    }
    return D.CLASSES[0];
  }

  function expNeed(level) {
    return Math.round(26 + (level - 1) * 20 + Math.pow(level - 1, 2) * 3.2);
  }

  // 레벨과 영구 보너스로부터 능력치를 다시 계산합니다.
  function recalc() {
    var cls = classOf(S.classId);
    var n = S.level - 1;
    S.maxHp = Math.round(cls.base.hp + cls.growth.hp * n) + S.bonus.hp;
    S.maxMp = Math.round(cls.base.mp + cls.growth.mp * n) + S.bonus.mp;
    S.atk   = Math.round(cls.base.atk + cls.growth.atk * n) + S.bonus.atk;
    S.def   = Math.round(cls.base.def + cls.growth.def * n) + S.bonus.def;
    S.spd   = Math.round(cls.base.spd + cls.growth.spd * n) + S.bonus.spd;
    S.luk   = Math.round(cls.base.luk + cls.growth.luk * n) + S.bonus.luk;
    S.hp = clamp(S.hp, 0, S.maxHp);
    S.mp = clamp(S.mp, 0, S.maxMp);
  }

  function PN() { return '<em>' + esc(S.name) + '</em>'; }

  /* --- 저장 / 불러오기 ---------------------------------------------------- */

  function save() {
    try { localStorage.setItem(SAVE_KEY, JSON.stringify(S)); } catch (e) { /* 무시 */ }
  }
  function loadSave() {
    try {
      var raw = localStorage.getItem(SAVE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (e) { return null; }
  }
  function clearSave() {
    try { localStorage.removeItem(SAVE_KEY); } catch (e) { /* 무시 */ }
  }
  function records() {
    try {
      var raw = localStorage.getItem(RECORD_KEY);
      var arr = raw ? JSON.parse(raw) : [];
      return Array.isArray(arr) ? arr : [];
    } catch (e) { return []; }
  }
  function addRecord(entry) {
    try {
      var list = records();
      list.push(entry);
      list.sort(function (a, b) { return b.floor - a.floor || b.level - a.level; });
      localStorage.setItem(RECORD_KEY, JSON.stringify(list.slice(0, 8)));
    } catch (e) { /* 무시 */ }
  }

  /* --- 화면 출력 ---------------------------------------------------------- */

  var logEl = $('log');
  var choicesEl = $('choices');

  function clearLog() { logEl.textContent = ''; }

  function log(html, cls) {
    var p = document.createElement('p');
    if (cls) { p.className = cls; }
    p.innerHTML = html;
    logEl.appendChild(p);
    logEl.scrollTop = logEl.scrollHeight;
  }

  function logTitle(text) { log(esc(text), 't-title'); }
  function logArt(emoji) {
    var d = document.createElement('div');
    d.className = 'art';
    d.textContent = emoji;
    logEl.appendChild(d);
    logEl.scrollTop = logEl.scrollHeight;
  }
  function logGap() { log('&nbsp;', 't-dim'); }

  /**
   * 선택지 버튼을 그립니다.
   * @param {Array} list {label, sub, cls, disabled, onClick}
   */
  function setChoices(list) {
    choicesEl.textContent = '';
    list.forEach(function (c) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'choice' + (c.cls ? ' ' + c.cls : '');
      btn.disabled = !!c.disabled;

      var main = document.createElement('span');
      main.className = 'c-main';
      main.textContent = c.label;
      btn.appendChild(main);

      if (c.sub) {
        var sub = document.createElement('span');
        sub.className = 'c-sub';
        sub.textContent = c.sub;
        btn.appendChild(sub);
      }
      if (c.onClick) { btn.addEventListener('click', c.onClick); }
      choicesEl.appendChild(btn);
    });
  }

  /* --- HUD ---------------------------------------------------------------- */

  function renderHud() {
    if (!S) { $('hud').hidden = true; return; }
    var cls = classOf(S.classId);
    $('hud').hidden = false;
    $('hudEmoji').textContent = cls.emoji;
    $('hudName').textContent = S.name;
    $('hudClass').textContent = cls.name + ' · ' + S.kills + '마리 처치';

    $('hpFill').style.width = (S.maxHp ? (S.hp / S.maxHp) * 100 : 0) + '%';
    $('mpFill').style.width = (S.maxMp ? (S.mp / S.maxMp) * 100 : 0) + '%';
    var need = expNeed(S.level);
    $('xpFill').style.width = clamp((S.exp / need) * 100, 0, 100) + '%';

    $('hpText').textContent = S.hp + '/' + S.maxHp;
    $('mpText').textContent = S.mp + '/' + S.maxMp;
    $('xpText').textContent = S.exp + '/' + need;

    $('hudFloor').textContent = S.floor + 'F';
    $('hudLevel').textContent = S.level;
    $('hudAtk').textContent = S.atk;
    $('hudDef').textContent = S.def;
    $('hudGold').textContent = S.gold + 'G';
  }

  function renderEnemy() {
    var box = $('enemyBox');
    if (!C || !C.enemy) { box.hidden = true; return; }
    var e = C.enemy;
    box.hidden = false;
    $('enemyEmoji').textContent = e.emoji;
    $('enemyName').textContent = e.name + (C.isBoss ? ' — 층주' : '');
    $('enemyHpText').textContent = Math.max(0, e.hp) + '/' + e.maxHp;
    $('enemyHpFill').style.width = clamp((e.hp / e.maxHp) * 100, 0, 100) + '%';
  }

  function render() { renderHud(); renderEnemy(); }

  /* --- 인벤토리 ----------------------------------------------------------- */

  function invAdd(id, n) {
    S.inv[id] = (S.inv[id] || 0) + (n || 1);
  }
  function invCount(id) { return S.inv[id] || 0; }
  function invList() {
    return Object.keys(S.inv).filter(function (k) { return S.inv[k] > 0 && D.ITEMS[k]; });
  }
  function invRemove(id) {
    if (S.inv[id]) {
      S.inv[id] -= 1;
      if (S.inv[id] <= 0) { delete S.inv[id]; }
    }
  }

  /* --- 타이틀 ------------------------------------------------------------- */

  function screenTitle() {
    S = null; C = null;
    render();
    $('enemyBox').hidden = true;
    clearLog();

    logArt('🗼');
    logTitle('잊혀진 탑');
    log('탑은 오르는 자를 기억하지 않는다. 오직 얼마나 높이 올랐는지만 남을 뿐.');
    log('세 직업 중 하나를 골라 층을 오르십시오. 5층마다 층주가 길을 막습니다.', 't-dim');

    var list = records();
    if (list.length) {
      logGap();
      logTitle('전당');
      list.slice(0, 5).forEach(function (r, i) {
        log((i + 1) + '. <em>' + esc(r.name) + '</em> — ' + esc(r.cls) +
            ' · <em>' + r.floor + '층</em> · Lv.' + r.level + ' · ' + r.kills + '마리 처치', 't-dim');
      });
    }

    var saved = loadSave();
    var choices = [];

    if (saved && saved.hp > 0) {
      choices.push({
        label: '이어하기',
        sub: saved.name + ' · Lv.' + saved.level + ' · ' + saved.floor + '층',
        cls: 'primary',
        onClick: function () {
          S = saved;
          if (!S.bonus) { S.bonus = { hp: 0, mp: 0, atk: 0, def: 0, spd: 0, luk: 0 }; }
          if (!S.inv) { S.inv = {}; }
          if (typeof S.bossDone !== 'boolean') { S.bossDone = false; }
          recalc();
          clearLog();
          logTitle(S.floor + '층');
          log('발걸음을 되짚어 다시 탑으로 들어섭니다.');
          landing();
        }
      });
    }
    choices.push({ label: '새 게임', sub: '직업을 고르고 처음부터', cls: saved && saved.hp > 0 ? '' : 'primary', onClick: screenClass });
    if (saved) {
      choices.push({ label: '저장 데이터 지우기', sub: '기록은 남습니다', cls: 'ghost', onClick: function () {
        clearSave();
        screenTitle();
      } });
    }
    setChoices(choices);
  }

  /* --- 직업 선택 / 이름 ---------------------------------------------------- */

  function screenClass() {
    clearLog();
    logTitle('직업 선택');
    log('어떤 방식으로 탑을 오르시겠습니까?');
    D.CLASSES.forEach(function (c) {
      log(c.emoji + ' <em>' + esc(c.name) + '</em> — ' + esc(c.blurb));
      log('HP ' + c.base.hp + ' · MP ' + c.base.mp + ' · 공격 ' + c.base.atk +
          ' · 방어 ' + c.base.def + ' · 속도 ' + c.base.spd + ' · 행운 ' + c.base.luk, 't-dim');
      log('고유 기술 — <em>' + esc(c.skill.name) + '</em> (MP ' + c.skill.cost + ') ' + esc(c.skill.desc), 't-dim');
    });

    var list = D.CLASSES.map(function (c) {
      return { label: c.emoji + ' ' + c.name, sub: c.skill.name, onClick: function () { screenName(c); } };
    });
    list.push({ label: '← 뒤로', cls: 'ghost', onClick: screenTitle });
    setChoices(list);
  }

  function screenName(cls) {
    clearLog();
    logArt(cls.emoji);
    logTitle(cls.name + '의 이름');
    log('탑에 새겨질 이름을 정하십시오.');

    choicesEl.textContent = '';
    var form = document.createElement('form');
    form.className = 'name-form';

    var input = document.createElement('input');
    input.type = 'text';
    input.maxLength = 12;
    input.placeholder = '이름 (최대 12자)';
    input.setAttribute('aria-label', '캐릭터 이름');

    var ok = document.createElement('button');
    ok.type = 'submit';
    ok.className = 'choice primary';
    ok.textContent = '탑에 들어선다';

    form.append(input, ok);
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var name = input.value.trim() || '이름 없는 자';
      startGame(cls, name.slice(0, 12));
    });
    choicesEl.appendChild(form);
    input.focus();
  }

  function startGame(cls, name) {
    S = {
      name: name,
      classId: cls.id,
      level: 1,
      exp: 0,
      gold: 60,
      floor: 1,
      room: 0,
      roomsInFloor: randInt(3, 4),
      kills: 0,
      bossKills: 0,
      bossDone: false,
      inv: {},
      bonus: { hp: 0, mp: 0, atk: 0, def: 0, spd: 0, luk: 0 },
      hp: 9999, mp: 9999
    };
    recalc();
    S.hp = S.maxHp;
    S.mp = S.maxMp;
    cls.startItems.forEach(function (id) { invAdd(id, 1); });

    clearLog();
    logArt('🚪');
    logTitle('1층 — 열린 문');
    log('탑의 문은 언제나 열려 있다. 닫히는 쪽은 늘 등 뒤였다.');
    log(PN() + ', ' + josa(cls.name, '은는') + ' 첫 계단에 발을 올렸다.');
    save();
    landing();
  }

  /* --- 층 진행 ------------------------------------------------------------ */

  // 층의 시작점(계단참): 다음 방으로 갈지 정합니다.
  function landing() {
    render();

    if (S.room >= S.roomsInFloor) {
      // 이 층의 방을 모두 지났습니다.
      if (S.floor % 5 === 0 && !S.bossDone) {
        bossIntro();
      } else {
        stairs();
      }
      return;
    }

    var left = S.roomsInFloor - S.room;
    setChoices([
      { label: '앞으로 나아간다', sub: '이 층에 ' + left + '개의 통로가 남았다', cls: 'primary', onClick: nextRoom },
      { label: '가방을 연다', sub: invList().length ? '아이템 ' + invList().length + '종' : '비어 있음',
        disabled: !invList().length, onClick: function () { openInventory(landing); } },
      { label: '저장하고 타이틀로', cls: 'ghost', onClick: function () { save(); screenTitle(); } }
    ]);
  }

  function stairs() {
    clearLog();
    logArt('🪜');
    logTitle(S.floor + '층 — 위층으로');
    log('통로 끝에서 위로 이어지는 계단을 찾았다.');

    var restCost = 18 + S.floor * 4;
    setChoices([
      { label: '계단을 오른다', sub: (S.floor + 1) + '층으로', cls: 'primary', onClick: function () {
        S.floor += 1;
        S.room = 0;
        S.roomsInFloor = randInt(3, 4);
        S.bossDone = false;
        save();
        clearLog();
        logTitle(S.floor + '층');
        log(pick([
          '공기가 한 단계 더 차가워졌다.',
          '계단을 다 오르자 발밑의 돌결이 달라졌다.',
          '아래층의 소리가 더는 들리지 않는다.',
          '벽에 새겨진 숫자가 ' + S.floor + '를 가리킨다.'
        ]), 't-flavor');
        landing();
      } },
      { label: '야영한다', sub: restCost + 'G · HP/MP 회복', disabled: S.gold < restCost, onClick: function () {
        S.gold -= restCost;
        var h = Math.round(S.maxHp * .55), m = Math.round(S.maxMp * .55);
        S.hp = clamp(S.hp + h, 0, S.maxHp);
        S.mp = clamp(S.mp + m, 0, S.maxMp);
        log('불을 피우고 잠시 눈을 붙였다. HP <em>+' + h + '</em>, MP <em>+' + m + '</em>', 't-good');
        save();
        stairs();
      } },
      { label: '가방을 연다', disabled: !invList().length, onClick: function () { openInventory(stairs); } }
    ]);
  }

  /* --- 방 진입 ------------------------------------------------------------ */

  function nextRoom() {
    S.room += 1;
    save();
    clearLog();

    var r = Math.random();
    if (r < .56) { roomCombat(); }
    else if (r < .74) { roomEvent(); }
    else if (r < .86) { roomTreasure(); }
    else if (r < .94) { roomCamp(); }
    else { roomMerchant(); }
  }

  function afterRoom() {
    render();
    save();
    setChoices([
      { label: '계속 나아간다', cls: 'primary', onClick: landing },
      { label: '가방을 연다', disabled: !invList().length, onClick: function () { openInventory(afterRoom); } }
    ]);
  }

  /* --- 방: 보물 ------------------------------------------------------------ */

  function roomTreasure() {
    logTitle('버려진 보관실');
    logArt('📦');
    log('무너진 선반 사이에서 쓸 만한 것을 찾아냈다.');

    if (chance(.55)) {
      var pool = ['potion_s', 'potion_s', 'ether_s', 'bomb', 'potion_l', 'smoke'];
      var id = pick(pool);
      invAdd(id, 1);
      var it = D.ITEMS[id];
      log(it.emoji + ' <em>' + esc(it.name) + '</em>' + josaOf(it.name, '을를') + ' 손에 넣었다.', 't-good');
    } else {
      var g = randInt(12, 26) + S.floor * 4;
      S.gold += g;
      log('낡은 주머니에서 <em>' + g + 'G</em>를 찾았다.', 't-gold');
    }
    afterRoom();
  }

  /* --- 방: 야영 ------------------------------------------------------------ */

  function roomCamp() {
    logTitle('바람이 통하는 방');
    logArt('🔥');
    log('벽이 무너진 틈으로 바깥바람이 들어온다. 잠시 숨을 고를 만한 자리다.');

    var h = Math.round(S.maxHp * .3) + 8;
    var m = Math.round(S.maxMp * .3) + 4;
    S.hp = clamp(S.hp + h, 0, S.maxHp);
    S.mp = clamp(S.mp + m, 0, S.maxMp);
    log('HP <em>+' + h + '</em>, MP <em>+' + m + '</em> 회복했다.', 't-good');
    afterRoom();
  }

  /* --- 방: 상인 ------------------------------------------------------------ */

  function roomMerchant() {
    logTitle('떠돌이 상인');
    logArt('🎒');
    log('후드를 눌러쓴 상인이 좌판을 펼치고 앉아 있다.');
    log('"올라가는 사람은 많은데, 내려오는 사람은 드물더군. 필요한 거 있나?"', 't-flavor');
    openShop(afterRoom);
  }

  function openShop(back) {
    render();
    var list = D.SHOP_STOCK.map(function (id) {
      var it = D.ITEMS[id];
      return {
        label: it.emoji + ' ' + it.name,
        sub: it.price + 'G · ' + it.desc,
        disabled: S.gold < it.price,
        onClick: function () {
          S.gold -= it.price;
          invAdd(id, 1);
          log('<em>' + esc(it.name) + '</em>' + josaOf(it.name, '을를') + ' 샀다. (-' + it.price + 'G)', 't-gold');
          save();
          openShop(back);
        }
      };
    });
    list.push({ label: '거래를 끝낸다', cls: 'ghost', onClick: function () { back(); } });
    setChoices(list);
  }

  /* --- 방: 이벤트 ---------------------------------------------------------- */

  function roomEvent() {
    var ev = pick(D.EVENTS);
    logTitle(ev.title);
    log(ev.text, 't-flavor');

    setChoices(ev.choices.map(function (c) {
      var poor = c.cost && S.gold < c.cost;
      return {
        label: c.label,
        sub: poor ? '골드가 부족하다' : null,
        disabled: !!poor,
        onClick: function () {
          if (c.cost) { S.gold -= c.cost; }
          resolveEvent(c.outcome);
        }
      };
    }));
  }

  function resolveEvent(outcome) {
    switch (outcome) {
      case 'pass':
        log('별다른 일 없이 방을 빠져나왔다.', 't-dim');
        break;

      case 'shrine_touch': {
        var r = Math.random();
        if (r < .45) {
          S.mp = S.maxMp;
          var h = Math.round(S.maxHp * .25);
          S.hp = clamp(S.hp + h, 0, S.maxHp);
          log('따뜻한 기운이 팔을 타고 올라온다. MP가 가득 차고 HP <em>+' + h + '</em>.', 't-good');
        } else if (r < .7) {
          var g = randInt(30, 60) + S.floor * 5;
          S.gold += g;
          log('제단 아래 감춰진 공간에서 <em>' + g + 'G</em>가 쏟아졌다.', 't-gold');
        } else if (r < .88) {
          var d = Math.max(4, Math.round(S.maxHp * .16));
          damagePlayer(d, '제단이 붉게 달아오르며 손을 태웠다');
        } else {
          S.bonus.atk += 1;
          recalc();
          log('제단이 낮게 울린다. 공격력이 <em>영구히 +1</em> 올랐다.', 't-good');
        }
        break;
      }

      case 'chest_open': {
        var r2 = Math.random();
        if (r2 < .15) {
          log('상자가 이빨을 드러냈다. 미믹이다!', 't-hit');
          startCombat(makeEnemy(pickMonsterFor(S.floor), false), false);
          return;
        }
        if (r2 < .7) {
          var id = pick(['potion_l', 'potion_s', 'ether_s', 'bomb', 'tonic', 'whetstone', 'lucky_coin']);
          invAdd(id, 1);
          log(D.ITEMS[id].emoji + ' 상자 안에서 <em>' + esc(D.ITEMS[id].name) + '</em>' + josaOf(D.ITEMS[id].name, '을를') + ' 찾았다.', 't-good');
        } else {
          var g2 = randInt(25, 55) + S.floor * 5;
          S.gold += g2;
          log('상자 바닥에 깔린 <em>' + g2 + 'G</em>를 챙겼다.', 't-gold');
        }
        break;
      }

      case 'fountain_drink':
        if (chance(.72)) {
          var h2 = Math.round(S.maxHp * .4);
          var m2 = Math.round(S.maxMp * .4);
          S.hp = clamp(S.hp + h2, 0, S.maxHp);
          S.mp = clamp(S.mp + m2, 0, S.maxMp);
          log('차갑고 깨끗하다. HP <em>+' + h2 + '</em>, MP <em>+' + m2 + '</em>', 't-good');
        } else {
          damagePlayer(Math.max(3, Math.round(S.maxHp * .12)), '물에서 쇠맛이 났다. 속이 뒤틀린다');
        }
        break;

      case 'corpse_loot':
        if (chance(.3)) {
          log('배낭에 손을 넣은 순간, 시체가 고개를 들었다.', 't-hit');
          startCombat(makeEnemy(pickMonsterFor(S.floor), false), false);
          return;
        } else {
          var g3 = randInt(20, 45) + S.floor * 4;
          S.gold += g3;
          invAdd('potion_s', 1);
          log('<em>' + g3 + 'G</em>와 작은 회복약을 챙겼다. 미안하다는 말은 하지 않았다.', 't-gold');
        }
        break;

      case 'corpse_pray':
        gainExp(Math.round(12 + S.floor * 3), true);
        log('두 손을 모으고 잠시 서 있었다. 무언가 배운 기분이 든다.', 't-good');
        break;

      case 'gamble':
        if (chance(.45)) {
          S.gold += 120;
          log('동전이 손등에 떨어졌다. <em>+120G</em>. 도박꾼이 헛웃음을 지었다.', 't-gold');
        } else {
          log('동전은 반대쪽이었다. 40G를 잃었다.', 't-dim');
        }
        break;

      default:
        break;
    }

    if (S.hp <= 0) { return gameOver('탑의 어둠 속에서'); }
    afterRoom();
  }

  /* --- 전투 준비 ----------------------------------------------------------- */

  // 층주는 등장 층에 맞춰 이미 설계된 수치를 쓰므로 층 배율을 받지 않습니다.
  // 일반 몬스터는 층에 따라 완만히 강해지고, 20층을 넘으면 압박이 한 단계 올라갑니다.
  function makeEnemy(base, isBoss) {
    var f = S.floor;
    var deep = Math.max(0, f - 20);
    var hpK  = isBoss ? 1 : 1 + (f - 1) * .09 + deep * .05;
    var atkK = isBoss ? 1 : 1 + (f - 1) * .06 + deep * .035;
    var defK = isBoss ? 1 : 1 + (f - 1) * .08;
    var rewK = 1 + (f - 1) * .12;

    return {
      id: base.id,
      name: base.name,
      emoji: base.emoji,
      flavor: base.flavor,
      maxHp: Math.round(base.hp * hpK),
      hp: Math.round(base.hp * hpK),
      atk: Math.round(base.atk * atkK),
      def: Math.round(base.def * defK),
      spd: base.spd,
      exp: Math.round(base.exp * rewK),
      gold: Math.round(base.gold * rewK)
    };
  }

  // 현재 층에서 등장할 수 있는 몬스터를 하나 고릅니다.
  function pickMonsterFor(floor) {
    var pool = D.MONSTERS.filter(function (m) { return m.tier <= floor; });
    if (!pool.length) { pool = [D.MONSTERS[0]]; }
    // 너무 약한 적만 계속 나오지 않도록 상위 절반에서 자주 뽑습니다.
    if (pool.length > 4 && chance(.7)) { pool = pool.slice(Math.floor(pool.length / 2)); }
    return pick(pool);
  }

  function roomCombat() {
    startCombat(makeEnemy(pickMonsterFor(S.floor), false), false);
  }

  function bossIntro() {
    clearLog();
    var idx = Math.floor(S.floor / 5) - 1;
    var cycle = Math.floor(idx / D.BOSSES.length);
    var base = D.BOSSES[Math.min(idx, D.BOSSES.length - 1)];

    var boss = makeEnemy(base, true);
    if (cycle > 0) {
      // 층주 목록을 한 바퀴 돈 뒤로는 같은 상대가 더 강해져 돌아옵니다.
      boss.maxHp = Math.round(boss.maxHp * (1 + cycle * .55));
      boss.hp = boss.maxHp;
      boss.atk = Math.round(boss.atk * (1 + cycle * .30));
      boss.exp = Math.round(boss.exp * (1 + cycle * .5));
      boss.gold = Math.round(boss.gold * (1 + cycle * .5));
      boss.name = boss.name + ' · 재림';
    }

    logTitle(S.floor + '층 — 층주');
    logArt(boss.emoji);
    log(boss.flavor, 't-flavor');
    log('물러설 곳은 없다. ' + josa(boss.name, '은는') + ' 도망칠 틈을 주지 않는다.', 't-hit');

    setChoices([
      { label: '맞선다', cls: 'primary danger', onClick: function () { startCombat(boss, true); } },
      { label: '가방을 연다', sub: '전투 전 마지막 준비', disabled: !invList().length,
        onClick: function () { openInventory(function () { bossPrep(boss); }); } }
    ]);
  }

  function bossPrep(boss) {
    render();
    setChoices([
      { label: '맞선다', cls: 'primary danger', onClick: function () { startCombat(boss, true); } },
      { label: '가방을 연다', disabled: !invList().length,
        onClick: function () { openInventory(function () { bossPrep(boss); }); } }
    ]);
  }

  function startCombat(enemy, isBoss) {
    C = { enemy: enemy, isBoss: isBoss, defending: false, turn: 0 };

    if (!isBoss) {
      logTitle('전투 — ' + enemy.name);
      logArt(enemy.emoji);
      log(enemy.flavor, 't-flavor');
    }
    render();

    // 속도 차가 크면 적이 선공합니다.
    if (enemy.spd > S.spd + 4 && chance(.6)) {
      log(josa(enemy.name, '이가') + ' 먼저 움직였다!', 't-hit');
      enemyTurn();
    } else {
      combatMenu();
    }
  }

  /* --- 전투 진행 ----------------------------------------------------------- */

  function critChance() { return clamp(.05 + S.luk * .012, .05, .45); }

  // 방어는 비율로 피해를 줄입니다. 높아도 0이 되지 않고, 낮아도 즉사하지 않습니다.
  // pierce 1 = 방어 전부 적용, 0.45 = 방어를 절반쯤 무시(마법)
  var DEF_K = 3.0;
  function calcDamage(atk, mult, targetDef, pierce) {
    var mitigation = 100 / (100 + targetDef * (pierce === undefined ? 1 : pierce) * DEF_K);
    var jitter = 0.9 + Math.random() * 0.2;
    return Math.max(1, Math.round(atk * mult * mitigation * jitter));
  }

  function dodgeChance(defenderSpd, attackerSpd) {
    return clamp(.02 + (defenderSpd - attackerSpd) * .012, 0, .28);
  }

  function combatMenu() {
    render();
    var cls = classOf(S.classId);
    var sk = cls.skill;

    setChoices([
      { label: '⚔️ 공격', sub: 'MP 소량 회복', cls: 'primary',
        onClick: function () {
          var gain = 3 + Math.floor(S.level / 4);
          var before = S.mp;
          S.mp = clamp(S.mp + gain, 0, S.maxMp);
          if (S.mp > before) { log('숨을 고르며 마력을 모았다. MP +' + (S.mp - before), 't-dim'); }
          playerAttack(1, 'phys', 0);
        } },
      { label: '✨ ' + sk.name, sub: 'MP ' + sk.cost + ' · ' + sk.desc, disabled: S.mp < sk.cost,
        onClick: function () {
          S.mp -= sk.cost;
          log(sk.text.replace('{name}', esc(S.name)));
          playerAttack(sk.mult, sk.type, sk.critBonus || 0);
        } },
      { label: '🛡️ 방어', sub: '받는 피해 절반', onClick: function () {
        C.defending = true;
        var m = Math.max(2, Math.round(S.maxMp * .1));
        S.mp = clamp(S.mp + m, 0, S.maxMp);
        log(PN() + josaOf(S.name, '이가') + ' 자세를 낮추고 방어했다. MP +' + m, 't-dim');
        enemyTurn();
      } },
      { label: '🎒 아이템', sub: invList().length ? invList().length + '종 보유' : '비어 있음',
        disabled: !invList().length, onClick: function () { openInventory(combatMenu, true); } },
      { label: '🏃 도주', sub: C.isBoss ? '층주에게선 불가' : '속도가 높을수록 유리',
        cls: 'ghost', disabled: C.isBoss, onClick: tryEscape }
    ]);
  }

  function playerAttack(mult, type, critBonus) {
    var e = C.enemy;

    if (chance(dodgeChance(e.spd, S.spd))) {
      log(josa(e.name, '이가') + ' 몸을 틀어 공격을 흘려보냈다.', 't-dim');
      return enemyTurn();
    }

    var crit = chance(critChance() + (critBonus || 0));
    var pierce = (type === 'magic') ? .45 : 1;
    var dmg = calcDamage(S.atk, mult, e.def, pierce);
    if (crit) { dmg = Math.round(dmg * 1.7); }

    e.hp -= dmg;
    if (crit) {
      log('치명타! ' + esc(e.name) + '에게' + ' <em>' + dmg + '</em>의 피해를 입혔다.', 't-crit');
    } else {
      log(esc(e.name) + '에게' + ' <em>' + dmg + '</em>의 피해를 입혔다.');
    }

    if (e.hp <= 0) { return victory(); }
    enemyTurn();
  }

  function tryEscape() {
    var e = C.enemy;
    var p = clamp(.42 + (S.spd - e.spd) * .03 + S.luk * .01, .15, .9);
    if (chance(p)) {
      log('등을 돌려 통로 밖으로 빠져나왔다.', 't-dim');
      C = null;
      renderEnemy();
      afterRoom();
    } else {
      log('길이 막혔다. 도망치지 못했다!', 't-hit');
      enemyTurn();
    }
  }

  function enemyTurn() {
    if (!C) { return; }
    var e = C.enemy;
    C.turn += 1;

    if (chance(dodgeChance(S.spd, e.spd))) {
      log(PN() + josaOf(S.name, '이가') + ' 몸을 낮춰 공격을 피했다.', 't-good');
      C.defending = false;
      return combatMenu();
    }

    var mult = 1;
    var isHeavy = chance(.18);
    if (isHeavy) { mult = 1.5; }

    var dmg = calcDamage(e.atk, mult, S.def, 1);
    if (C.defending) { dmg = Math.max(1, Math.round(dmg * .45)); }

    if (isHeavy) {
      log(josa(e.name, '이가') + ' 크게 몸을 젖혔다 — 강타!', 't-hit');
    }
    C.defending = false;
    damagePlayer(dmg, josa(e.name, '이가') + ' 덮쳐왔다');

    if (S.hp <= 0) { return gameOver(S.floor + '층, ' + e.name + '의 앞에서'); }
    combatMenu();
  }

  function damagePlayer(dmg, reason) {
    S.hp = Math.max(0, S.hp - dmg);
    log(reason + '. <em>' + dmg + '</em>의 피해를 입었다. (HP ' + S.hp + '/' + S.maxHp + ')', 't-hit');
    render();
  }

  function victory() {
    var e = C.enemy;
    var isBoss = C.isBoss;
    C = null;
    renderEnemy();

    S.kills += 1;
    S.gold += e.gold;
    log(josa(e.name, '을를') + ' 쓰러뜨렸다!', 't-good');
    log('<em>' + e.gold + 'G</em>를 얻었다.', 't-gold');
    gainExp(e.exp);

    if (isBoss) {
      S.bossKills += 1;
      S.bossDone = true;
      logGap();
      log('층주가 무너지자 위층으로 가는 문이 열렸다.', 't-good');
      // 층주 보상
      var drop = pick(['potion_l', 'elixir', 'tonic', 'whetstone', 'lucky_coin']);
      invAdd(drop, 1);
      log(D.ITEMS[drop].emoji + ' 전리품 — <em>' + esc(D.ITEMS[drop].name) + '</em>', 't-good');
      save();
      bossCleared();
      return;
    }

    if (S.hp <= 0) { return gameOver('탑 안에서'); }
    save();
    afterRoom();
  }

  function bossCleared() {
    render();
    setChoices([
      { label: '위층으로 오른다', sub: (S.floor + 1) + '층으로', cls: 'primary', onClick: function () {
        S.floor += 1;
        S.room = 0;
        S.roomsInFloor = randInt(3, 4);
        S.bossDone = false;
        var h = Math.round(S.maxHp * .35), m = Math.round(S.maxMp * .35);
        S.hp = clamp(S.hp + h, 0, S.maxHp);
        S.mp = clamp(S.mp + m, 0, S.maxMp);
        save();
        clearLog();
        logTitle(S.floor + '층');
        log('층주를 넘어선 자에게 탑이 잠시 숨을 돌릴 틈을 준다. HP +' + h + ', MP +' + m, 't-good');
        landing();
      } },
      { label: '가방을 연다', disabled: !invList().length, onClick: function () { openInventory(bossCleared); } },
      { label: '저장하고 타이틀로', cls: 'ghost', onClick: function () { save(); screenTitle(); } }
    ]);
  }

  /* --- 경험치 / 레벨업 ------------------------------------------------------ */

  function gainExp(amount, quiet) {
    S.exp += amount;
    if (!quiet) { log('경험치 <em>+' + amount + '</em>', 't-dim'); }

    var leveled = 0;
    while (S.exp >= expNeed(S.level)) {
      S.exp -= expNeed(S.level);
      S.level += 1;
      leveled += 1;
    }
    if (leveled > 0) {
      var before = { hp: S.maxHp, mp: S.maxMp, atk: S.atk, def: S.def };
      recalc();
      S.hp = S.maxHp;
      S.mp = S.maxMp;
      log('레벨 업! <em>Lv.' + S.level + '</em> — 최대 HP +' + (S.maxHp - before.hp) +
          ', MP +' + (S.maxMp - before.mp) + ', 공격 +' + (S.atk - before.atk) +
          ', 방어 +' + (S.def - before.def) + ' · 상처가 모두 아물었다.', 't-levelup');
    }
    render();
  }

  /* --- 인벤토리 화면 -------------------------------------------------------- */

  function openInventory(back, inCombat) {
    render();
    var ids = invList();

    var list = ids.map(function (id) {
      var it = D.ITEMS[id];
      var useless = inCombat && (it.type === 'escape' && C && C.isBoss);
      return {
        label: it.emoji + ' ' + it.name + ' ×' + invCount(id),
        sub: it.desc,
        disabled: !!useless,
        onClick: function () { useItem(id, back, inCombat); }
      };
    });

    if (!list.length) {
      log('가방이 비어 있다.', 't-dim');
    }
    list.push({ label: '← 닫는다', cls: 'ghost', onClick: function () { back(); } });
    setChoices(list);
  }

  function useItem(id, back, inCombat) {
    var it = D.ITEMS[id];

    switch (it.type) {
      case 'heal': {
        if (S.hp >= S.maxHp) { log('이미 상처가 없다.', 't-dim'); return openInventory(back, inCombat); }
        var h = Math.min(it.value, S.maxHp - S.hp);
        S.hp += h;
        invRemove(id);
        log(it.emoji + ' ' + esc(it.name) + josaOf(it.name, '을를') + ' 마셨다. HP <em>+' + h + '</em>', 't-good');
        break;
      }
      case 'mana': {
        if (S.mp >= S.maxMp) { log('마력이 이미 가득하다.', 't-dim'); return openInventory(back, inCombat); }
        var m = Math.min(it.value, S.maxMp - S.mp);
        S.mp += m;
        invRemove(id);
        log(it.emoji + ' ' + esc(it.name) + josaOf(it.name, '을를') + ' 마셨다. MP <em>+' + m + '</em>', 't-good');
        break;
      }
      case 'full':
        invRemove(id);
        S.hp = S.maxHp;
        S.mp = S.maxMp;
        log(it.emoji + ' 엘릭서가 몸을 훑고 지나갔다. HP와 MP가 모두 찼다.', 't-good');
        break;

      case 'buff': {
        invRemove(id);
        if (it.stat === 'maxHp') {
          S.bonus.hp += it.value;
          recalc();
          S.hp = clamp(S.hp + it.value, 0, S.maxHp);
          log(it.emoji + ' 최대 HP가 <em>영구히 +' + it.value + '</em> 올랐다.', 't-good');
        } else {
          S.bonus[it.stat] += it.value;
          recalc();
          var label = { atk: '공격력', def: '방어력', spd: '속도', luk: '행운' }[it.stat] || it.stat;
          log(it.emoji + ' ' + label + josaOf(label, '이가') + ' <em>영구히 +' + it.value + '</em> 올랐다.', 't-good');
        }
        break;
      }

      case 'damage':
        if (!inCombat || !C) { log('지금은 쓸 일이 없다.', 't-dim'); return openInventory(back, inCombat); }
        invRemove(id);
        C.enemy.hp -= it.value;
        log(it.emoji + ' 폭탄이 터지며 ' + esc(C.enemy.name) + '에게' + ' <em>' + it.value + '</em>의 피해!', 't-crit');
        save();
        render();
        if (C.enemy.hp <= 0) { return victory(); }
        return enemyTurn();

      case 'escape':
        if (!inCombat || !C) { log('지금은 쓸 일이 없다.', 't-dim'); return openInventory(back, inCombat); }
        if (C.isBoss) { log('층주 앞에서는 연막도 소용없다.', 't-dim'); return openInventory(back, inCombat); }
        invRemove(id);
        log(it.emoji + ' 연막이 퍼지는 사이 통로 밖으로 빠져나왔다.', 't-dim');
        C = null;
        renderEnemy();
        save();
        return afterRoom();

      default:
        break;
    }

    save();
    render();

    // 전투 중에 회복/강화 아이템을 쓰면 한 턴을 소비합니다.
    if (inCombat && C) { return enemyTurn(); }
    openInventory(back, inCombat);
  }

  /* --- 게임 오버 ----------------------------------------------------------- */

  function gameOver(where) {
    C = null;
    renderEnemy();
    render();

    var cls = classOf(S.classId);
    logGap();
    log('시야가 검게 좁아진다. ' + PN() + '의 도전은 ' + esc(where) + ' 끝났다.', 't-death');

    addRecord({
      name: S.name,
      cls: cls.name,
      level: S.level,
      floor: S.floor,
      kills: S.kills,
      date: new Date().toISOString().slice(0, 10)
    });
    clearSave();

    logTitle('기록');
    log('도달한 층 <em>' + S.floor + '층</em> · 레벨 <em>' + S.level + '</em> · 처치 <em>' + S.kills + '</em>마리 · 층주 <em>' + S.bossKills + '</em>체');

    setChoices([
      { label: '다시 도전한다', cls: 'primary', onClick: screenClass },
      { label: '타이틀로', cls: 'ghost', onClick: screenTitle }
    ]);
  }

  /* --- 시작 ---------------------------------------------------------------- */

  screenTitle();
}());
