/* ============================================================
   도형 스프라이트 생성기 — 바닥 타일과 지형지물을 코드로 그려 구워둔다.
   캐릭터/몬스터는 assets/ 의 픽셀아트를 쓰지만, 에셋을 불러오지 못한
   환경(file:// 로 연 경우 등)에서는 여기 있는 도형 캐릭터로 대체된다.
   아트 그리드 1칸 = 렌더 픽셀 PS칸 (기본 2) → 확대해도 픽셀이 유지된다.
   ============================================================ */
var Sprites = (function(){
  'use strict';

  var PS = 2;                 /* 아트 픽셀 크기 */
  var CW = 22, CH = 27;       /* 캐릭터 아트 그리드 (가로/세로) */
  var cache = {};

  function mk(w, h){
    var c = document.createElement('canvas');
    c.width = w; c.height = h;
    var x = c.getContext('2d');
    x.imageSmoothingEnabled = false;
    return c;
  }

  /* 아트 좌표 기준 사각형 */
  function px(x, ax, ay, w, h, col){
    if(!col) return;
    x.fillStyle = col;
    x.fillRect(ax*PS, ay*PS, w*PS, h*PS);
  }

  /* 아트 좌표 기준 선 (브레젠험) */
  function pxLine(x, x0, y0, x1, y1, col, th){
    th = th || 1;
    x0 = Math.round(x0); y0 = Math.round(y0); x1 = Math.round(x1); y1 = Math.round(y1);
    var dx = Math.abs(x1-x0), sx = x0<x1?1:-1;
    var dy = -Math.abs(y1-y0), sy = y0<y1?1:-1;
    var err = dx+dy, e2, guard = 0;
    while(guard++ < 200){
      px(x, x0, y0, th, th, col);
      if(x0===x1 && y0===y1) break;
      e2 = 2*err;
      if(e2 >= dy){ err += dy; x0 += sx; }
      if(e2 <= dx){ err += dx; y0 += sy; }
    }
  }

  function shade(col, amt){
    var m = /^#([0-9a-f]{6})$/i.exec(col || '#000000');
    if(!m) return col;
    var n = parseInt(m[1], 16);
    var r = Math.max(0, Math.min(255, ((n>>16)&255) + amt));
    var g = Math.max(0, Math.min(255, ((n>>8)&255) + amt));
    var b = Math.max(0, Math.min(255, (n&255) + amt));
    return 'rgb('+r+','+g+','+b+')';
  }

  /* ---------- 무기 ---------------------------------------- */
  /* hx,hy = 손 위치(아트좌표), ang = 라디안(0 = 오른쪽, 아래가 +) */
  function drawWeapon(x, weapon, hx, hy, ang, el, flip){
    var dx = Math.cos(ang), dy = Math.sin(ang);
    var tip, mid;
    switch(weapon){
      case 'sword':
        tip = [hx+dx*9, hy+dy*9];
        pxLine(x, hx, hy, tip[0], tip[1], '#e6ecf5', 1);
        pxLine(x, hx+dx, hy+dy, tip[0]-dx, tip[1]-dy, '#aab6c6', 1);
        px(x, Math.round(hx-dy), Math.round(hy+dx), 1, 1, '#e0c063');
        px(x, Math.round(hx+dy), Math.round(hy-dx), 1, 1, '#e0c063');
        break;
      case 'greatsword':
        tip = [hx+dx*14, hy+dy*14];
        pxLine(x, hx, hy, tip[0], tip[1], '#dfe6ef', 2);
        pxLine(x, hx+dx*2, hy+dy*2, tip[0], tip[1], '#f6f9ff', 1);
        pxLine(x, hx-dy*2, hy+dx*2, hx+dy*2, hy-dx*2, '#c07a3a', 1);
        break;
      case 'longsword':
        tip = [hx+dx*11, hy+dy*11];
        pxLine(x, hx, hy, tip[0], tip[1], '#cfe0ff', 1);
        pxLine(x, hx+dx*3, hy+dy*3, tip[0], tip[1], '#8fb6ff', 1);
        px(x, Math.round(hx-dy), Math.round(hy+dx), 1, 1, '#a8e0ff');
        break;
      case 'dagger':
        tip = [hx+dx*5, hy+dy*5];
        pxLine(x, hx, hy, tip[0], tip[1], '#d8f0c8', 1);
        px(x, Math.round(tip[0]), Math.round(tip[1]), 1, 1, '#8ce35b');
        break;
      case 'staff':
        tip = [hx+dx*12, hy+dy*12];
        pxLine(x, hx-dx*3, hy-dy*3, tip[0], tip[1], '#8a6a3a', 1);
        px(x, Math.round(tip[0]-1), Math.round(tip[1]-1), 3, 3, el || '#c79bff');
        px(x, Math.round(tip[0]), Math.round(tip[1]), 1, 1, '#ffffff');
        break;
      case 'mace':
        tip = [hx+dx*8, hy+dy*8];
        pxLine(x, hx, hy, tip[0], tip[1], '#9a8a6a', 1);
        px(x, Math.round(tip[0]-1), Math.round(tip[1]-1), 3, 3, '#c0c4cc');
        px(x, Math.round(tip[0]), Math.round(tip[1]-1), 1, 1, '#f0f4ff');
        break;
      case 'bow':
        /* 활대는 조준 방향과 수직으로 세운다 */
        mid = [hx+dx*2, hy+dy*2];
        var nx = -dy, ny = dx;
        pxLine(x, mid[0]+nx*6, mid[1]+ny*6, mid[0]+dx*3, mid[1]+dy*3, '#8a5a2a', 1);
        pxLine(x, mid[0]+dx*3, mid[1]+dy*3, mid[0]-nx*6, mid[1]-ny*6, '#8a5a2a', 1);
        pxLine(x, mid[0]+nx*6, mid[1]+ny*6, mid[0]-nx*6, mid[1]-ny*6, '#e8e0c8', 1);
        pxLine(x, mid[0]-dx*2, mid[1]-dy*2, mid[0]+dx*7, mid[1]+dy*7, '#d8d0b8', 1);   /* 화살 */
        break;
      case 'fist':
        px(x, Math.round(hx-1), Math.round(hy-1), 3, 3, '#e8a068');
        px(x, Math.round(hx), Math.round(hy), 1, 1, '#fff0d8');
        break;
    }
  }

  /* ---------- 인간형 캐릭터 -------------------------------- */
  /* dir: 's'(정면) 'n'(뒤) 'e'(옆) / anim: 'idle' 'walk' 'atk' */
  function drawHumanoid(x, look, weapon, dir, anim, f, elCol){
    var L = look || {};
    var skin = L.skin || '#f0c49b', hair = L.hair || '#3a2a1a';
    var main = L.main || '#5f7fa8', sub = L.sub || '#c9d6e6';
    var trim = L.trim || '#e0c063', cape = L.cape;
    var cx = 11;                       /* 몸 중심 */
    var bob = (anim === 'walk' && (f === 1 || f === 3)) ? -1 : 0;
    var legA = 0, legB = 0;
    if(anim === 'walk'){
      if(f === 1){ legA = -1; legB = 1; }
      else if(f === 3){ legA = 1; legB = -1; }
    }
    var top = 2 + bob;

    /* 망토 (몸 뒤) */
    if(cape){
      px(x, cx-5, top+7, 10, 10, shade(cape, -14));
      px(x, cx-4, top+16, 8, 2, shade(cape, -30));
    }

    /* 다리 */
    px(x, cx-4, top+15+legA, 3, 6, shade(sub, -40));
    px(x, cx+1, top+15+legB, 3, 6, shade(sub, -40));
    px(x, cx-4, top+20+legA, 3, 2, '#2f2a26');
    px(x, cx+1, top+20+legB, 3, 2, '#2f2a26');

    /* 몸통 */
    px(x, cx-4, top+7, 8, 9, main);
    px(x, cx-4, top+7, 8, 2, shade(main, 26));      /* 어깨 하이라이트 */
    px(x, cx-4, top+13, 8, 2, trim);                /* 벨트 */
    px(x, cx-5, top+7, 1, 5, sub);                  /* 어깨 패드 */
    px(x, cx+4, top+7, 1, 5, sub);

    /* 팔 */
    var armSwing = 0;
    if(anim === 'walk') armSwing = (f === 1 ? 1 : f === 3 ? -1 : 0);
    px(x, cx-6, top+8+armSwing, 2, 6, sub);
    px(x, cx+4, top+8-armSwing, 2, 6, sub);
    px(x, cx-6, top+13+armSwing, 2, 2, skin);
    px(x, cx+4, top+13-armSwing, 2, 2, skin);

    /* 머리 */
    px(x, cx-3, top+1, 7, 7, skin);
    px(x, cx-3, top, 7, 3, hair);
    px(x, cx-4, top+1, 1, 4, hair);
    px(x, cx+4, top+1, 1, 4, hair);
    if(dir === 's'){
      px(x, cx-2, top+4, 1, 1, '#20242c');
      px(x, cx+1, top+4, 1, 1, '#20242c');
      px(x, cx-1, top+6, 3, 1, shade(skin, -50));
    }else if(dir === 'n'){
      px(x, cx-3, top+1, 7, 5, hair);               /* 뒤통수 */
    }else{
      px(x, cx+1, top+4, 1, 1, '#20242c');
      px(x, cx+3, top+3, 1, 3, skin);               /* 코 */
    }

    /* 무기 각도 — 지팡이·활은 들고 있는 자세가 따로 있다 */
    var ang;
    if(weapon === 'staff') ang = (anim === 'atk') ? (f === 0 ? -1.35 : -0.6) : -1.15;
    else if(weapon === 'bow') ang = (anim === 'atk') ? -0.12 : -0.38;
    else if(anim === 'atk') ang = (f === 0 ? -0.95 : 0.55);
    else ang = (anim === 'walk' && f === 1) ? 0.95 : 0.8;
    var hx = cx + 5, hy = top + 13;
    if(dir === 'n'){ hx = cx - 5; ang = Math.PI - ang; }
    drawWeapon(x, weapon, hx, hy, ang, elCol);
  }

  /* ---------- 몬스터 몸체 --------------------------------- */
  function drawBlob(x, look, anim, f){
    var main = look.main || '#6fd06a', sub = look.sub || '#2f8a3a';
    var sq = (anim === 'walk' && (f === 1 || f === 3)) ? 1 : 0;
    var cx = 11, base = 22;
    var h = 9 - sq, w = 12 + sq*2;
    px(x, cx-w/2, base-h, w, h, main);
    px(x, cx-w/2+1, base-h-2, w-2, 3, main);
    px(x, cx-w/2+2, base-h-1, 4, 2, shade(main, 45));
    px(x, cx-w/2, base-2, w, 2, sub);
    px(x, cx-3, base-h+2, 2, 2, look.eye || '#123');
    px(x, cx+1, base-h+2, 2, 2, look.eye || '#123');
  }

  function drawFlyer(x, look, anim, f){
    var main = look.main || '#8a5ac0', sub = look.sub || '#4a2a70';
    var cx = 11, cy = 11 + ((f % 2) ? -1 : 0);
    var flap = (f % 2) ? 3 : 1;
    /* 날개 */
    pxLine(x, cx-3, cy, cx-9, cy-flap, sub, 2);
    pxLine(x, cx+3, cy, cx+9, cy-flap, sub, 2);
    pxLine(x, cx-9, cy-flap, cx-6, cy+3, sub, 1);
    pxLine(x, cx+9, cy-flap, cx+6, cy+3, sub, 1);
    /* 몸통 */
    px(x, cx-3, cy-2, 6, 8, main);
    px(x, cx-2, cy-5, 4, 4, main);
    px(x, cx-2, cy-4, 1, 1, look.eye || '#ff5');
    px(x, cx+1, cy-4, 1, 1, look.eye || '#ff5');
    px(x, cx-3, cy-7, 1, 2, shade(main, -40));
    px(x, cx+2, cy-7, 1, 2, shade(main, -40));
  }

  function drawGolem(x, look, anim, f){
    var main = look.main || '#8a8a92', sub = look.sub || '#5a5a66';
    var step = (anim === 'walk' && (f === 1 || f === 3)) ? 1 : 0;
    var cx = 11, top = 3;
    px(x, cx-5, top+16+step, 4, 6, sub);
    px(x, cx+1, top+16-step, 4, 6, sub);
    px(x, cx-6, top+5, 12, 12, main);
    px(x, cx-6, top+5, 12, 3, shade(main, 30));
    px(x, cx-8, top+6, 2, 8, sub);
    px(x, cx+6, top+6, 2, 8, sub);
    px(x, cx-3, top, 6, 6, shade(main, 12));
    px(x, cx-2, top+2, 2, 2, look.eye || '#ff8a3a');
    px(x, cx+1, top+2, 2, 2, look.eye || '#ff8a3a');
    px(x, cx-4, top+9, 3, 3, shade(main, -34));   /* 균열 */
    px(x, cx+2, top+12, 2, 2, shade(main, -34));
  }

  /* ---------- 공개 API ------------------------------------ */
  function bake(key, w, h, fn){
    if(cache[key]) return cache[key];
    var c = mk(w, h), x = c.getContext('2d');
    fn(x);
    cache[key] = c;
    return c;
  }

  /* 캐릭터 스프라이트: 좌우 반전은 렌더러가 처리한다 */
  function unit(look, weapon, body, dir, anim, f, elCol){
    var key = [body, weapon, dir, anim, f, elCol,
               look.skin, look.hair, look.main, look.sub, look.trim, look.cape, look.eye].join('|');
    return bake(key, CW*PS, CH*PS, function(x){
      if(body === 'blob') drawBlob(x, look, anim, f);
      else if(body === 'flyer') drawFlyer(x, look, anim, f);
      else if(body === 'golem') drawGolem(x, look, anim, f);
      else drawHumanoid(x, look, weapon, dir, anim, f, elCol);
    });
  }

  /* 초상화 (직업 선택 UI용) — 크게 확대해서 그린다 */
  function portrait(look, weapon, scale){
    var s = scale || 3;
    var key = 'pt|' + s + '|' + weapon + '|' + [look.skin,look.hair,look.main,look.sub,look.trim,look.cape].join(',');
    return bake(key, CW*PS*s, CH*PS*s, function(x){
      var tmp = unit(look, weapon, 'humanoid', 's', 'idle', 0);
      x.imageSmoothingEnabled = false;
      x.drawImage(tmp, 0, 0, CW*PS*s, CH*PS*s);
    });
  }

  /* ---------- 바닥 타일 ----------------------------------- */
  var TW = 128, TH = 64;

  function diamond(x, col){
    x.fillStyle = col;
    x.beginPath();
    x.moveTo(TW/2, 0); x.lineTo(TW, TH/2); x.lineTo(TW/2, TH); x.lineTo(0, TH/2);
    x.closePath(); x.fill();
  }

  /* 결정적 난수 — 같은 타일은 항상 같은 무늬 */
  function rnd(seed){
    var t = seed * 16807 % 2147483647;
    return (t < 0 ? t + 2147483647 : t) / 2147483647;
  }

  function tile(kind, v){
    var key = 'tile|' + kind + '|' + v;
    return bake(key, TW, TH, function(x){
      var base, dot, dot2;
      if(kind === 'stone'){ base = '#6a6a72'; dot = '#7a7a84'; dot2 = '#565660'; }
      else if(kind === 'dirt'){ base = '#7a5f42'; dot = '#8c6f4e'; dot2 = '#654c34'; }
      else if(kind === 'dark'){ base = '#3a4a3a'; dot = '#46583f'; dot2 = '#2e3c2e'; }
      else { base = '#4e7a42'; dot = '#5d8c4c'; dot2 = '#436b3a'; }
      diamond(x, base);
      /* 타일 무늬 */
      var i, n = 26, s = v * 97 + 13;
      for(i = 0; i < n; i++){
        var a = rnd(s + i*7), b = rnd(s + i*13);
        var ty = Math.floor(b * (TH-8)) + 4;
        var half = (1 - Math.abs(ty - TH/2) / (TH/2)) * (TW/2) - 6;
        var tx = Math.floor(TW/2 + (a*2-1) * half);
        x.fillStyle = (i % 3 === 0) ? dot2 : dot;
        x.fillRect(tx, ty, 4, 4);
      }
      /* 타일 경계 */
      x.strokeStyle = 'rgba(0,0,0,0.16)';
      x.lineWidth = 1;
      x.beginPath();
      x.moveTo(TW/2, 0.5); x.lineTo(TW-0.5, TH/2); x.lineTo(TW/2, TH-0.5); x.lineTo(0.5, TH/2);
      x.closePath(); x.stroke();
    });
  }

  /* ---------- 지형지물 ------------------------------------ */
  function prop(kind){
    var key = 'prop|' + kind;
    if(kind === 'tree'){
      return bake(key, 60, 96, function(x){
        px(x, 12, 26, 5, 16, '#4a3220');                /* 줄기 */
        px(x, 13, 26, 2, 16, '#6b4a2c');
        px(x, 11, 40, 7, 2, '#3a2818');
        px(x, 5, 12, 19, 15, '#2b5f30');                /* 잎 아래단 */
        px(x, 7, 7, 15, 8, '#356e37');
        px(x, 9, 3, 11, 6, '#3f8340');
        px(x, 11, 1, 7, 4, '#4b9647');
        px(x, 8, 9, 4, 3, '#5aa851');                   /* 하이라이트 */
        px(x, 15, 5, 3, 2, '#5aa851');
        px(x, 6, 18, 4, 3, '#20492a');                  /* 그늘 */
        px(x, 17, 20, 5, 3, '#20492a');
      });
    }
    if(kind === 'rock'){
      return bake(key, 56, 48, function(x){
        px(x, 4, 12, 18, 8, '#6f6f78');
        px(x, 6, 8, 13, 5, '#82828c');
        px(x, 8, 9, 6, 2, '#9a9aa4');
        px(x, 4, 19, 18, 3, '#4e4e58');
        px(x, 10, 13, 3, 4, '#5c5c66');
      });
    }
    if(kind === 'bush'){
      return bake(key, 48, 40, function(x){
        px(x, 4, 10, 15, 8, '#2f6134');
        px(x, 6, 7, 11, 4, '#3a7a3c');
        px(x, 8, 8, 4, 2, '#4c9349');
        px(x, 4, 17, 15, 2, '#20492a');
      });
    }
    if(kind === 'crystal'){
      return bake(key, 48, 72, function(x){
        px(x, 10, 8, 4, 18, '#5aa8d8');
        px(x, 9, 12, 6, 12, '#7fd8ff');
        px(x, 11, 4, 2, 9, '#d8f4ff');
        px(x, 15, 16, 3, 9, '#4a90c0');
        px(x, 7, 19, 2, 6, '#4a90c0');
        px(x, 7, 25, 10, 2, 'rgba(0,0,0,0.3)');
      });
    }
    /* torch */
    return bake(key, 36, 64, function(x){
      px(x, 8, 12, 3, 16, '#5a3a20');
      px(x, 9, 12, 1, 16, '#7a5230');
      px(x, 7, 6, 5, 6, '#ff8a2a');
      px(x, 8, 3, 3, 5, '#ffc23a');
      px(x, 9, 2, 1, 3, '#fff0a0');
      px(x, 6, 27, 7, 2, 'rgba(0,0,0,0.3)');
    });
  }

  return {
    PS: PS, CW: CW, CH: CH, TW: TW, TH: TH,
    unit: unit, portrait: portrait, tile: tile, prop: prop, shade: shade
  };
})();
