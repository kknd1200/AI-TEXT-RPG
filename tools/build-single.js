/* ============================================================
   단일 파일 빌드 — index.html + css + js + assets 를 하나로 합친다.
   그림은 전부 data URI 로 넣어서 서버 없이 파일만 열어도 돌아간다.

     node tools/build-single.js [출력경로]

   기본 출력: dist/quarterview-rpg.html
   --body 옵션을 주면 <html>/<head>/<body> 를 뺀 조각만 내보낸다
   (아티팩트처럼 바깥 골격을 직접 씌우는 곳에 쓴다).
   ============================================================ */
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const bodyOnly = process.argv.indexOf('--body') >= 0;
const OUT = process.argv.filter(function(a){ return a !== '--body'; })[2] ||
            path.join(ROOT, 'dist', bodyOnly ? 'quarterview-rpg.body.html' : 'quarterview-rpg.html');

const MIME = { png:'image/png', webp:'image/webp', gif:'image/gif' };

function read(p){ return fs.readFileSync(path.join(ROOT, p), 'utf8'); }

/* ---- 그림을 data URI 로 ---- */
const manifest = JSON.parse(read('assets/manifest.json'));
const files = {};
let bytes = 0;
for(const kind in manifest){
  for(const name in manifest[kind]){
    const rel = manifest[kind][name].file;
    if(files[rel]) continue;                    /* 여러 항목이 같은 파일을 가리킬 수 있다 */
    const buf = fs.readFileSync(path.join(ROOT, 'assets', rel));
    bytes += buf.length;
    files[rel] = 'data:' + MIME[rel.split('.').pop()] + ';base64,' + buf.toString('base64');
  }
}

/* ---- HTML 조립 ---- */
let html = read('index.html');
const css = read('css/style.css');
const js = ['js/data.js','js/sprites.js','js/assets.js','js/input.js',
            'js/engine.js','js/render.js','js/ui.js','js/main.js'].map(read);

const bundle = '<script>window.__ASSET_BUNDLE__=' +
               JSON.stringify({ manifest: manifest, files: files }) + ';<\/script>';

html = html.replace('<link rel="stylesheet" href="css/style.css">', '<style>\n' + css + '\n</style>');
html = html.replace(/<script src="js\/[a-z]+\.js"><\/script>\s*/g, '');
html = html.replace('</body>', bundle + '\n' +
        js.map(function(src){ return '<script>\n' + src + '\n<\/script>'; }).join('\n') + '\n</body>');

if(bodyOnly){
  /* <head> 안의 title/style 만 살려서 본문 앞에 붙인다 */
  const title = (html.match(/<title>[^<]*<\/title>/) || [''])[0];
  const style = (html.match(/<style>[\s\S]*?<\/style>/) || [''])[0];
  const body  = html.slice(html.indexOf('<body>') + 6, html.lastIndexOf('</body>'));
  html = title + '\n' + style + '\n' + body;
}

fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, html);
console.log(OUT);
console.log('  그림 ' + Object.keys(files).length + '장 (' + Math.round(bytes/1024) + 'KB) → ' +
            '전체 ' + Math.round(fs.statSync(OUT).size / 1024 / 1024 * 10) / 10 + 'MB');
