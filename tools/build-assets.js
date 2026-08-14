/* ============================================================
   에셋 빌드 — 원본 HTML(index_story_1.html)에 base64 로 박혀 있는
   픽셀아트를 꺼내서 assets/ 아래 파일로 저장한다.

     node tools/build-assets.js <원본html> [출력디렉터리]

   - 애니메이션 GIF : ImageDecoder 로 프레임을 뜯어 가로 스프라이트 시트(PNG)
   - 대형 PNG       : 게임에서 쓰는 높이(150px)로 축소
   - 이펙트 WEBP    : 8프레임 시트를 손실 압축으로 재인코딩 (용량 1/4)
   결과와 함께 assets/manifest.json 을 만든다.
   ============================================================ */
const fs = require('fs');
const path = require('path');

const SRC = process.argv[2];
const ATK = process.argv[3] && !process.argv[3].startsWith('-') &&
            fs.existsSync(process.argv[3]) && fs.statSync(process.argv[3]).isDirectory()
            ? process.argv[3] : null;          /* 몬스터 공격 GIF 폴더(선택) */
const OUT = (ATK ? process.argv[4] : process.argv[3]) || path.join(__dirname, '..', 'assets');
if(!SRC || !fs.existsSync(SRC)){
  console.error('원본 HTML 경로를 넘겨라: node tools/build-assets.js <html> [공격gif폴더] [out]');
  process.exit(1);
}

/* ---- 게임에서 실제로 쓰는 것만 골라 담는다 ---- */
const HERO = {                       /* 직업 스프라이트 */
  knight:'knight', mage:'mage', archer:'archer', priest:'priest',
  warrior:'warrior', ice_mage:'ice_mage', assassin:'assassin',
  lancer:'lancer', summoner:'summoner'
};
const MOB = [
  'slime','slime_poison','slime_ice','slime_king','goblin','goblin_archer','goblin_knight',
  'goblin_mage','goblin_lord','orc','orc_warrior','orc_archer','orc_mage','orc_lord',
  'skeleton','zombie','ghoul','lich','lizard','lizard_archer','lizard_mage','lizard_lord',
  'darkelf','darkelf_mage','darkelf_knight','darkelf_queen','golem','succubus',
  'spirit_light','spirit_dark','chaos_lord','demon_lord'
];
/* 이펙트 시트: 원본의 d, d_2 … d_27 을 의미 있는 이름으로 바꿔 쓴다 */
const FX = {
  d:'slash_dust',      d_2:'slash_arcane',  d_3:'burst_white',   d_4:'burst_flame',
  d_5:'slash_cross',   d_6:'boom_red',      d_7:'meteor',        d_8:'pillar_fire',
  d_9:'nova_arcane',   d_10:'holy_burst',   d_11:'holy_pillar',  d_12:'boom_crimson',
  d_13:'slash_claw',   d_14:'beam_red',     d_15:'rune_circle',  d_16:'slash_dark',
  d_17:'poison_splash',d_18:'mark_ring',    d_19:'ice_shard',    d_20:'ice_burst',
  d_21:'dome_white',   d_22:'water_burst',  d_23:'dust_ground',  d_24:'heal_burst',
  d_25:'slash_gold',   d_26:'crescent_gold',d_27:'arrow_rain'
};
/* 직업 공격 모션 (원본의 512px 공격 GIF) — 이미 오른쪽을 보고 있어 반전하지 않는다 */
const HERO_ATK = {
  knight_2:'knight', mage_2:'mage', archer_2:'archer',
  priest_2:'priest', warrior_2:'warrior'
};
const HERO_H = 150;                  /* 대형 PNG 를 줄일 높이 */

/* 공격 GIF 폴더가 있으면 몬스터 목록과 이름이 겹치는 것만 골라 담는다 */
const atkItems = [], atkKeys = {};
if(ATK){
  for(const f of fs.readdirSync(ATK)){
    const m = /^(.+)_attack\.gif$/.exec(f);
    if(!m || MOB.indexOf(m[1]) < 0) continue;
    atkKeys[m[1]] = true;
    atkItems.push({ kind:'mobatk', name:m[1], ext:'gif',
                    b64: fs.readFileSync(path.join(ATK, f)).toString('base64') });
  }
}

