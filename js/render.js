/* ============================================================
   아이소메트릭(쿼터뷰) 렌더러
   월드(wx,wy) → 화면(sx,sy):  sx = wx - wy,  sy = (wx + wy) / 2
   캔버스 transform(1, .5, -1, .5, ox, oy) 이 그대로 이 변환이라,
   원·부채꼴 같은 이펙트는 월드 좌표로 그리면 알아서 마름모로 눕는다.
   ============================================================ */
var Render = (function(){
  'use strict';

  var cv, ctx, VW = 0, VH = 0;
  var SCALE = 1;               /* CSS 픽셀 → 렌더 픽셀. 아트를 원본 크기로 그린다 */
  var cam = { x: 0, y: 0 };
  var ox = 0, oy = 0;
  var SP = Sprites;

  function init(canvas){
    cv = canvas;
    ctx = cv.getContext('2d');
    resize();
    window.addEventListener('resize', resize);
  }

  function resize(){
    var w = cv.clientWidth || window.innerWidth;
    var h = cv.clientHeight || window.innerHeight;
    VW = Math.max(320, Math.round(w / SCALE));
    VH = Math.max(240, Math.round(h / SCALE));
    cv.width = VW; cv.height = VH;
    ctx.imageSmoothingEnabled = false;
  }

  function scaleFactor(){ return SCALE; }

  function w2s(wx, wy){ return { x: wx - wy + ox, y: (wx + wy) * 0.5 + oy }; }
  function s2w(sx, sy){
    var x = sx - ox, y = sy - oy;
    return { x: y + x * 0.5, y: y - x * 0.5 };
  }
  /* 화면 좌표(마우스) → 월드 좌표 */
  function screenToWorld(sx, sy){ return s2w(sx, sy); }

  function worldMode(){ ctx.save(); ctx.transform(1, 0.5, -1, 0.5, ox, oy); }
  function endWorld(){ ctx.restore(); }

  /* ---------- 프레임 -------------------------------------- */
  function draw(W, ui){
    var p = W.player;
    cam.x += (p.x - cam.x) * 0.18;
    cam.y += (p.y - cam.y) * 0.18;
    ox = VW/2 - (cam.x - cam.y);
    oy = VH/2 - (cam.x + cam.y) * 0.5 - 24;

    ctx.fillStyle = '#12151c';
    ctx.fillRect(0, 0, VW, VH);

    drawGround(W);
    drawGroundFx(W);
    drawArtFx(W);
    drawEntities(W, ui);
    drawAirFx(W);
    drawOffscreen(W);
    drawTexts(W);
    drawCursor(W, ui);
    drawVignette();
    drawBossBar(W);
  }

  /* ---------- 바닥 ---------------------------------------- */
  function drawGround(W){
    var T = W.tile, i, j;
    /* 화면에 보이는 타일 범위 추정 */
    var c0 = s2w(-SP.TW, -SP.TH), c1 = s2w(VW + SP.TW, -SP.TH);
    var c2 = s2w(-SP.TW, VH + SP.TH), c3 = s2w(VW + SP.TW, VH + SP.TH);
    var minX = Math.min(c0.x, c1.x, c2.x, c3.x), maxX = Math.max(c0.x, c1.x, c2.x, c3.x);
    var minY = Math.min(c0.y, c1.y, c2.y, c3.y), maxY = Math.max(c0.y, c1.y, c2.y, c3.y);
    var tx0 = Math.max(0, Math.floor(minX / T) - 1), tx1 = Math.min(W.mapW-1, Math.ceil(maxX / T) + 1);
    var ty0 = Math.max(0, Math.floor(minY / T) - 1), ty1 = Math.min(W.mapH-1, Math.ceil(maxY / T) + 1);

    for(j = ty0; j <= ty1; j++){
      for(i = tx0; i <= tx1; i++){
        var t = W.tiles[j*W.mapW + i];
        if(!t) continue;
        var s = w2s(i*T + T/2, j*T + T/2);
        ctx.drawImage(SP.tile(t.kind, t.v), Math.round(s.x - SP.TW/2), Math.round(s.y - SP.TH/2));
      }
    }
  }

  /* 바닥에 깔리는 이펙트 (장판/표식/흔적) */
  function drawGroundFx(W){
    var i, f, k;
    worldMode();
    /* 지속 장판 */
    for(i = 0; i < W.zones.length; i++){
      var z = W.zones[i];
      ctx.globalAlpha = 0.18;
      ctx.fillStyle = EL_COLOR[z.el] || '#fff';
      ctx.beginPath(); ctx.arc(z.x, z.y, z.r, 0, 6.2832); ctx.fill();
      ctx.globalAlpha = 0.5;
      ctx.strokeStyle = EL_COLOR[z.el] || '#fff';
      ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(z.x, z.y, z.r, 0, 6.2832); ctx.stroke();
    }
    for(i = 0; i < W.fx.length; i++){
      f = W.fx[i];
      k = f.t / f.dur;
      switch(f.type){
        case 'mark':
          ctx.globalAlpha = 0.35;
          ctx.fillStyle = f.col;
          ctx.beginPath(); ctx.arc(f.x, f.y, f.radius * k, 0, 6.2832); ctx.fill();
          ctx.globalAlpha = 0.85; ctx.strokeStyle = f.col; ctx.lineWidth = 2.5;
          ctx.beginPath(); ctx.arc(f.x, f.y, f.radius, 0, 6.2832); ctx.stroke();
          break;
        case 'boom':
          ctx.globalAlpha = (1 - k) * 0.55;
          ctx.fillStyle = f.col;
          ctx.beginPath(); ctx.arc(f.x, f.y, f.radius * (0.35 + k*0.75), 0, 6.2832); ctx.fill();
          ctx.globalAlpha = 1 - k; ctx.strokeStyle = '#fff'; ctx.lineWidth = 3 * (1-k);
          ctx.beginPath(); ctx.arc(f.x, f.y, f.radius * (0.4 + k), 0, 6.2832); ctx.stroke();
          break;
        case 'nova':
          ctx.globalAlpha = (1 - k) * 0.9;
          ctx.strokeStyle = f.col; ctx.lineWidth = 6 * (1 - k) + 1;
          ctx.beginPath(); ctx.arc(f.x, f.y, f.radius * (0.25 + k*0.85), 0, 6.2832); ctx.stroke();
          ctx.globalAlpha = (1 - k) * 0.25;
          ctx.fillStyle = f.col;
          ctx.beginPath(); ctx.arc(f.x, f.y, f.radius * (0.2 + k*0.8), 0, 6.2832); ctx.fill();
          break;
        case 'zonetick':
          ctx.globalAlpha = (1 - k) * 0.22;
          ctx.fillStyle = f.col;
          ctx.beginPath(); ctx.arc(f.x, f.y, f.radius, 0, 6.2832); ctx.fill();
          break;
        case 'trail':
          ctx.globalAlpha = (1 - k) * 0.6;
          ctx.strokeStyle = f.col; ctx.lineWidth = 14 * (1 - k);
          ctx.beginPath(); ctx.moveTo(f.x, f.y); ctx.lineTo(f.x2, f.y2); ctx.stroke();
          break;
        case 'slash':
          ctx.globalAlpha = (1 - k) * 0.85;
          ctx.strokeStyle = f.col || '#fff';
          ctx.lineWidth = 7 * (1 - k*0.6);
          ctx.beginPath();
          ctx.arc(f.x, f.y, f.range * (0.62 + k*0.4), f.ang - f.arc/2, f.ang + f.arc/2);
          ctx.stroke();
          ctx.globalAlpha = (1 - k) * 0.35;
          ctx.lineWidth = 2;
          ctx.beginPath();
          ctx.arc(f.x, f.y, f.range * (0.4 + k*0.3), f.ang - f.arc/2, f.ang + f.arc/2);
          ctx.stroke();
          break;
        case 'beam':
          ctx.globalAlpha = (1 - k);
          ctx.strokeStyle = f.col; ctx.lineWidth = f.width * (1 - k*0.5);
          ctx.beginPath(); ctx.moveTo(f.x, f.y); ctx.lineTo(f.x2, f.y2); ctx.stroke();
          ctx.globalAlpha = (1 - k) * 0.9; ctx.strokeStyle = '#fff'; ctx.lineWidth = 3;
          ctx.beginPath(); ctx.moveTo(f.x, f.y); ctx.lineTo(f.x2, f.y2); ctx.stroke();
          break;
        case 'spawn':
          ctx.globalAlpha = 0.7 * (1 - k);
          ctx.strokeStyle = f.col; ctx.lineWidth = 3;
          ctx.beginPath(); ctx.arc(f.x, f.y, 34 * (1 - k) + 6, 0, 6.2832); ctx.stroke();
          break;
        case 'blink':
          ctx.globalAlpha = (1 - k) * 0.8;
          ctx.strokeStyle = f.col || '#c79bff'; ctx.lineWidth = 3;
          ctx.beginPath(); ctx.arc(f.x, f.y, 8 + k*30, 0, 6.2832); ctx.stroke();
          break;
        case 'levelup':
          ctx.globalAlpha = (1 - k) * 0.9;
          ctx.strokeStyle = '#ffd76a'; ctx.lineWidth = 4 * (1 - k) + 1;
          ctx.beginPath(); ctx.arc(f.x, f.y, 20 + k*80, 0, 6.2832); ctx.stroke();
          ctx.beginPath(); ctx.arc(f.x, f.y, 10 + k*44, 0, 6.2832); ctx.stroke();
          break;
      }
    }
    ctx.globalAlpha = 1;
    endWorld();
  }

  /* ---------- 엔티티 (깊이 정렬) --------------------------- */
  function drawEntities(W, ui){
    var list = [], i;
    for(i = 0; i < W.props.length; i++) list.push({ d: W.props[i].x + W.props[i].y, kind:'prop', o: W.props[i] });
    for(i = 0; i < W.corpses.length; i++) list.push({ d: W.corpses[i].x + W.corpses[i].y, kind:'corpse', o: W.corpses[i] });
    for(i = 0; i < W.mobs.length; i++) list.push({ d: W.mobs[i].x + W.mobs[i].y, kind:'mob', o: W.mobs[i] });
    for(i = 0; i < W.orbs.length; i++) list.push({ d: W.orbs[i].x + W.orbs[i].y, kind:'orb', o: W.orbs[i] });
    for(i = 0; i < W.shots.length; i++) list.push({ d: W.shots[i].x + W.shots[i].y, kind:'shot', o: W.shots[i] });
    list.push({ d: W.player.x + W.player.y, kind:'player', o: W.player });
    list.sort(function(a, b){ return a.d - b.d; });

    for(i = 0; i < list.length; i++){
      var e = list[i];
      if(e.kind === 'prop') drawProp(e.o);
      else if(e.kind === 'mob') drawMob(e.o);
      else if(e.kind === 'orb') drawOrb(e.o);
      else if(e.kind === 'shot') drawShot(e.o);
      else if(e.kind === 'corpse') drawCorpse(e.o);
      else drawPlayer(W, e.o);
    }
  }

  function shadow(sx, sy, r, a){
    ctx.globalAlpha = a === undefined ? 0.28 : a;
    ctx.fillStyle = '#000';
    ctx.beginPath();
    ctx.ellipse(sx, sy, r, r * 0.5, 0, 0, 6.2832);
    ctx.fill();
    ctx.globalAlpha = 1;
  }

  function drawProp(pr){
    var s = w2s(pr.x, pr.y);
    var img = SP.prop(pr.kind), k = 2;
    shadow(s.x, s.y, (pr.kind === 'tree' ? 13 : 9) * k, 0.22);
    ctx.drawImage(img, Math.round(s.x - img.width*k/2), Math.round(s.y - (img.height - 14) * k),
                  img.width*k, img.height*k);
  }

  /* 스프라이트 시트에서 프레임 하나를 그린다.
     sp = {img, frames, fw, fh, bx, by, bw, bh}, targetH = 화면상 높이 */
  function drawSprite(sp, frame, sx, sy, targetH, flip, flash, alpha, sil){
    var k = targetH / sp.bh;
    var sxSrc = (frame % sp.frames) * sp.fw;
    var dw = sp.fw * k, dh = sp.fh * k;
    var dx = sx - (sp.bx + sp.bw/2) * k;      /* 내용 가운데를 발 위치에 맞춘다 */
    var dy = sy - (sp.by + sp.bh) * k;
    ctx.save();
    if(alpha !== undefined) ctx.globalAlpha = alpha;
    if(flip){                                  /* sx 기준 좌우 대칭 */
      ctx.translate(sx, 0);
      ctx.scale(-1, 1);
      ctx.translate(-sx, 0);
    }
    ctx.drawImage(sp.img, sxSrc, 0, sp.fw, sp.fh, Math.round(dx), Math.round(dy), dw, dh);
    if(flash > 0){
      /* 실루엣이 있으면 흰 판을 덮어 확실히 번쩍이게 한다 */
      ctx.globalAlpha = Math.min(0.85, flash * 6.5);
      if(sil){
        ctx.drawImage(sil.img, sxSrc, 0, sp.fw, sp.fh, Math.round(dx), Math.round(dy), dw, dh);
      }else{
        ctx.globalCompositeOperation = 'lighter';
        ctx.drawImage(sp.img, sxSrc, 0, sp.fw, sp.fh, Math.round(dx), Math.round(dy), dw, dh);
      }
    }
    ctx.restore();
  }

  /* 에셋이 없을 때 쓰는 도형 스프라이트 */
  function drawUnitSprite(img, s, flip, scale, flash){
    var w = img.width * scale, h = img.height * scale;
    var dx = Math.round(s.x - w/2), dy = Math.round(s.y - h + 6 * scale);
    ctx.save();
    if(flip){
      ctx.translate(Math.round(s.x), 0);
      ctx.scale(-1, 1);
      ctx.drawImage(img, Math.round(-w/2), dy, w, h);
    }else{
      ctx.drawImage(img, dx, dy, w, h);
    }
    ctx.restore();
    if(flash > 0){
      ctx.save();
      ctx.globalAlpha = Math.min(0.85, flash * 5);
      ctx.globalCompositeOperation = 'lighter';
      ctx.drawImage(img, dx, dy, w, h);
      ctx.restore();
    }
  }

  function drawMob(m){
    var s = w2s(m.x, m.y);
    /* 공격 중에는 공격 시트를, 평소에는 같은 시트의 첫 프레임을 쓴다 */
    var atk = m.atkAnim >= 0 ? Assets.get('mobatk', m.art) : null;
    var sp = atk || Assets.get('mob', m.art);
    var frame = 0;
    if(atk) frame = Math.min(atk.frames - 1, Math.floor(m.atkAnim / m.atkDur * atk.frames));
    shadow(s.x, s.y, m.r * 0.9, 0.32);

    if(sp){
      /* 걸을 때 위아래로 살짝 흔든다 (정지 이미지에 생동감을 준다) */
      var bob = m.anim === 'walk' ? Math.sin(m.animT * 3.2) * (m.h * 0.02) : 0;
      /* 맞으면 맞은 방향으로 튕겼다가 돌아온다 */
      var push = m.hitPush || 0, rx = 0, ry = 0;
      if(push > 0){
        var kick = Math.sin(push * Math.PI) * (m.boss ? 5 : 11);
        var cd = Math.cos(m.hitDir || 0), sd = Math.sin(m.hitDir || 0);
        rx = (cd - sd) * kick;
        ry = (cd + sd) * 0.5 * kick;
      }
      var squash = 1 - Math.sin(push * Math.PI) * 0.07;
      drawSprite(sp, frame, s.x + rx, s.y + bob + ry, m.h * squash, m.flip, m.flash,
                 undefined, Assets.silhouette(atk ? 'mobatk' : 'mob', m.art, '#fff'));
    }else{
      var img = SP.unit({}, 'none', 'humanoid', m.dir, m.anim, m.frame);
      drawUnitSprite(img, s, m.flip, 1, m.flash);
    }

    if(m.freeze > 0){
      ctx.save();
      ctx.globalAlpha = 0.35; ctx.fillStyle = '#7fd8ff';
      ctx.fillRect(Math.round(s.x - m.r), Math.round(s.y - m.h), m.r*2, m.h);
      ctx.restore();
    }

    /* 체력바 */
    var bw = Math.max(30, m.r * 2.2), hy = s.y - m.h - 9;
    if(m.hp < m.maxhp || m.boss){
      ctx.fillStyle = 'rgba(0,0,0,0.65)';
      ctx.fillRect(Math.round(s.x - bw/2) - 1, Math.round(hy) - 1, bw + 2, 6);
      ctx.fillStyle = m.boss ? '#e04a4a' : '#68d06a';
      ctx.fillRect(Math.round(s.x - bw/2), Math.round(hy), Math.round(bw * Math.max(0, m.hp/m.maxhp)), 4);
    }
    if(m.dots.length){
      ctx.fillStyle = m.dots[0].el === 'poison' ? '#8ce35b' : '#ff7b2a';
      ctx.fillRect(Math.round(s.x - bw/2), Math.round(hy) - 5, 4, 4);
    }
  }

  /* 쓰러지는 연출 — 흰 섬광 뒤에 맞은 방향으로 밀리며 옅어진다 */
  function drawCorpse(c){
    var sp = Assets.get('mob', c.art);
    if(!sp) return;
    var k = c.t / c.dur;
    var s = w2s(c.x, c.y);
    var cd = Math.cos(c.dir), sd = Math.sin(c.dir);
    var slide = k * (c.boss ? 6 : 16);
    var dx = (cd - sd) * slide, dy = (cd + sd) * 0.5 * slide;
    shadow(s.x + dx, s.y + dy, c.h * 0.2 * (1 - k), 0.3 * (1 - k));
    if(k < 0.28){
      drawSprite(sp, 0, s.x + dx, s.y + dy, c.h, c.flip, 1, 1,
                 Assets.silhouette('mob', c.art, '#fff'));
    }else{
      drawSprite(sp, 0, s.x + dx, s.y + dy - k * 10, c.h * (1 - k * 0.15),
                 c.flip, 0, 1 - (k - 0.28) / 0.72);
    }
  }

  function drawPlayer(W, p){
    var s = w2s(p.x, p.y);
    if(p.dead){
      shadow(s.x, s.y, 20, 0.3);
      ctx.globalAlpha = 0.55;
      ctx.fillStyle = '#8a2a2a';
      ctx.fillRect(Math.round(s.x-18), Math.round(s.y-10), 36, 12);
      ctx.globalAlpha = 1;
      return;
    }
    shadow(s.x, s.y, 19, 0.34);

    /* 버프 오라 */
    if(p.buffs.length){
      worldMode();
      ctx.globalAlpha = 0.3 + Math.sin(W.time*6)*0.08;
      ctx.strokeStyle = EL_COLOR[p.buffs[p.buffs.length-1].el] || '#ffd76a';
      ctx.lineWidth = 4;
      ctx.beginPath(); ctx.arc(p.x, p.y, 38, 0, 6.2832); ctx.stroke();
      ctx.globalAlpha = 1;
      endWorld();
    }
    if(p.shield > 0){
      ctx.globalAlpha = 0.32;
      ctx.strokeStyle = '#a8e0ff'; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.ellipse(s.x, s.y - 44, 34, 52, 0, 0, 6.2832); ctx.stroke();
      ctx.globalAlpha = 1;
    }

    var art = Engine.artOf(p);
    var sp = Assets.forArt('hero', art);
    var flash = p.hitFlash > 0 ? p.hitFlash : 0;
    var blink = (p.invuln > 0 && Math.floor(W.time*20) % 2) ? 0.5 : undefined;

    if(sp){
      /* 공격 중에는 조준 방향으로 살짝 내지르는 연출 */
      var lunge = 0;
      if(p.anim === 'atk') lunge = Math.max(0, 1 - p.animT / 0.24) * 9;
      var px = s.x + Math.cos(p.aim) * lunge - Math.sin(p.aim) * 0;
      var lx = (Math.cos(p.aim) - Math.sin(p.aim)) * lunge;         /* 화면 기준 이동 */
      var ly = (Math.cos(p.aim) + Math.sin(p.aim)) * lunge * 0.5;
      var bob = p.anim === 'walk' ? Math.sin(p.animT * 2.4) * 2 : 0;
      var frame = Math.floor(W.time * 1000 / sp.dur) % sp.frames;
      drawSprite(sp, frame, s.x + lx, s.y + ly + bob, art.h, p.flip, flash, blink,
                 Assets.silhouette('hero', art.sprite, '#ff6a6a'));
    }else{
      var img = SP.unit(Engine.lookOf(p), Engine.weaponOf(p), 'humanoid', p.dir, p.anim, p.frame);
      drawUnitSprite(img, s, p.flip, 1, flash);
    }
  }

  function drawShot(sh){
    var s = w2s(sh.x, sh.y);
    var col = EL_COLOR[sh.el] || '#fff';
    var r = sh.radius ? Math.max(11, sh.radius * 0.34) : (sh.basic ? 8 : 10);
    ctx.save();
    ctx.globalCompositeOperation = 'lighter';
    ctx.globalAlpha = 0.85;
    ctx.fillStyle = col;
    ctx.beginPath(); ctx.ellipse(s.x, s.y - 30, r*1.5, r, 0, 0, 6.2832); ctx.fill();
    ctx.globalAlpha = 1;
    ctx.fillStyle = '#fff';
    ctx.beginPath(); ctx.ellipse(s.x, s.y - 30, r*0.6, r*0.42, 0, 0, 6.2832); ctx.fill();
    ctx.restore();
    /* 꼬리 */
    ctx.globalAlpha = 0.4;
    ctx.strokeStyle = col; ctx.lineWidth = r * 0.9;
    ctx.beginPath();
    ctx.moveTo(s.x, s.y - 30);
    var t = w2s(sh.x - sh.vx*0.04, sh.y - sh.vy*0.04);
    ctx.lineTo(t.x, t.y - 30);
    ctx.stroke();
    ctx.globalAlpha = 1;
  }

  function drawOrb(o){
    var s = w2s(o.x, o.y);
    var bob = Math.sin(o.t * 5) * 3;
    var col = o.kind === 'hp' ? '#ff6a7a' : '#6ab6ff';
    shadow(s.x, s.y, 9, 0.25);
    ctx.save();
    ctx.globalCompositeOperation = 'lighter';
    ctx.fillStyle = col;
    ctx.beginPath(); ctx.arc(s.x, s.y - 14 + bob, 9, 0, 6.2832); ctx.fill();
    ctx.fillStyle = '#fff';
    ctx.beginPath(); ctx.arc(s.x - 2, s.y - 16 + bob, 3, 0, 6.2832); ctx.fill();
    ctx.restore();
  }

  /* ---------- 스프라이트 시트 이펙트 ----------------------- */
  function drawArtFx(W){
    for(var i = 0; i < W.fx.length; i++){
      var f = W.fx[i];
      if(f.type !== 'art') continue;
      var sp = Assets.get('fx', f.sheet);
      if(!sp) continue;
      var fr = Math.min(sp.frames - 1, Math.floor(f.t / f.dur * sp.frames));
      var s = w2s(f.x, f.y);
      var k = f.size / sp.fw;
      var dw = sp.fw * k, dh = sp.fh * k;
      ctx.save();
      ctx.globalAlpha = 0.92;
      /* 이펙트는 바닥에 붙어 위로 터지는 그림이라 아래쪽 가운데를 기준점으로 둔다 */
      ctx.drawImage(sp.img, fr * sp.fw, 0, sp.fw, sp.fh,
                    Math.round(s.x - dw/2), Math.round(s.y - dh * 0.86), dw, dh);
      ctx.restore();
    }
  }

  /* ---------- 공중/전면 이펙트 ---------------------------- */
  function drawAirFx(W){
    var i, f, k, j;
    for(i = 0; i < W.fx.length; i++){
      f = W.fx[i];
      k = f.t / f.dur;
      var s;
      if(f.type === 'hit'){
        s = w2s(f.x, f.y);
        ctx.save();
        ctx.globalCompositeOperation = 'lighter';
        ctx.globalAlpha = 1 - k;
        ctx.strokeStyle = f.col; ctx.lineWidth = 2;
        for(j = 0; j < 4; j++){
          var a = j * 1.57 + k * 1.2;
          var r0 = 6 + k*16, r1 = 16 + k*24;
          ctx.beginPath();
          ctx.moveTo(s.x + Math.cos(a)*r0, s.y + Math.sin(a)*r0*0.6);
          ctx.lineTo(s.x + Math.cos(a)*r1, s.y + Math.sin(a)*r1*0.6);
          ctx.stroke();
        }
        ctx.restore();
      }else if(f.type === 'bolt'){
        var p0 = w2s(f.x, f.y), p1 = w2s(f.x2, f.y2);
        ctx.save();
        ctx.globalAlpha = 1 - k;
        ctx.strokeStyle = f.col; ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.moveTo(p0.x, p0.y - 12);
        var seg = 5;
        for(j = 1; j < seg; j++){
          var t = j/seg;
          ctx.lineTo(p0.x + (p1.x-p0.x)*t + (Math.random()-0.5)*14,
                     p0.y - 12 + (p1.y-p0.y+12-12)*t + (Math.random()-0.5)*14);
        }
        ctx.lineTo(p1.x, p1.y - 12);
        ctx.stroke();
        ctx.strokeStyle = '#fff'; ctx.lineWidth = 1;
        ctx.stroke();
        ctx.restore();
      }else if(f.type === 'death'){
        s = w2s(f.x, f.y);
        ctx.save();
        ctx.globalAlpha = 1 - k;
        ctx.fillStyle = f.col;
        for(j = 0; j < 8; j++){
          var ang = j * 0.785;
          var dd = k * (18 + f.size);
          ctx.fillRect(Math.round(s.x + Math.cos(ang)*dd - 2), Math.round(s.y - 10 + Math.sin(ang)*dd*0.6 - 2), 4, 4);
        }
        ctx.restore();
      }else if(f.type === 'buff' || f.type === 'heal'){
        s = w2s(f.x, f.y);
        ctx.save();
        ctx.globalAlpha = 1 - k;
        ctx.fillStyle = f.type === 'heal' ? '#7fe07f' : (f.col || '#ffd76a');
        for(j = 0; j < 6; j++){
          var aa = j * 1.05 + k * 2;
          ctx.fillRect(Math.round(s.x + Math.cos(aa) * 16 - 1.5),
                       Math.round(s.y - k * 42 + Math.sin(aa) * 6 - 4), 3, 3);
        }
        ctx.restore();
      }else if(f.type === 'levelup'){
        s = w2s(f.x, f.y);
        ctx.save();
        ctx.globalAlpha = 1 - k;
        ctx.fillStyle = '#ffe9a8';
        for(j = 0; j < 10; j++){
          var ax = j * 0.628;
          ctx.fillRect(Math.round(s.x + Math.cos(ax)*(10 + k*60) - 2),
                       Math.round(s.y - 16 + Math.sin(ax)*(10 + k*60)*0.55 - 2), 4, 4);
        }
        ctx.restore();
      }
    }
    ctx.globalAlpha = 1;
  }

  /* 화면 밖의 적을 가장자리 화살표로 알려준다 */
  function drawOffscreen(W){
    var pad = 26, shown = 0;
    for(var i = 0; i < W.mobs.length && shown < 18; i++){
      var m = W.mobs[i];
      if(m.dead) continue;
      var s = w2s(m.x, m.y);
      if(s.x > pad && s.x < VW - pad && s.y > pad && s.y < VH - pad) continue;
      var cx = VW/2, cy = VH/2;
      var dx = s.x - cx, dy = s.y - cy;
      var len = Math.sqrt(dx*dx + dy*dy) || 1;
      /* 화면 안쪽 사각형과의 교점 */
      var t = Math.min((VW/2 - pad) / Math.abs(dx || 0.0001), (VH/2 - pad) / Math.abs(dy || 0.0001));
      var ax = cx + dx * t, ay = cy + dy * t;
      var ang = Math.atan2(dy, dx);
      ctx.save();
      ctx.translate(ax, ay);
      ctx.rotate(ang);
      ctx.globalAlpha = 0.75;
      ctx.fillStyle = m.boss ? '#ff5a5a' : '#ffd76a';
      ctx.beginPath();
      ctx.moveTo(11, 0); ctx.lineTo(-9, -7); ctx.lineTo(-9, 7);
      ctx.closePath(); ctx.fill();
      ctx.restore();
      shown++;
    }
    ctx.globalAlpha = 1;
  }

  /* ---------- 데미지 숫자 --------------------------------- */
  var TEXT_COL = {
    dmg:'#ffffff', crit:'#ffd23a', taken:'#ff5a5a', heal:'#7fe07f',
    poison:'#8ce35b', burn:'#ff9a3a', shield:'#a8e0ff', mp:'#6ab6ff'
  };

  function drawTexts(W){
    ctx.textAlign = 'center';
    for(var i = 0; i < W.texts.length; i++){
      var t = W.texts[i];
      var s = w2s(t.x, t.y);
      var k = t.t / t.dur;
      var big = t.kind === 'crit';
      ctx.globalAlpha = k > 0.7 ? (1 - k) / 0.3 : 1;
      ctx.font = 'bold ' + (big ? 22 : 16) + 'px "Courier New", monospace';
      ctx.lineWidth = 4;
      ctx.strokeStyle = 'rgba(0,0,0,0.85)';
      var str = (t.kind === 'heal' ? '+' : '') + t.v;
      ctx.strokeText(str, s.x, s.y);
      ctx.fillStyle = TEXT_COL[t.kind] || '#fff';
      ctx.fillText(str, s.x, s.y);
    }
    ctx.globalAlpha = 1;
    ctx.textAlign = 'left';
  }

  /* ---------- 커서 / 조준 -------------------------------- */
  function drawCursor(W, ui){
    if(!ui || !ui.aim) return;
    var a = ui.aim;
    worldMode();
    ctx.globalAlpha = 0.55;
    ctx.strokeStyle = '#ffe9a8'; ctx.lineWidth = 1.6;
    ctx.beginPath(); ctx.arc(a.x, a.y, 20, 0, 6.2832); ctx.stroke();
    ctx.beginPath(); ctx.arc(a.x, a.y, 6, 0, 6.2832); ctx.stroke();
    /* 시전 예정 지점 미리보기 */
    if(ui.preview){
      ctx.globalAlpha = 0.3;
      ctx.strokeStyle = ui.preview.col; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(ui.preview.x, ui.preview.y, ui.preview.r, 0, 6.2832); ctx.stroke();
    }
    ctx.globalAlpha = 1;
    endWorld();
  }

  function drawVignette(){
    var g = ctx.createRadialGradient(VW/2, VH/2, Math.min(VW,VH)*0.35, VW/2, VH/2, Math.max(VW,VH)*0.72);
    g.addColorStop(0, 'rgba(0,0,0,0)');
    g.addColorStop(1, 'rgba(0,0,0,0.45)');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, VW, VH);
  }

  function drawBossBar(W){
    var b = W.boss;
    if(!b || b.dead) return;
    var w = Math.min(520, VW - 80), x = (VW - w)/2, y = 18;
    ctx.fillStyle = 'rgba(0,0,0,0.6)';
    ctx.fillRect(x-3, y-3, w+6, 20);
    ctx.fillStyle = '#3a1416';
    ctx.fillRect(x, y, w, 14);
    ctx.fillStyle = '#e04a4a';
    ctx.fillRect(x, y, w * Math.max(0, b.hp/b.maxhp), 14);
    ctx.font = 'bold 14px "Courier New", monospace';
    ctx.textAlign = 'center';
    ctx.fillStyle = '#ffd8d8';
    ctx.fillText(b.name, VW/2, y + 32);
    ctx.textAlign = 'left';
  }

  return {
    init: init, draw: draw, resize: resize,
    screenToWorld: screenToWorld, w2s: w2s,
    scaleFactor: scaleFactor,
    get vw(){ return VW; }, get vh(){ return VH; }
  };
})();
