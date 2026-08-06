/* ============================================================
   입력 — WASD 이동 / 좌클릭 기본공격 / 우클릭 지정 스킬 / 1~4 스킬
   ============================================================ */
var Input = (function(){
  'use strict';

  var keys = {};          /* 눌린 상태 */
  var pressed = {};       /* 이번 프레임에 새로 눌림 */
  var mouse = { x: 0, y: 0, left: false, right: false, leftHit: false, rightHit: false, inside: false };
  var canvas = null;

  function norm(e){
    var k = e.key;
    if(k === ' ') return 'space';
    if(k && k.length === 1) return k.toLowerCase();
    return (k || '').toLowerCase();
  }

  function init(cv){
    canvas = cv;
    window.addEventListener('keydown', function(e){
      var k = norm(e);
      /* 게임 조작키는 브라우저 기본동작을 막는다 */
      if(['w','a','s','d','1','2','3','4','space','k','escape','tab'].indexOf(k) >= 0) e.preventDefault();
      if(!keys[k]) pressed[k] = true;
      keys[k] = true;
    });
    window.addEventListener('keyup', function(e){ keys[norm(e)] = false; });
    window.addEventListener('blur', function(){ keys = {}; mouse.left = mouse.right = false; });

    canvas.addEventListener('contextmenu', function(e){ e.preventDefault(); });
    canvas.addEventListener('mousemove', function(e){ setPos(e); });
    canvas.addEventListener('mouseenter', function(){ mouse.inside = true; });
    canvas.addEventListener('mouseleave', function(){ mouse.inside = false; mouse.left = mouse.right = false; });
    canvas.addEventListener('mousedown', function(e){
      e.preventDefault(); setPos(e);
      if(e.button === 0){ mouse.left = true; mouse.leftHit = true; }
      if(e.button === 2){ mouse.right = true; mouse.rightHit = true; }
    });
    window.addEventListener('mouseup', function(e){
      if(e.button === 0) mouse.left = false;
      if(e.button === 2) mouse.right = false;
    });
  }

  /* CSS 좌표 → 캔버스 내부(렌더) 좌표 */
  function setPos(e){
    var r = canvas.getBoundingClientRect();
    if(!r.width || !r.height) return;
    mouse.x = (e.clientX - r.left) * (canvas.width / r.width);
    mouse.y = (e.clientY - r.top) * (canvas.height / r.height);
    mouse.inside = true;
  }

  /* 프레임 끝에서 1회성 플래그 정리 */
  function endFrame(){
    pressed = {};
    mouse.leftHit = false;
    mouse.rightHit = false;
  }

  function moveVector(){
    var mx = 0, my = 0;
    if(keys['w']) my -= 1;
    if(keys['s']) my += 1;
    if(keys['a']) mx -= 1;
    if(keys['d']) mx += 1;
    return { x: mx, y: my };
  }

  return {
    init: init,
    endFrame: endFrame,
    moveVector: moveVector,
    down: function(k){ return !!keys[k]; },
    hit: function(k){ return !!pressed[k]; },
    mouse: mouse,
    clearKeys: function(){ keys = {}; pressed = {}; }
  };
})();
