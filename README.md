# 크레키우기

`kknd1200/AI-TEXT-RPG`의 내용을 현재 픽셀 사육장 버전으로 교체한 Vercel 프로젝트입니다.
React + Vite, Vercel API, Supabase Auth·Postgres·Edge Functions를 사용합니다.

## 게임

- 알부터 시작합니다. 약 3분 동안 기다리거나 온기·분무·청소로 부화를 앞당길 수 있습니다.
- 8종의 굵은 도트 크레와 4프레임 애니메이션, 사육장 한 곳, 먹이·분무·청소·놀이를 제공합니다.
- 베이비 → 아성체 → 성체로 성장합니다. 새 알을 받으면 기존 크레를 보관하고 다시 선택할 수 있습니다.
- 돌봄 직후와 매분 자동 저장하며, 수동 저장과 재로그인 불러오기를 제공합니다.
- 부화 확률은 패턴리스 30%, 플레임 24%, 타이거 18%, 달마시안 12%, 할리퀸 8%, 트라이컬러 5%, 릴리 화이트 2.5%, 아잔틱 0.5%입니다. 게임용 독립 추첨이며 실제 유전 확률이 아닙니다.

## 계정과 저장

아이디·비밀번호로 가입하고 로그인합니다. 가입 시 표시되는 복구 코드로 비밀번호를 재설정할 수 있습니다. 복구 코드는 확인 버튼을 누를 때까지 화면에 남습니다.

기존 `cre_accounts`와 동일한 Supabase Auth 계정을 사용하므로 계정 UUID와 기존 비밀번호가 유지됩니다. 이메일 연결을 위한 기존 프로필 필드도 유지합니다. 실제 이메일 연결 화면은 아직 없습니다.

성장 기록은 `cre_terrarium_saves`에 저장합니다. 계정에 연결된 이전 사육장 기록은 데이터베이스에 옮겼으며, 기존 RPG 및 이전 도감 테이블을 삭제하지 않았습니다. 이번 화면은 8종 사육장 버전입니다.

브라우저의 로그인 토큰은 Supabase SDK가 저장·갱신합니다. 서버는 매 게임 요청에서 Supabase Auth와 `cre_accounts` 소속을 확인합니다. 브라우저는 게임 상태를 직접 수정할 수 없으며, 서버가 돌봄과 부화 결과를 계산합니다. 동시 요청은 revision 비교로 한 번만 저장합니다.

## Vercel 설정

GitHub `main`에 연결된 기존 Vercel `ai-text-rpg` 프로젝트로 자동 배포합니다. `vercel.json`에 Vite 빌드와 API 경로 설정을 포함했습니다.

| 환경변수 | 용도 |
| --- | --- |
| `SUPABASE_URL` | 서버 프로젝트 URL. 현재 연결 프로젝트를 기본값으로 사용합니다. |
| `SUPABASE_PUBLISHABLE_KEY` | 서버에서 사용하며 `VITE_SUPABASE_PUBLISHABLE_KEY`도 지원합니다. |
| `VITE_SUPABASE_URL` | 브라우저 프로젝트 URL |
| `VITE_SUPABASE_PUBLISHABLE_KEY` | 브라우저 공개 키. 서비스 역할 키를 넣으면 안 됩니다. |

계정 요청은 `cre-public-account` 함수에서 처리하므로 Vercel에 별도 계정 서버 키를 설정할 필요가 없습니다. 공개 가입, 비밀번호 검증 로그인, 복구 코드 재설정만 허용하고 아이디와 게이트웨이 IP를 기준으로 시도를 제한합니다. 클라이언트가 제출한 IP는 사용하지 않습니다. 기존 키를 사용하는 `cre-account` 함수는 다른 클라이언트를 위해 유지합니다.

현재 연결된 Supabase 프로젝트는 `buapfwbukpremwaksahr`입니다. 신규 환경에는 `supabase/terrarium.sql`을 적용하고 `supabase/functions/cre-terrarium`과 `supabase/functions/cre-public-account`를 배포합니다. `cre-public-account`는 로그인 비밀번호 또는 복구 코드를 함수 내부에서 직접 검증하는 공개 계정 API이므로 `verify_jwt=false`를 사용합니다.

`cre-terrarium`은 함수 내부의 `auth.getUser(token)`과 계정 조회로 인증하므로 게이트웨이 `verify_jwt=false`로 배포합니다. 서비스 역할 키는 Supabase 함수 내부에서만 사용합니다. 이 키를 Vercel이나 브라우저에 복사할 필요는 없습니다.

## 개발·검증

```bash
npm ci
npm test
npm run build
npm run dev
```

`npm run dev`는 프론트 개발용입니다. 계정·저장 API를 포함한 로컬 확인에는 Vercel 개발 환경과 환경변수가 필요합니다. 운영 Supabase 키를 저장소에 커밋하지 마세요.

자동 테스트는 확률 구간, 알 돌봄, 성장, 저장·재조회, 계정별 분리, 동시 부화, Vercel 계정 프록시와 요청 출처 검증을 확인합니다. 로컬 API 테스트의 인증 HTTP와 저장소는 대역을 사용하며 실제 브라우저 로그인 검증을 대신하지 않습니다.
# 36종 돌봄 애니메이션 작업본 — 최종 배포 전

이 브랜치는 크레 36종 × 아기/성체 72종의 도트 원화와 돌봄 애니메이션을 통합하는 작업본입니다. 이미지 생성 한도로 전체 세트가 아직 완성되지 않았습니다. 운영 게임에 반영된 버전으로 안내하면 안 됩니다.

- 정리된 원화: 104장. 아기/성체별 4프레임 동작 208개.
- 기본 PNG: 아기 36장(128×128), 성체 36장(160×160).
- GitHub의 생성 PNG 원본은 `art-source/cre36/runtime-sprites.tar.gz`에 묶었습니다. 빌드가 원래 경로에 자동 복원합니다. 개발 시 `node scripts/restore-cre36.mjs`로도 복원할 수 있습니다.
- 남은 원화: 분무·청소·놀기 40장(아기/성체 동작 80개), 돌봄 효과 4장.
- 자세한 누락 목록과 재개 절차: `art-source/cre36/RESUME.md`.
- `npm run build`는 누락된 동작이나 효과가 있으면 중단합니다. 개발 중 타입 검사와 UI 컴파일은 `node node_modules/typescript/bin/tsc --noEmit`, `node node_modules/vite/bin/vite.js build`로 따로 실행할 수 있습니다.
- 부화 서버의 36종 목록은 아직 Supabase 운영 함수에 배포하지 않았습니다. 전체 그림 검수와 프런트 배포 준비가 끝난 다음 함께 반영해야 합니다.
