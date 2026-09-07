# 크레키우기 (Cre Growing Pixel)

Repository: `kknd1200/AI-TEXT-RPG`

웹게임용 GitHub → Supabase → Vercel 구조의 기준 프로젝트입니다.

## 포함된 것
- 36종 모프 이름/설명/정확한 부화 확률(JSON, 합계 100%)
- 36종 × 아기/성체 = 72개의 픽셀 크레 변형을 `PixelGecko` 렌더러로 정확하게 매칭
- Supabase 진행 저장 스키마 + RLS
- 서버 측 확률 추첨 `cre_hatch()` RPC
- 서버 측 돌보기/성장 `cre_care_action()` RPC
- React/Vite 모바일 대응 UI + 사육장 / 내 크레 / 36종 도감
- Vercel 배포용 설정 및 계정 프록시

## 구조
```text
src/data/morphs.json
src/components/PixelGecko.jsx
src/services/game.js
src/services/auth.js
supabase/migrations/
api/cre-account.js
```

## Supabase
현재 프로젝트 ref: `buapfwbukpremwaksahr`

브라우저에는 publishable key만 사용하며 service role/secret key는 프론트 코드에 넣지 않습니다.

## Vercel 환경변수
- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_PUBLISHABLE_KEY`
- `SUPABASE_URL`
- `CRE_SERVER_KEY`

## 로컬 실행
```bash
npm install
npm run dev
```

GitHub push → Vercel 자동 재배포 구조를 기준으로 운영합니다.
