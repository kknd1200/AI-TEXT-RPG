"""Persist an explicitly incomplete asset bundle and its exact resumption list."""
import argparse, hashlib, json, zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'art-source/cre36'
PUBLIC=ROOT/'public/assets/cre36'

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output-dir',required=True,type=Path)
    args=parser.parse_args()
    args.output_dir.mkdir(parents=True,exist_ok=True)
    ids=json.loads((ART/'spec-v2.json').read_text())['identities']
    manifest=json.loads((PUBLIC/'manifest.json').read_text())
    missing_raw=[{'morphId':mid,'name':name,'action':a,'prompt':f'art-source/cre36/prompts/{mid}-{a}.txt','reference':f'art-source/cre36/raw/{mid}-feed.png'} for mid,name,_ in ids for a in ['feed','mist','clean','play'] if not (ART/'raw'/f'{mid}-{a}.png').exists()]
    raw_files=sorted((ART/'raw').glob('*.png'))
    body_count=sum(a!='idle' for form in manifest['forms'] for a in form['animations'])
    status={
        'status':'incomplete-image-generation-limit','productionPublished':False,
        'productionBaseCommit':'d60ad4d2bfd3465994c49462ffc260ab40349c3f',
        'branch':'work/cre36-care-sprites',
        'quotaResetUtc':'2026-09-08T01:30:06Z',
        'morphs':36,'forms':len(manifest['forms']),'portraits':sum('portrait' in f for f in manifest['forms']),
        'generatedRawSheets':len(raw_files),'processedBodyAnimations':body_count,
        'targetBodyAnimations':288,'missingRawSheets':missing_raw,
        'missingEffects':manifest['missingEffects'],
        'missingProcessedFiles':manifest['missingFiles'],
        'visualReviewRemaining':['Compare every action against its feed reference before final release.','cre_035: verify ivory dorsal coverage against the intended Black Lilly White identity; current feed has a dark saddle.'],
        'rawSources':[{'name':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in raw_files],
    }
    (ART/'checkpoint-status.json').write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n')
    lines=['# 크레 36종 동작 작업 재개','',
      '**전체 완료/운영 배포 전입니다.** 이미지 생성 한도로 중단됐으며 원화와 처리 결과를 보존했습니다.','',
      f'- 생성 원화 {len(raw_files)}장 → 아기/성체 동작 {body_count}/288개(각 4프레임).',
      '- 기본 이미지: 아기 36장(128×128), 성체 36장(160×160).',
      f'- 남은 원화 {len(missing_raw)}장 + 효과 {len(manifest["missingEffects"])}장.',
      '- 서버 함수와 Vercel 운영 버전은 이 변경으로 배포하지 않았습니다.',
      '- 이미지 도구가 알려준 한도 재설정: 2026-09-08 01:30:06 UTC (한국 10:30:06).','',
      '## 누락 원화','', '| 번호 | 모프 | 동작 |','|---|---|---|']
    for item in missing_raw: lines.append(f'| {item["morphId"]} | {item["name"]} | {item["action"]} |')
    lines += ['', '## 재개 절차','',
      '1. 원화 체크포인트 ZIP의 `art-source/cre36/raw`와 `prompts`를 저장소의 같은 위치에 복원합니다.',
      '2. `generate2dsprite` 스킬을 읽고 모프별 feed 원본을 `view_image`로 확인한 다음 built-in image_gen으로 누락 동작을 생성합니다. 기존 원화를 재사용하며, 동작마다 별도 2열×4행 시트(아기 4프레임/성체 4프레임)를 생성합니다.',
      '3. `prompts/fx-*.txt`의 네 효과를 별도 2×2 시트로 생성·처리하여 `public/assets/cre36/fx/{action}.png`에 둡니다. 가짜 CSS/SVG 그림이나 기존 동작 복제로 채우지 않습니다.',
      '4. `python scripts/process-cre36.py`로 투명 처리와 크기·위치 검사를 실행합니다. 처리기는 원화를 그리지 않고 픽셀 정리만 합니다. Python Pillow, NumPy가 필요하며 SciPy가 있으면 같은 마스크 처리가 빨라집니다.',
      '5. 각 단계의 색·무늬·비율·동작을 실제 이미지로 비교합니다. 특히 cre_035의 등 흰색 영역을 확인하고 필요하면 원화를 수정합니다. `quality-report.json`은 기계적 검사이며 시각적 일치의 보증이 아닙니다.',
      '6. `python scripts/pack-cre36.py` (partial 옵션 없이), `npm run check:sprites`, `npm test`, `npm run build`를 통과시킵니다. 현재 partial atlas의 빈 칸은 미완료 상태이므로 배포하지 않습니다.',
      '7. 전체 준비가 끝난 뒤 Supabase `buapfwbukpremwaksahr`의 `cre-terrarium`에 index.ts와 _shared/pet-handler.ts, pet.ts, morph-catalog.ts를 함께 배포합니다. 기존 함수의 내부 getUser 인증과 verify_jwt=false 설정을 유지합니다. 계정이나 저장 데이터를 초기화하지 않습니다.',
      '8. 원격 main 변경을 확인하여 충돌을 해결하고, GitHub main에 반영 후 Vercel 배포 성공 상태를 확인합니다. 현재 Vercel 연결 도구의 프로젝트 목록에는 ai-text-rpg가 보이지 않아 GitHub의 Vercel 상태를 통해 배포를 추적했습니다.',
      '', '## 완료된 검증','',
      '- TypeScript 검사와 Vite UI 컴파일 성공.',
      '- 확률 구간·부화 결과 보존·계정별 저장 분리·동시 부화·프록시 인증 관련 자동 검사 10개 통과.',
      '- `npm run build`는 미완료 세트의 운영 배포를 막도록 의도적으로 누락 검사에서 중단됩니다.',
      '- 실제 운영 로그인 및 36종 부화 서버 검증은 아직 진행하지 않았습니다.','']
    (ART/'RESUME.md').write_text('\n'.join(lines))
    available=args.output_dir/'cre36-available-sprites.zip'
    with zipfile.ZipFile(available,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(PUBLIC.glob('cre_*/*/*')):
            if p.suffix in ['.png','.gif']:z.write(p,str(p.relative_to(ROOT/'public/assets')))
        for p in sorted((ROOT/'public/assets/geckos').glob('*/*.png')):z.write(p,str(p.relative_to(ROOT/'public/assets')))
        for p in [ART/'RESUME.md',ART/'checkpoint-status.json',ART/'quality-report.json',ART/'prompts.json']:
            z.write(p,p.name)
    original=args.output_dir/'cre36-source-checkpoint.zip'
    with zipfile.ZipFile(original,'w',zipfile.ZIP_STORED) as z:
        for p in raw_files+sorted((ART/'prompts').glob('*.txt'))+[ART/'spec-v2.json',ART/'checkpoint-status.json',ART/'RESUME.md']:
            z.write(p,str(p.relative_to(ROOT)))
    print(json.dumps({'status':status['status'],'forms':status['forms'],'bodyAnimations':body_count,'missingRawSheets':len(missing_raw),'files':[str(available),str(original)]},ensure_ascii=False))

if __name__=='__main__':main()
