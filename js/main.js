/* ============================================================
   진입점 — 루프 / 저장 / 입력 연결
   ============================================================ */
(function(){
  'use strict';

  var SAVE_KEY = 'qvrpg.save.v1';
  var canvas = document.getElementById('game');
  var started = false, paused = false;
  var last = 0, saveT = 0;

  Render.init(canvas);
  Input.init(canvas);

  /* ---------- 저장 ---------------------------------------- */
  function readSave(){
    try{
      var raw = localStorage.getItem(SAVE_KEY);
      if(!raw) return null;
      var d = JSON.parse(raw);
      if(!d || !CLASS_DB[d.cls]) return null;
      return d;
    }catch(e){ return null; }
  }

  function save(){
    if(!started) return;
    var p = Engine.state.player;
    try{
      localStorage.setItem(SAVE_KEY, JSON.stringify({
        cls: p.cls, job2: p.job2, level: p.level, xp: p.xp,
        kills: p.kills, wave: Engine.state.wave, slots: p.slots
      }));
    }catch(e){ /* 저장 불가 환경은 무시 */ }
  }

  /* ---------- 시작 ---------------------------------------- */
  function begin(cls, data){
    Engine.init(cls);
    if(data) Engine.loadPlayer(data);
    Engine.state.onJob2 = function(){ UI.showJob2(Engine.state.player.cls); };
    started = true; paused = false;
    Input.clearKeys();
    UI.startGame();
    save();
  }

  UI.init({
    start: function(cls){ begin(cls, null); },
    load: function(){ var d = readSave(); if(d) begin(d.cls, d); },
    job2: function(id){ Engine.chooseJob2(id); save(); },
    revive: function(){ Engine.revive(); save(); },
    save: save,
    reset: function(){
      try{ localStorage.removeItem(SAVE_KEY); }catch(e){}
      started = false;
      UI.hide('screenHelp');
      UI.showTitle(null);
    }
  });

  UI.showTitle(readSave());

  /* ---------- 조준 지점 ------------------------------------ */
  function aimPoint(){
    var m = Input.mouse;
    var w = Render.screenToWorld(m.x, m.y);
    var p = Engine.state.player;
    if(!m.inside){    /* 마우스가 밖이면 바라보던 방향 유지 */
      return { x: p.x + Math.cos(p.aim) * 120, y: p.y + Math.sin(p.aim) * 120 };
    }
    return w;
  }

  /* 우클릭 슬롯이 지정형이면 착탄 예상 원을 보여준다 */
  function previewOf(aim){
    var p = Engine.state.player;
    var id = p.slots.R;
    if(!id) return null;
    var s = SKILL_BY_ID[id];
    if(!s || (s.type !== 'ground')) return null;
    var dx = aim.x - p.x, dy = aim.y - p.y;
    var d = Math.sqrt(dx*dx + dy*dy), max = s.castRange || 260;
    var x = aim.x, y = aim.y;
    if(d > max){ var a = Math.atan2(dy, dx); x = p.x + Math.cos(a)*max; y = p.y + Math.sin(a)*max; }
    return { x: x, y: y, r: s.radius || 60, col: EL_COLOR[s.el] || '#fff' };
  }

  /* ---------- 루프 ---------------------------------------- */
  function frame(ts){
    requestAnimationFrame(frame);
    if(!last) last = ts;
    var dt = Math.min(0.05, (ts - last) / 1000);
    last = ts;
    if(!started) return;

    var W = Engine.state, p = W.player;

    /* 창 토글 */
    if(Input.hit('k')) UI.toggleSkills();
    if(Input.hit('escape')) UI.toggleHelp();
    if(Input.hit('p') && !UI.anyModal()){
      paused = !paused;
      Engine.say(paused ? '일시정지 (P)' : '재개', 1.2);
    }

    /* 40레벨인데 아직 전직하지 않았다면(저장 불러오기 포함) 항상 전직창을 띄운다 */
    if(p.level >= JOB2_LEVEL && !p.job2 && !UI.anyModal()) UI.showJob2(p.cls);

    var blocked = UI.anyModal() || paused;
    var aim = aimPoint();

    if(!blocked){
      var wantSkills = [];
      if(Input.mouse.right) wantSkills.push('R');
      if(Input.down('1')) wantSkills.push(1);
      if(Input.down('2')) wantSkills.push(2);
      if(Input.down('3')) wantSkills.push(3);
      if(Input.down('4')) wantSkills.push(4);
      Engine.update(dt, aim, Input.mouse.left, wantSkills);

      saveT -= dt;
      if(saveT <= 0){ saveT = 10; save(); }
      if(p.dead && !UI.isOpen('screenDeath')) UI.showDeath(W);
    }

    Render.draw(W, { aim: aim, preview: blocked ? null : previewOf(aim) });
    UI.update(W, dt);
    Input.endFrame();
  }
  requestAnimationFrame(frame);

  window.addEventListener('beforeunload', save);
})();
