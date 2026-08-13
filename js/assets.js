/* ============================================================
   에셋 로더 — assets/manifest.json 에 적힌 스프라이트를 읽어온다.
   각 항목: {file, frames, fw, fh, dur, bx, by, bw, bh}
     frames  가로로 이어 붙인 프레임 수
     fw/fh   프레임 한 장 크기
     bx..bh  프레임 안에서 그림이 실제로 차지하는 영역(투명 여백 제외)
   ============================================================ */
var Assets = (function(){
  'use strict';

  var man = null;
  var imgs = {};          /* 'hero/knight' → Image */
  var tintCache = {};
  var loaded = 0, total = 0, ready = false;

  function key(kind, name){ return kind + '/' + name; }

  /* manifest.json 을 못 읽는 환경(file:// 등)에서도 게임은 돌아가야 하므로
     실패하면 ready=false 로 두고 렌더러가 도형 스프라이트로 대체한다. */
  function load(base, onProgress){
    base = base || 'assets/';
    /* 단일 파일 빌드는 그림이 data URI 로 함께 들어 있다 (tools/build-single.js) */
    var bundle = window.__ASSET_BUNDLE__;
    var head = bundle
      ? Promise.resolve(bundle.manifest)
      : fetch(base + 'manifest.json').then(function(r){
          if(!r.ok) throw new Error('manifest ' + r.status);
          return r.json();
        });
    if(bundle) base = '';
    return head
      .then(function(json){
        man = json;
        var list = [];
        ['hero','mob','fx'].forEach(function(kind){
          for(var name in man[kind]) list.push({ kind: kind, name: name, def: man[kind][name] });
        });
        total = list.length; loaded = 0;
        return Promise.all(list.map(function(it){
          return new Promise(function(res){
            var img = new Image();
            img.onload = img.onerror = function(){
              loaded++;
              if(onProgress) onProgress(loaded, total);
              res();
            };
            img.src = bundle ? bundle.files[it.def.file] : base + it.def.file;
            imgs[key(it.kind, it.name)] = img;
          });
        }));
      })
      .then(function(){ ready = true; return true; })
      .catch(function(e){
        console.warn('에셋을 불러오지 못했다 — 기본 도형으로 그린다:', e.message);
        ready = false;
        return false;
      });
  }

  /* 스프라이트 정보 + 이미지. 없으면 null */
  function get(kind, name){
    if(!ready || !man || !man[kind] || !man[kind][name]) return null;
    var d = man[kind][name], img = imgs[key(kind, name)];
    if(!img || !img.width) return null;
    return { img: img, frames: d.frames, fw: d.fw, fh: d.fh, dur: d.dur || 120,
             bx: d.bx, by: d.by, bw: d.bw, bh: d.bh };
  }

  /* 색조 변경본 — 명암은 유지하고 색만 바꾼다 (2차 전직 색놀이용) */
  function tinted(kind, name, color, amount){
    var sp = get(kind, name);
    if(!sp || !color) return sp;
    var ck = key(kind, name) + '|' + color + '|' + amount;
    if(tintCache[ck]) return tintCache[ck];

    var c = document.createElement('canvas');
    c.width = sp.img.width; c.height = sp.img.height;
    var x = c.getContext('2d');
    x.imageSmoothingEnabled = false;
    x.drawImage(sp.img, 0, 0);
    x.globalCompositeOperation = 'color';       /* 색상만 덧씌운다 */
    x.globalAlpha = amount === undefined ? 0.5 : amount;
    x.fillStyle = color;
    x.fillRect(0, 0, c.width, c.height);
    x.globalAlpha = 1;
    x.globalCompositeOperation = 'destination-in';  /* 원본 투명도 복원 */
    x.drawImage(sp.img, 0, 0);

    var out = { img: c, frames: sp.frames, fw: sp.fw, fh: sp.fh, dur: sp.dur,
                bx: sp.bx, by: sp.by, bw: sp.bw, bh: sp.bh };
    tintCache[ck] = out;
    return out;
  }

  /* 단색 실루엣 — 피격 순간 흰색으로 번쩍이게 할 때 쓴다.
     가산 합성은 밝은 그림에서 티가 안 나서, 아예 모양만 남긴 판을 덧그린다. */
  function silhouette(kind, name, color){
    var sp = get(kind, name);
    if(!sp) return null;
    var ck = 'sil|' + key(kind, name) + '|' + color;
    if(tintCache[ck]) return tintCache[ck];

    var c = document.createElement('canvas');
    c.width = sp.img.width; c.height = sp.img.height;
    var x = c.getContext('2d');
    x.imageSmoothingEnabled = false;
    x.drawImage(sp.img, 0, 0);
    x.globalCompositeOperation = 'source-in';
    x.fillStyle = color || '#fff';
    x.fillRect(0, 0, c.width, c.height);

    var out = { img: c, frames: sp.frames, fw: sp.fw, fh: sp.fh, dur: sp.dur,
                bx: sp.bx, by: sp.by, bw: sp.bw, bh: sp.bh };
    tintCache[ck] = out;
    return out;
  }

  /* art 설정({sprite,h,tint,tintAmt})을 그대로 받아 스프라이트를 돌려준다 */
  function forArt(kind, art){
    if(!art) return null;
    return art.tint ? tinted(kind, art.sprite, art.tint, art.tintAmt) : get(kind, art.sprite);
  }

  return {
    load: load, get: get, tinted: tinted, silhouette: silhouette, forArt: forArt,
    get ready(){ return ready; },
    get progress(){ return total ? loaded / total : 0; }
  };
})();