const html = fs.readFileSync(SRC, 'utf8');
const re = /([A-Za-z_$][A-Za-z0-9_$]*)\s*[:=]\s*["'](data:image\/(png|webp|gif);base64,([A-Za-z0-9+/=\s]+))["']/g;

const seen = {}, items = [];
let m;
while((m = re.exec(html)) !== null){
  const key = m[1], ext = m[3], b64 = m[4].replace(/\s+/g, '');
  seen[key] = (seen[key] || 0) + 1;
  const uniq = seen[key] === 1 ? key : key + '_' + seen[key];
  let kind = null, name = null;
  if(ext === 'gif' && HERO[key] && seen[key] === 1){ kind = 'hero'; name = HERO[key]; }
  else if(ext === 'png' && HERO[key] && seen[key] === 1){ kind = 'hero'; name = HERO[key]; }
  else if(ext === 'png' && MOB.indexOf(key) >= 0 && seen[key] === 1 && !atkKeys[key]){ kind = 'mob'; name = key; }
  else if(ext === 'gif' && HERO_ATK[uniq]){ kind = 'heroatk'; name = HERO_ATK[uniq]; }
  else if(ext === 'webp' && FX[uniq]){ kind = 'fx'; name = FX[uniq]; }
  if(kind) items.push({ kind, name, ext, b64 });
}
items.push.apply(items, atkItems);
console.log('처리 대상 ' + items.length + '개' + (ATK ? ' (공격모션 ' + atkItems.length + '종 포함)' : ''));

(async () => {
  const { chromium } = require('/opt/node22/lib/node_modules/playwright');
  /* ImageDecoder 는 보안 컨텍스트에서만 노출된다 → 로컬 http 로 띄운다 */
  const server = require('http').createServer((q, s) => {
    s.writeHead(200, { 'Content-Type': 'text/html' });
    s.end('<!doctype html><meta charset=utf-8><title>build</title>');
  });
  await new Promise(r => server.listen(0, '127.0.0.1', r));
  const port = server.address().port;

  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('http://127.0.0.1:' + port + '/');

  const manifest = { hero: {}, mob: {}, fx: {}, mobatk: {}, heroatk: {} };
  ['hero','mob','fx','mobatk','heroatk'].forEach(function(d){
    fs.mkdirSync(path.join(OUT, d), { recursive: true });
  });

  for(const it of items){
    const res = await page.evaluate(async (a) => {
      const url = 'data:image/' + a.ext + ';base64,' + a.b64;
      const toB64 = blob => new Promise(r => {
        const fr = new FileReader();
        fr.onload = () => r(fr.result.split(',')[1]);
        fr.readAsDataURL(blob);
      });

      /* 첫 프레임에서 실제 그림이 차지하는 영역을 잰다.
         발 위치를 맞추고 크기를 통일하려면 투명 여백을 알아야 한다. */
      function bboxOf(cx, fw, fh){
        const d = cx.getImageData(0, 0, fw, fh).data;
        let x0 = fw, y0 = fh, x1 = -1, y1 = -1;
        for(let y = 0; y < fh; y++){
          for(let x = 0; x < fw; x++){
            if(d[(y*fw + x)*4 + 3] > 12){
              if(x < x0) x0 = x;
              if(x > x1) x1 = x;
              if(y < y0) y0 = y;
              if(y > y1) y1 = y;
            }
          }
        }
        if(x1 < 0) return { bx:0, by:0, bw:fw, bh:fh };
        return { bx:x0, by:y0, bw:x1-x0+1, bh:y1-y0+1 };
      }

      /* --- 애니메이션 GIF → 가로 스프라이트 시트 --- */
      if(a.ext === 'gif'){
        const buf = await (await fetch(url)).arrayBuffer();
        const dec = new ImageDecoder({ data: buf, type: 'image/gif' });
        await dec.tracks.ready; await dec.completed;
        const n = dec.tracks.selectedTrack.frameCount;
        const first = await dec.decode({ frameIndex: 0 });
        const ow = first.image.displayWidth, oh = first.image.displayHeight;
        /* 크기 기준: 보통은 캔버스 높이, 공격 모션은 첫 프레임의 "몸 높이" */
        let ref = oh;
        if(a.byContent){
          const t = new OffscreenCanvas(ow, oh);
          const tx = t.getContext('2d');
          tx.drawImage(first.image, 0, 0);
          ref = bboxOf(tx, ow, oh).bh;
        }
        const k = ref > a.maxH ? a.maxH / ref : 1;
        let fw = Math.round(ow * k), fh = Math.round(oh * k);
        let cv = new OffscreenCanvas(fw * n, fh);
        let cx = cv.getContext('2d');
        cx.imageSmoothingEnabled = k < 1;
        cx.imageSmoothingQuality = 'high';
        let dur = 0;
        for(let i = 0; i < n; i++){
          const f = await dec.decode({ frameIndex: i });
          if(a.mirror){                       /* 원본이 왼쪽을 보고 있으면 뒤집는다 */
            cx.save();
            cx.translate((i + 1) * fw, 0);
            cx.scale(-1, 1);
            cx.drawImage(f.image, 0, 0, fw, fh);
            cx.restore();
          }else{
            cx.drawImage(f.image, i * fw, 0, fw, fh);
          }
          dur += (f.image.duration || 100000) / 1000;
        }
        let bb = bboxOf(cx, fw, fh);

        if(a.crop){
          /* 전 프레임을 합친 여백을 잘라 용량을 줄인다 (무손실 유지) */
          let ux0 = fw, uy0 = fh, ux1 = -1, uy1 = -1;
          for(let i = 0; i < n; i++){
            const t = new OffscreenCanvas(fw, fh);
            const tx = t.getContext('2d');
            tx.drawImage(cv, i * fw, 0, fw, fh, 0, 0, fw, fh);
            const b2 = bboxOf(tx, fw, fh);
            ux0 = Math.min(ux0, b2.bx); uy0 = Math.min(uy0, b2.by);
            ux1 = Math.max(ux1, b2.bx + b2.bw); uy1 = Math.max(uy1, b2.by + b2.bh);
          }
          const uw = Math.max(1, ux1 - ux0), uh = Math.max(1, uy1 - uy0);
          const cut = new OffscreenCanvas(uw * n, uh);
          const cutx = cut.getContext('2d');
          cutx.imageSmoothingEnabled = false;
          for(let i = 0; i < n; i++)
            cutx.drawImage(cv, i * fw + ux0, uy0, uw, uh, i * uw, 0, uw, uh);
          bb = { bx: bb.bx - ux0, by: bb.by - uy0, bw: bb.bw, bh: bb.bh };
          cv = cut; cx = cutx; fw = uw; fh = uh;
        }

        /* 공격 시트는 장수가 많아 손실 압축으로 담는다 (4배 확대해도 차이가 안 보이는 수준) */
        const blob = a.crop
          ? await cv.convertToBlob({ type: 'image/webp', quality: 0.92 })
          : await cv.convertToBlob({ type: 'image/png' });
        return Object.assign({ b64: await toB64(blob), ext: a.crop ? 'webp' : 'png',
                 frames: n, fw, fh, dur: Math.round(dur / n) }, bb);
      }

      /* --- 이미지 로드 --- */
      const img = new Image();
      img.src = url;
      await img.decode();

      /* --- 이펙트 시트: 8프레임 유지, 손실 재인코딩으로 용량만 줄인다 --- */
      if(a.ext === 'webp'){
        const n = 8, fw = Math.round(img.width / n);
        const cv = new OffscreenCanvas(img.width, img.height);
        const cx = cv.getContext('2d');
        cx.drawImage(img, 0, 0);
        /* 이펙트는 프레임마다 크기가 달라 가장 큰 프레임 기준으로 잰다 */
        const bb = bboxOf(cx, img.width, img.height);
        bb.bx = bb.bx % fw; bb.bw = Math.min(fw, bb.bw);
        const blob = await cv.convertToBlob({ type: 'image/webp', quality: 0.82 });
        return Object.assign({ b64: await toB64(blob), ext: 'webp', frames: n, fw,
                               fh: img.height, dur: 55 }, bb);
      }

      /* --- 정지 PNG: 너무 크면 줄인다 --- */
      let w = img.width, h = img.height;
      if(h > a.maxH){ w = Math.round(w * a.maxH / h); h = a.maxH; }
      const cv = new OffscreenCanvas(w, h);
      const cx = cv.getContext('2d');
      cx.imageSmoothingEnabled = (img.height / h > 1.2);   /* 축소할 때만 보간 */
      cx.imageSmoothingQuality = 'high';
      cx.drawImage(img, 0, 0, w, h);
      const bb = bboxOf(cx, w, h);
      const blob = await cv.convertToBlob({ type: 'image/png' });
      return Object.assign({ b64: await toB64(blob), ext: 'png', frames: 1,
                             fw: w, fh: h, dur: 0 }, bb);
    }, { ext: it.ext, b64: it.b64, maxH: HERO_H,
         byContent: it.kind === 'mobatk' || it.kind === 'heroatk',
         mirror: it.kind === 'mobatk',
         crop: it.kind === 'mobatk' || it.kind === 'heroatk' });

    const file = it.kind + '/' + it.name + '.' + res.ext;
    fs.writeFileSync(path.join(OUT, file), Buffer.from(res.b64, 'base64'));
    manifest[it.kind][it.name] = { file: file, frames: res.frames, fw: res.fw, fh: res.fh,
                                   dur: res.dur, bx: res.bx, by: res.by, bw: res.bw, bh: res.bh };
    console.log('  ' + file.padEnd(28) + res.fw + 'x' + res.fh + ' ×' + res.frames +
                '  ' + Math.round(Buffer.from(res.b64, 'base64').length / 1024) + 'KB');
  }

  /* 공격 시트가 있는 몬스터는 대기 모습도 같은 시트의 첫 프레임을 쓴다.
     (파일은 하나만 두고 manifest 에서 1프레임짜리로 가리킨다) */
  for(const name in manifest.mobatk){
    const a = manifest.mobatk[name];
    manifest.mob[name] = { file: a.file, frames: 1, fw: a.fw, fh: a.fh, dur: 0,
                           bx: a.bx, by: a.by, bw: a.bw, bh: a.bh };
  }

  fs.writeFileSync(path.join(OUT, 'manifest.json'), JSON.stringify(manifest, null, 1));
  await browser.close();
  server.close();

  let total = 0;
  for(const k of ['hero','mob','fx','mobatk','heroatk'])
    for(const n in manifest[k]) total += fs.statSync(path.join(OUT, manifest[k][n].file)).size;
  console.log('완료 — 합계 ' + Math.round(total/1024) + 'KB');
})();
