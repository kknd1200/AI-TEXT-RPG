/* ============================================================
   UI — HUD / 직업 선택 / 2차 전직 / 스킬 등록 / 도움말
   ============================================================ */
var UI = (function(){
  'use strict';

  var $ = function(id){ return document.getElementById(id); };
  var el = {};
  var cb = {};                       /* main.js 콜백 */
  var pickClass = null, pickJob2 = null, pickSkill = null;
  var slotEls = {}, barSig = '';
  var toastT = 0, lastToast = '';

  var WEAPON_ICON = {
    sword:'⚔️', greatsword:'🗡️', longsword:'⚔️', staff:'🪄',
    bow:'🏹', dagger:'🔪', mace:'🔨', fist:'👊'
  };
  var SLOT_KEYS = ['R', 1, 2, 3, 4];

  function init(callbacks){
    cb = callbacks || {};
    ['hud','statPanel','jobName','lvBadge','hpFill','hpTxt','mpFill','mpTxt','xpFill','xpTxt',
     'buffs','waveTxt','killTxt','skillBar','toast','screenTitle','classList','btnStart',
     'btnContinue','screenJob2','job2List','btnJob2','screenSkills','skillList','slotList',
     'skillDetail','btnCloseSkills','screenDeath','deathInfo','btnRevive','screenHelp',
     'btnCloseHelp','btnReset','screenLoad','loadFill','loadTxt'].forEach(function(id){ el[id] = $(id); });

    buildClassCards();

    el.btnStart.onclick = function(){ if(pickClass && cb.start) cb.start(pickClass); };
    el.btnContinue.onclick = function(){ if(cb.load) cb.load(); };
    el.btnJob2.onclick = function(){
      if(pickJob2 && cb.job2){ cb.job2(pickJob2); hide('screenJob2'); pickJob2 = null; }
    };
    el.btnCloseSkills.onclick = function(){ closeSkills(); };
    el.btnRevive.onclick = function(){ hide('screenDeath'); if(cb.revive) cb.revive(); };
    el.btnCloseHelp.onclick = function(){ hide('screenHelp'); };
    el.btnReset.onclick = function(){
      if(confirm('저장을 지우고 처음부터 시작한다.')) { if(cb.reset) cb.reset(); }
    };
  }

  /* 직업 카드용 초상화. 스프라이트 시트를 애니메이션시킨다. */
  var portraits = [];
  function heroCanvas(art, look, weapon, targetH){
    var c = document.createElement('canvas');
    var sp = Assets.forArt('hero', art);
    if(sp){
      var k = targetH / sp.bh;
      c.width = Math.ceil(sp.bw * k) + 8;
      c.height = Math.ceil(sp.bh * k) + 8;
      var x = c.getContext('2d');
      x.imageSmoothingEnabled = false;
      portraits.push({ cv: c, ctx: x, sp: sp, k: k });
      drawPortrait(portraits[portraits.length-1], 0);
    }else{
      var pt = Sprites.portrait(look, weapon, 2);
      c.width = pt.width; c.height = pt.height;
      c.getContext('2d').drawImage(pt, 0, 0);
    }
    return c;
  }
  function drawPortrait(p, frame){
    var sp = p.sp, x = p.ctx, k = p.k;
    x.clearRect(0, 0, p.cv.width, p.cv.height);
    x.drawImage(sp.img, (frame % sp.frames) * sp.fw, 0, sp.fw, sp.fh,
                Math.round(4 - sp.bx * k), Math.round(4 - sp.by * k),
                Math.round(sp.fw * k), Math.round(sp.fh * k));
  }
  /* main 루프에서 매 프레임 호출 */
  function tickPortraits(ts){
    if(!portraits.length) return;
    for(var i = 0; i < portraits.length; i++){
      var p = portraits[i];
      if(p.sp.frames < 2) continue;
      var f = Math.floor(ts / p.sp.dur) % p.sp.frames;
      if(f !== p.last){ p.last = f; drawPortrait(p, f); }
    }
  }

  function setLoading(v){
    el.loadFill.style.width = Math.round(v * 100) + '%';
    el.loadTxt.textContent = Math.round(v * 100) + '%';
  }
  function hideLoading(){ el.screenLoad.classList.add('hidden'); }

  function show(id){ el[id].classList.remove('hidden'); }
  function hide(id){ el[id].classList.add('hidden'); }
  function isOpen(id){ return !el[id].classList.contains('hidden'); }

  function anyModal(){
    return isOpen('screenTitle') || isOpen('screenJob2') || isOpen('screenSkills') ||
           isOpen('screenDeath') || isOpen('screenHelp');
  }

  /* ---------- 타이틀 / 직업 선택 --------------------------- */
  function buildClassCards(){
    el.classList.innerHTML = '';
    portraits.length = 0;
    Object.keys(CLASS_DB).forEach(function(key){
      var C = CLASS_DB[key];
      var d = document.createElement('div');
      d.className = 'card';
      d.appendChild(heroCanvas(C.art, C.look, C.weapon, 150));
      var b = C.base;
      d.insertAdjacentHTML('beforeend',
        '<div class="nm">' + C.name + '</div>' +
        '<div class="wp">' + WEAPON_DB[C.weapon].name + '</div>' +
        '<div class="ds">' + C.desc + '</div>' +
        '<div class="st">HP ' + b.hp + ' · MP ' + b.mp + ' · 공 ' + b.atk +
        ' · 마 ' + b.matk + ' · 방 ' + b.def + '</div>' +
        '<div class="st">2차: ' + JOB2_CHOICES[key].map(function(j){ return JOB2_DB[j].name; }).join(' / ') + '</div>');
      d.onclick = function(){
        pickClass = key;
        Array.prototype.forEach.call(el.classList.children, function(c){ c.classList.remove('on'); });
        d.classList.add('on');
        el.btnStart.disabled = false;
        el.btnStart.textContent = C.name + '(으)로 시작';
      };
      el.classList.appendChild(d);
    });
  }

  function showTitle(save){
    pickClass = null;
    el.btnStart.disabled = true;
    el.btnStart.textContent = '선택한 직업으로 시작';
    Array.prototype.forEach.call(el.classList.children, function(c){ c.classList.remove('on'); });
    if(save){
      el.btnContinue.classList.remove('hidden');
      var nm = save.job2 ? JOB2_DB[save.job2].name : CLASS_DB[save.cls].name;
      el.btnContinue.textContent = '이어하기 — ' + nm + ' Lv.' + save.level;
    }else{
      el.btnContinue.classList.add('hidden');
    }
    show('screenTitle');
    hide('hud');
  }

  function startGame(){
    hide('screenTitle');
    show('hud');
    barSig = '';
  }

  /* ---------- 2차 전직 ------------------------------------ */
  function showJob2(cls){
    pickJob2 = null;
    el.btnJob2.disabled = true;
    el.job2List.innerHTML = '';
    portraits.length = 0;
    JOB2_CHOICES[cls].forEach(function(id){
      var J = JOB2_DB[id];
      var d = document.createElement('div');
      d.className = 'card';
      d.appendChild(heroCanvas(J.art, J.look, J.weapon, 150));
      var sk = skillsOfJob(id).map(function(s){ return s.icon + ' ' + s.name; }).join(' · ');
      d.insertAdjacentHTML('beforeend',
        '<div class="nm">' + J.name + '</div>' +
        '<div class="wp">' + WEAPON_DB[J.weapon].name + '</div>' +
        '<div class="ds">' + J.desc + '</div>' +
        '<div class="st">' + sk + '</div>');
      d.onclick = function(){
        pickJob2 = id;
        Array.prototype.forEach.call(el.job2List.children, function(c){ c.classList.remove('on'); });
        d.classList.add('on');
        el.btnJob2.disabled = false;
        el.btnJob2.textContent = J.name + '(으)로 전직';
      };
      el.job2List.appendChild(d);
    });
    show('screenJob2');
  }

  /* ---------- 스킬창 -------------------------------------- */
  function openSkills(){
    if(anyModal() && !isOpen('screenSkills')) return;
    pickSkill = null;
    renderSkillList();
    renderSlotList();
    el.skillDetail.innerHTML = '스킬을 선택하면 설명이 표시된다.';
    show('screenSkills');
  }
  function closeSkills(){ hide('screenSkills'); barSig = ''; }
  function toggleSkills(){ isOpen('screenSkills') ? closeSkills() : openSkills(); }

  function boundKeyOf(p, id){
    for(var k in p.slots) if(p.slots[k] === id) return k === 'R' ? '우클릭' : k;
    return '';
  }

  function renderSkillList(){
    var p = Engine.state.player;
    var list = Engine.learned(p);
    el.skillList.innerHTML = '';
    if(!list.length){ el.skillList.innerHTML = '<div class="sub">아직 배운 스킬이 없다.</div>'; return; }
    list.forEach(function(s){
      var d = document.createElement('div');
      d.className = 'skRow' + (pickSkill === s.id ? ' on' : '');
      var bk = boundKeyOf(p, s.id);
      d.innerHTML = '<span class="ic">' + s.icon + '</span>' +
        '<span class="tx"><span class="nm">' + s.name + '</span>' +
        '<span class="mt">Lv.' + s.lv + ' · MP ' + s.mp + ' · ' + s.cd + '초</span></span>' +
        (bk ? '<span class="bd">[' + bk + ']</span>' : '');
      d.onclick = function(){
        pickSkill = s.id;
        renderSkillList();
        showDetail(s);
      };
      el.skillList.appendChild(d);
    });
  }

  var TYPE_NAME = {
    arc:'근접 부채꼴', proj:'투사체', nova:'자기중심 광역', ground:'지정 지점 광역',
    dash:'돌진/순간이동', beam:'관통 직선', chain:'연쇄', buff:'자기 강화',
    heal:'즉시 회복', aura:'지속 장판'
  };

  function showDetail(s){
    var extra = [];
    if(s.coef) extra.push((s.base === 'matk' ? '마력' : '공격력') + ' × ' + s.coef);
    if(s.hits) extra.push(s.hits + '연타');
    if(s.count) extra.push(s.count + '발');
    if(s.dot) extra.push('지속피해 ' + s.dot.dur + '초');
    if(s.slow) extra.push('둔화 ' + Math.round(s.slow.amt*100) + '%');
    if(s.freeze) extra.push('빙결 ' + s.freeze + '초');
    if(s.stun) extra.push('기절 ' + s.stun + '초');
    if(s.lifesteal) extra.push('흡혈 ' + Math.round(s.lifesteal*100) + '%');
    el.skillDetail.innerHTML =
      '<b>' + s.icon + ' ' + s.name + '</b><br>' +
      '<span class="mt">' + TYPE_NAME[s.type] + ' · MP ' + s.mp + ' · 쿨 ' + s.cd + '초</span><br>' +
      s.desc + (extra.length ? '<br><span class="mt">' + extra.join(' · ') + '</span>' : '');
  }

  function renderSlotList(){
    var p = Engine.state.player;
    el.slotList.innerHTML = '';
    SLOT_KEYS.forEach(function(k){
      var id = p.slots[k], s = id ? SKILL_BY_ID[id] : null;
      var b = document.createElement('button');
      b.className = 'slotBtn';
      b.innerHTML = '<span class="key">' + (k === 'R' ? 'RMB' : k) + '</span>' +
        (s ? s.icon + '<span class="nm">' + s.name + '</span>' : '<span style="opacity:.35">＋</span>');
      b.onclick = function(){
        if(!pickSkill){ el.skillDetail.innerHTML = '먼저 왼쪽에서 스킬을 선택한다.'; return; }
        Engine.bindSkill(k, pickSkill);
        renderSkillList();
        renderSlotList();
        barSig = '';
        if(cb.save) cb.save();
      };
      el.slotList.appendChild(b);
    });
  }

  /* ---------- 사망 / 도움말 ------------------------------- */
  function showDeath(W){
    el.deathInfo.textContent = '웨이브 ' + W.wave + ' · 처치 ' + W.player.kills +
      ' — 부활하면 경험치 10%를 잃고 이전 웨이브부터 다시 시작한다.';
    show('screenDeath');
  }
  function toggleHelp(){
    if(isOpen('screenHelp')) hide('screenHelp');
    else if(isOpen('screenSkills')) closeSkills();
    else if(!isOpen('screenTitle') && !isOpen('screenJob2') && !isOpen('screenDeath')) show('screenHelp');
  }

  /* ---------- HUD 갱신 ------------------------------------ */
  function buildBar(p){
    el.skillBar.innerHTML = '';
    slotEls = {};
    /* 기본공격 */
    var w = Engine.weaponOf(p);
    var basic = document.createElement('div');
    basic.className = 'slot ready';
    basic.innerHTML = '<span class="key">LMB</span>' + (WEAPON_ICON[w] || '⚔️') +
      '<span class="nm">' + WEAPON_DB[w].name + '</span>';
    el.skillBar.appendChild(basic);

    SLOT_KEYS.forEach(function(k){
      var id = p.slots[k], s = id ? SKILL_BY_ID[id] : null;
      var d = document.createElement('div');
      d.className = 'slot' + (s ? '' : ' empty');
      d.innerHTML = '<span class="key">' + (k === 'R' ? 'RMB' : k) + '</span>' +
        (s ? s.icon + '<span class="cost">' + s.mp + '</span>' +
             '<span class="nm">' + s.name + '</span>' +
             '<span class="cdMask"></span><span class="cdNum"></span>' : '');
      d.onclick = function(){ openSkills(); };
      el.skillBar.appendChild(d);
      slotEls[k] = d;
    });
  }

  function update(W, dt){
    var p = W.player;
    /* 스킬바 재구성이 필요한지 */
    var sig = Engine.jobOf(p) + '|' + SLOT_KEYS.map(function(k){ return p.slots[k]; }).join(',');
    if(sig !== barSig){ barSig = sig; buildBar(p); }

    el.jobName.textContent = Engine.jobName(p);
    el.lvBadge.textContent = 'Lv.' + p.level + (p.level >= JOB2_LEVEL && !p.job2 ? ' ★전직가능' : '');

    var hpP = Math.max(0, p.hp / p.max.hp) * 100;
    el.hpFill.style.width = hpP + '%';
    el.hpTxt.textContent = Math.ceil(p.hp) + ' / ' + p.max.hp + (p.shield > 0 ? ' (+' + Math.round(p.shield) + ')' : '');
    el.mpFill.style.width = Math.max(0, p.mp / p.max.mp) * 100 + '%';
    el.mpTxt.textContent = Math.floor(p.mp) + ' / ' + p.max.mp;

    if(p.level >= MAX_LEVEL){
      el.xpFill.style.width = '100%';
      el.xpTxt.textContent = 'MAX';
    }else{
      var need = xpNeed(p.level);
      el.xpFill.style.width = Math.min(100, p.xp / need * 100) + '%';
      el.xpTxt.textContent = Math.floor(p.xp) + ' / ' + need;
    }

    /* 버프 */
    var bh = p.buffs.map(function(b){
      return '<div class="buffIcon" title="' + b.name + '">' + b.icon + '<b>' + Math.ceil(b.t) + '</b></div>';
    }).join('');
    if(el.buffs.dataset.h !== bh){ el.buffs.innerHTML = bh; el.buffs.dataset.h = bh; }

    el.waveTxt.textContent = 'WAVE ' + Math.max(1, W.wave) +
      (W.waveState === 'ready' ? ' 대기 ' + Math.ceil(W.waveT) : '');
    var alive = W.mobs.length + W.spawnQueue.length;
    el.killTxt.textContent = '처치 ' + p.kills + (alive ? ' · 남은 적 ' + alive : '');

    /* 쿨다운 */
    SLOT_KEYS.forEach(function(k){
      var d = slotEls[k];
      if(!d) return;
      var id = p.slots[k];
      if(!id) return;
      var s = SKILL_BY_ID[id], cd = p.cds[id] || 0;
      var mask = d.querySelector('.cdMask'), num = d.querySelector('.cdNum');
      if(cd > 0){
        mask.style.height = Math.min(100, cd / s.cd * 100) + '%';
        num.textContent = cd >= 1 ? Math.ceil(cd) : cd.toFixed(1);
      }else{
        mask.style.height = '0%';
        num.textContent = '';
      }
      var ok = cd <= 0 && p.mp >= s.mp;
      d.className = 'slot' + (ok ? ' ready' : (p.mp < s.mp ? ' noMp' : ''));
    });

    /* 토스트 */
    if(W.msg && W.msg !== lastToast){
      lastToast = W.msg;
      el.toast.textContent = W.msg;
      el.toast.classList.add('show');
      toastT = 1.6;
    }
    if(toastT > 0){
      toastT -= dt;
      if(toastT <= 0){ el.toast.classList.remove('show'); lastToast = ''; }
    }
  }

  return {
    init: init, showTitle: showTitle, startGame: startGame, showJob2: showJob2,
    openSkills: openSkills, closeSkills: closeSkills, toggleSkills: toggleSkills,
    showDeath: showDeath, toggleHelp: toggleHelp, update: update,
    setLoading: setLoading, hideLoading: hideLoading, tickPortraits: tickPortraits,
    buildClassCards: buildClassCards,
    anyModal: anyModal, isOpen: isOpen, hide: hide
  };
})();
