# krflow — 국내장 외국인·기관 실시간 수급 상위 모니터

코스피/코스닥에서 **외국인·기관 순매수(순매도) 상위 종목**을 실시간으로 확인하는 프로그램입니다.
터미널 대시보드와 브라우저 대시보드를 모두 제공하고, JSON/CSV로 내보낼 수 있습니다.

```
╭──────────────────────────────── krflow ────────────────────────────────╮
│ 실시간 수급 상위  전체 · 외국인+기관 · 순매수 상위 · 순매수 금액 기준  │
│ 소스: 한국투자증권 KIS Open API (kis) | 장 상태: 장중 | 갱신: 13:24:05 │
│  #  종목            코드     현재가   등락률  외국인(억원) 기관(억원)  │
│  1  삼성전자        005930   74,500   +1.64%       +920.0     -175.0   │
│  2  SK하이닉스      000660  198,000   -1.74%        -99.0     +237.6   │
╰────────────────────────────────────────────────────────────────────────╯
```

## 설치

```bash
pip install -e .
# KRX 일별 확정치까지 쓰려면
pip install -e ".[krx]"
```

## 바로 실행해 보기 (키·네트워크 불필요)

```bash
krflow watch --provider mock          # 가상 데이터로 화면 확인
krflow serve --provider mock          # http://127.0.0.1:8765
```

## 실시간 데이터 연결하기

가장 정확한 실시간 소스는 **한국투자증권 KIS Open API**입니다. 무료이며 계좌만 있으면 됩니다.

1. https://apiportal.koreainvestment.com 접속 → 로그인 → `My Page > 앱 등록`
2. 앱키(App Key) / 앱시크릿(App Secret) 발급
3. 프로젝트 루트에 `.env` 작성

```bash
cp .env.example .env
# .env 를 열어 KIS_APP_KEY / KIS_APP_SECRET 입력
```

```bash
krflow watch                    # provider=auto → 키가 있으면 KIS 사용
krflow providers                # 현재 사용 가능한 소스와 설정 상태 확인
```

키가 없으면 `auto`는 자동으로 네이버 금융 스크래핑으로 넘어갑니다.

## 명령어

| 명령 | 설명 |
| --- | --- |
| `krflow watch` | 터미널에서 주기적으로 갱신하며 표시 |
| `krflow once` | 1회 조회 후 출력 / `--json` / `--csv` 저장 |
| `krflow serve` | 브라우저 대시보드 실행 |
| `krflow providers` | 데이터 소스 목록과 설정 상태 |

### 공통 옵션

| 옵션 | 값 | 기본 | 설명 |
| --- | --- | --- | --- |
| `--provider` | `auto` `kis` `naver` `krx` `mock` | `auto` | 데이터 소스 |
| `--market` | `all` `kospi` `kosdaq` | `all` | 시장 구분 |
| `--investor` | `both` `foreign` `inst` | `both` | 외국인 / 기관 / 합산 |
| `--metric` | `value` `qty` | `value` | 금액(억원) / 수량(천주) 기준 |
| `--side` | `buy` `sell` | `buy` | 순매수 상위 / 순매도 상위 |
| `--top` | 정수 | `20` | 표시 종목 수 |
| `--min-abs` | 실수 | `0` | 최소 \|순매수\| (금액=백만원, 수량=주) |
| `--interval` | 초 | `10` | 갱신 주기 (`watch` / `serve`) |

### 예시

```bash
# 코스피 외국인 순매수 상위 20종목, 10초마다 갱신
krflow watch --market kospi --investor foreign --top 20 --interval 10

# 코스닥 기관 순매도 상위를 수량 기준으로
krflow once --market kosdaq --investor inst --side sell --metric qty

# 100억 이상 순매수만 추려서 CSV 저장
krflow once --min-abs 10000 --csv flow.csv

# 브라우저 대시보드 (화면에서 투자자/기준/순위 전환 가능)
krflow serve --port 8765 --interval 10
```

## 데이터 소스 비교

| provider | 실시간성 | 키 | 비고 |
| --- | --- | --- | --- |
| `kis` | 장중 실시간 **가집계** | 필요 | 권장. 종목별 외국인·기관 순매수 수량/금액 + 시세 |
| `naver` | 장중 갱신 | 불필요 | 매수상위·매도상위 표를 조인해 순매수를 계산. 상위권 종목만 커버 |
| `krx` | 일별 **확정치** | 불필요 | `pykrx` 필요. 실시간 아님. 마감 후 검증용 |
| `mock` | — | 불필요 | 가상 데이터. UI 확인용 |

단위는 소스와 무관하게 내부에서 **수량=주, 금액=백만원**으로 정규화되며, 화면에는 **억원 / 천주**로 표시됩니다.
순매수는 양수(빨강), 순매도는 음수(파랑)입니다.

## 알아둘 점

- **장중 수치는 가집계(잠정치)** 입니다. 장 마감 후 거래소 확정치와 차이가 날 수 있으니,
  확정치가 필요하면 `--provider krx` 로 교차 확인하세요.
- 장 상태 표시는 주말만 휴장으로 처리합니다. **공휴일 휴장 캘린더는 반영하지 않습니다** —
  공휴일에는 갱신 시각이 멈춘 것으로 확인할 수 있습니다.
- `naver` provider는 공식 API가 아닌 HTML 스크래핑입니다. 페이지 구조가 바뀌면 파서 조정이 필요하고,
  과도한 폴링을 막기 위해 최소 갱신 주기가 15초로 제한됩니다.
- `.env` 는 `.gitignore` 에 포함되어 있습니다. 앱키를 커밋하지 마세요.
- 이 프로그램은 정보 조회용입니다. 주문·매매 기능은 없으며, 투자 판단의 책임은 사용자에게 있습니다.

## 개발

```bash
pip install -e ".[dev]"
pytest -q
```

구조:

```
krflow/
  models.py          FlowRow / Snapshot (단위 정규화 규약)
  ranking.py         정렬·필터·합계
  market.py          KST 장 운영시간
  config.py          .env / 환경변수
  fmt.py             표시 포맷 (콘솔·웹 공용)
  providers/         kis · naver · krx · mock
  ui/console.py      rich 터미널 대시보드
  ui/web.py          표준 라이브러리 기반 웹 대시보드
```

새 소스를 붙이려면 `providers/base.py` 의 `Provider` 를 상속해 `fetch()` 가
`Snapshot` 을 돌려주도록 만들고 `providers/__init__.py` 의 `create()` 에 등록하면 됩니다.
