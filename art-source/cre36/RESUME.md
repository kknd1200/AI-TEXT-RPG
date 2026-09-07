# 크레 36종 동작 작업 재개

**전체 완료/운영 배포 전입니다.** 이미지 생성 한도로 중단됐으며 원화와 처리 결과를 보존했습니다.

- 생성 원화 104장 → 아기/성체 동작 208/288개(각 4프레임).
- 기본 이미지: 아기 36장(128×128), 성체 36장(160×160).
- 남은 원화 40장 + 효과 4장.
- 서버 함수와 Vercel 운영 버전은 이 변경으로 배포하지 않았습니다.
- 이미지 도구가 알려준 한도 재설정: 2026-09-08 01:30:06 UTC (한국 10:30:06).

## 누락 원화

| 번호 | 모프 | 동작 |
|---|---|---|
| cre_023 | WHITE LILLY WHITE | clean |
| cre_023 | WHITE LILLY WHITE | play |
| cre_024 | WHITE PINSTRIPE | mist |
| cre_024 | WHITE PINSTRIPE | play |
| cre_025 | BLACK PATTERNLESS | mist |
| cre_025 | BLACK PATTERNLESS | clean |
| cre_025 | BLACK PATTERNLESS | play |
| cre_026 | BLACK FLAME | mist |
| cre_026 | BLACK FLAME | clean |
| cre_026 | BLACK FLAME | play |
| cre_027 | LAVENDER BICOLOR | mist |
| cre_027 | LAVENDER BICOLOR | clean |
| cre_027 | LAVENDER BICOLOR | play |
| cre_028 | LAVENDER PINSTRIPE | mist |
| cre_028 | LAVENDER PINSTRIPE | clean |
| cre_028 | LAVENDER PINSTRIPE | play |
| cre_029 | RED HALLOWEEN | mist |
| cre_029 | RED HALLOWEEN | clean |
| cre_029 | RED HALLOWEEN | play |
| cre_030 | WHITE TRICOLOR | mist |
| cre_030 | WHITE TRICOLOR | clean |
| cre_030 | WHITE TRICOLOR | play |
| cre_031 | BLACK SUPER DALMATIAN | mist |
| cre_031 | BLACK SUPER DALMATIAN | clean |
| cre_031 | BLACK SUPER DALMATIAN | play |
| cre_032 | LAVENDER HARLEQUIN | mist |
| cre_032 | LAVENDER HARLEQUIN | clean |
| cre_032 | LAVENDER HARLEQUIN | play |
| cre_033 | WHITE EXTREME HARLEQUIN | mist |
| cre_033 | WHITE EXTREME HARLEQUIN | clean |
| cre_033 | WHITE EXTREME HARLEQUIN | play |
| cre_034 | GRAY AXANTHIC | mist |
| cre_034 | GRAY AXANTHIC | clean |
| cre_034 | GRAY AXANTHIC | play |
| cre_035 | BLACK LILLY WHITE | mist |
| cre_035 | BLACK LILLY WHITE | clean |
| cre_035 | BLACK LILLY WHITE | play |
| cre_036 | LAVENDER EXTREME HARLEQUIN | mist |
| cre_036 | LAVENDER EXTREME HARLEQUIN | clean |
| cre_036 | LAVENDER EXTREME HARLEQUIN | play |

## 재개 절차

1. 원화 체크포인트 ZIP의 `art-source/cre36/raw`와 `prompts`를 저장소의 같은 위치에 복원합니다.
2. `generate2dsprite` 스킬을 읽고 모프별 feed 원본을 `view_image`로 확인한 다음 built-in image_gen으로 누락 동작을 생성합니다. 기존 원화를 재사용하며, 동작마다 별도 2열×4행 시트(아기 4프레임/성체 4프레임)를 생성합니다.
3. `prompts/fx-*.txt`의 네 효과를 별도 2×2 시트로 생성·처리하여 `public/assets/cre36/fx/{action}.png`에 둡니다. 가짜 CSS/SVG 그림이나 기존 동작 복제로 채우지 않습니다.
4. `python scripts/process-cre36.py`로 투명 처리와 크기·위치 검사를 실행합니다. 처리기는 원화를 그리지 않고 픽셀 정리만 합니다. Python Pillow, NumPy가 필요하며 SciPy가 있으면 같은 마스크 처리가 빨라집니다.
5. 각 단계의 색·무늬·비율·동작을 실제 이미지로 비교합니다. 특히 cre_035의 등 흰색 영역을 확인하고 필요하면 원화를 수정합니다. `quality-report.json`은 기계적 검사이며 시각적 일치의 보증이 아닙니다.
6. `python scripts/pack-cre36.py` (partial 옵션 없이), `npm run check:sprites`, `npm test`, `npm run build`를 통과시킵니다. 현재 partial atlas의 빈 칸은 미완료 상태이므로 배포하지 않습니다.
7. 전체 준비가 끝난 뒤 Supabase `buapfwbukpremwaksahr`의 `cre-terrarium`에 index.ts와 _shared/pet-handler.ts, pet.ts, morph-catalog.ts를 함께 배포합니다. 기존 함수의 내부 getUser 인증과 verify_jwt=false 설정을 유지합니다. 계정이나 저장 데이터를 초기화하지 않습니다.
8. 원격 main 변경을 확인하여 충돌을 해결하고, GitHub main에 반영 후 Vercel 배포 성공 상태를 확인합니다. 현재 Vercel 연결 도구의 프로젝트 목록에는 ai-text-rpg가 보이지 않아 GitHub의 Vercel 상태를 통해 배포를 추적했습니다.

## 완료된 검증

- TypeScript 검사와 Vite UI 컴파일 성공.
- 확률 구간·부화 결과 보존·계정별 저장 분리·동시 부화·프록시 인증 관련 자동 검사 10개 통과.
- `npm run build`는 미완료 세트의 운영 배포를 막도록 의도적으로 누락 검사에서 중단됩니다.
- 실제 운영 로그인 및 36종 부화 서버 검증은 아직 진행하지 않았습니다.
