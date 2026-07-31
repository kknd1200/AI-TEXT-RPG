# krflow — 국내장 외국인·기관 실시간 수급 상위 모니터

코스피/코스닥에서 **외국인·기관 순매수(순매도) 상위 종목**을 실시간으로 확인하는 프로그램입니다.
**텔레그램 봇**, 터미널 대시보드, 브라우저 대시보드를 제공하고 JSON/CSV로 내보낼 수 있습니다.

```
📈 전체 · 외국인+기관 순매수 상위          ╭─────────────── krflow ───────────────╮
순매수 금액 기준 (억원) · 13:24 · 장중     │ 실시간 수급 상위  전체 · 외국인+기관 │
                                           │ 소스: 키움증권 REST API · 장중       │
 # 종목         외인   기관   합계         │  #  종목       코드     외국인  기관 │
────────────────────────────────           │  1  삼성전자   005930   +920.0 -175.0│
 1 SK하이닉스 +382.6  +59.2 +441.8         │  2  SK하이닉스 000660    -99.0 +237.6│
 2 LG에너지…  +332.9  +47.3 +380.2         ╰──────────────────────────────────────╯
 3 NAVER      +247.8  +95.4 +343.2
[외국인][기관][● 합산] [🔄]                 (텔레그램 · 터미널 · 브라우저)
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

증권사 Open API 키가 필요합니다. 둘 중 아무거나 하나 있으면 됩니다.

**키움증권 REST API** — https://openapi.kiwoom.com → 로그인 → 앱 등록 → 앱키/시크릿키

**한국투자증권 KIS** — https://apiportal.koreainvestment.com → 로그인 → `My Page > 앱 등록`

```bash
cp .env.example .env
# .env 를 열어 KIWOOM_APP_KEY / KIWOOM_APP_SECRET (또는 KIS_*) 입력
```

```bash
krflow watch                    # provider=auto → 키움 → KIS → 네이버 순 자동 선택
krflow providers                # 현재 사용 가능한 소스와 설정 상태 확인
```

키가 하나도 없으면 `auto`는 네이버 금융 스크래핑으로 넘어갑니다.

> 키움은 **REST API**(앱키+시크릿) 전용입니다. 구버전 **OpenAPI+ (OCX/COM)** 는 윈도우 32비트
> 파이썬 + PyQt5 전용이라 지원하지 않습니다. REST 쪽은 OS 제약이 없어 서버에서 24시간 돌릴 수 있습니다.

## 텔레그램 봇

폰으로 받아보는 게 목적이면 이쪽이 제일 편합니다.

**1. 봇 만들기** — 텔레그램에서 [@BotFather](https://t.me/BotFather) 에게 `/newbot` 을 보내고
이름을 정하면 `123456:ABC-DEF...` 형태의 토큰을 줍니다. `.env` 에 넣으세요.

```
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_ALLOWED_CHAT_IDS=
```

**2. 내 chat_id 알아내기** — 그대로 실행하고 봇에게 아무 메시지나 보내면 chat_id 를 알려줍니다.

```bash
krflow bot
```

**3. chat_id 를 `.env` 에 넣고 다시 실행**

```
TELEGRAM_ALLOWED_CHAT_IDS=123456789
```

```bash
krflow bot --provider kiwoom
```

> `TELEGRAM_ALLOWED_CHAT_IDS` 를 비워두면 **아무도 쓸 수 없습니다.** 봇 토큰만 알면 누구나
> 말을 걸 수 있기 때문에, 허용 목록을 명시적으로 지정하게 해두었습니다.
> 그룹방에 넣을 때는 음수 chat_id 를 추가하세요.

### 봇 명령어

| 명령 | 설명 |
| --- | --- |
| `/top` | 현재 설정으로 수급 상위 조회 |
| `/watch 5` | 장중(08:50~15:40)에 5분마다 자동 전송 |
| `/stop` | 자동 전송 해제 |
| `/daily on` | 장 시작(09:05)·마감(15:35) 요약 자동 전송 |
| `/status` | 현재 설정과 구독 상태 |
| `/help` | 도움말 |

조회 조건(외국인/기관/합산, 순매수/순매도, 금액/수량, 시장, 순위 개수)은 메시지 아래
**인라인 버튼**으로 바로 바꿉니다. 버튼을 누르면 새 메시지를 쌓지 않고 그 자리에서 갱신됩니다.
설정과 구독 상태는 `~/.krflow/telegram_state.json` 에 채팅방별로 저장되어 재시작해도 유지됩니다.

### 버튼이 안 눌릴 때

```bash
krflow bot --provider kiwoom --verbose
```

`--verbose` 를 붙이면 버튼을 누를 때마다 `버튼 수신: data=...` 이 터미널에 찍힙니다.

| 터미널에 찍히는 것 | 원인 | 해결 |
| --- | --- | --- |
| `다른 곳에서 이미 실행 중입니다` | **봇을 두 군데서 실행 중** (가장 흔함) | 다른 터미널 창·서버의 `krflow bot` 을 끄세요 |
| 아무것도 안 찍힘 | 봇 프로세스가 꺼져 있음 | 터미널에 `krflow bot` 이 떠 있는지 확인 |
| `버튼 수신` 은 찍히는데 화면이 그대로 | 데이터 소스 오류 | 같이 찍히는 오류 메시지를 확인 |

버튼은 **봇이 실행 중일 때만** 동작합니다. 터미널을 닫으면 메시지에 버튼은 남아 있지만
누를 사람이 없어져서 반응하지 않습니다. GitHub Actions(`krflow push`)로 받은 메시지에는
같은 이유로 버튼이 붙지 않습니다.

## 내 PC에 아무것도 설치하지 않고 쓰기

폴더를 만들기 싫거나 PC를 계속 켜두기 어렵다면 두 가지 방법이 있습니다.

### 방법 A. GitHub Actions — 서버도 PC도 필요 없음

GitHub가 정해진 시각에 대신 실행해서 텔레그램으로 보내줍니다. **설치할 게 하나도 없습니다.**
대신 버튼·명령어 같은 대화형 기능은 없고, 정해진 시각에 오는 알림만 받습니다.

1. 이 저장소를 본인 계정으로 **Fork**
2. `Settings > Secrets and variables > Actions > New repository secret` 에서 4개 등록
   - `KIWOOM_APP_KEY`, `KIWOOM_APP_SECRET`
   - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_CHAT_IDS`
3. `Actions` 탭 → `수급 알림 (텔레그램)` → `Enable workflow`
4. `Run workflow` 로 바로 한 번 눌러보면 텔레그램에 도착합니다

기본 스케줄은 **평일 장중 30분마다**입니다. 주기를 바꾸려면
[`.github/workflows/krflow-telegram.yml`](.github/workflows/krflow-telegram.yml) 의
`cron` 을 고치세요 (UTC 기준, KST = UTC+9).

> Actions 스케줄은 GitHub 부하에 따라 몇 분 늦게 실행될 수 있고, 저장소가 비공개면
> 무료 실행 시간이 소진될 수 있습니다. 공개 저장소면 무제한입니다.
> 매 실행이 새 프로세스라 키움 토큰을 매번 새로 발급합니다.

### 방법 B. 클라우드 호스팅 — 대화형 봇을 24시간

`Dockerfile` 이 들어 있어서 Railway·Render·Fly.io·Koyeb 같은 곳에 GitHub 저장소만
연결하면 배포됩니다. 이쪽은 버튼과 `/watch` 까지 전부 동작합니다.

1. 이 저장소를 Fork
2. 호스팅 서비스에서 `Deploy from GitHub` → Fork한 저장소 선택 (Dockerfile 자동 인식)
3. 대시보드의 환경변수(Environment Variables)에 4개 입력
   - `KIWOOM_APP_KEY`, `KIWOOM_APP_SECRET`
   - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_CHAT_IDS`
4. 배포 완료

무료 요금제가 "포트를 여는 웹 서비스"만 받아주는 경우가 많은데, `$PORT` 가 주입되면
봇이 헬스체크 서버를 함께 띄우므로 그대로 통과합니다.

> 컨테이너 파일시스템은 재시작하면 초기화됩니다. `/watch`·`/daily` 구독 상태가
> 재배포 때 사라지므로, 재배포 후 한 번 더 등록하세요.

### 한눈에 비교

| | 설치 | 대화형 버튼 | `/watch` | 비용 |
| --- | --- | --- | --- | --- |
| 내 PC (`krflow bot`) | 필요 | ✅ | ✅ | 무료 (PC 켜둬야 함) |
| GitHub Actions | **불필요** | ❌ | 고정 스케줄로 대체 | 무료 |
| 클라우드 호스팅 | **불필요** | ✅ | ✅ | 서비스별 상이 |

## 명령어

| 명령 | 설명 |
| --- | --- |
| `krflow bot` | 텔레그램 봇 실행 (대화형, 계속 켜둬야 함) |
| `krflow push` | 텔레그램으로 1회 전송 후 종료 (cron·GitHub Actions용) |
| `krflow watch` | 터미널에서 주기적으로 갱신하며 표시 |
| `krflow once` | 1회 조회 후 출력 / `--json` / `--csv` 저장 |
| `krflow serve` | 브라우저 대시보드 실행 |
| `krflow providers` | 데이터 소스 목록과 설정 상태 |

### 공통 옵션

| 옵션 | 값 | 기본 | 설명 |
| --- | --- | --- | --- |
| `--provider` | `auto` `kiwoom` `kis` `naver` `krx` `mock` | `auto` | 데이터 소스 |
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

# 텔레그램 봇을 코스닥 전용으로
krflow bot --provider kiwoom --market kosdaq
```

## 데이터 소스 비교

| provider | 실시간성 | 키 | 비고 |
| --- | --- | --- | --- |
| `kiwoom` | 장중 실시간 집계 | 필요 | 키움 REST API. 외국인기관매매상위(`ka90009`). 시세 열은 없음 |
| `kis` | 장중 실시간 **가집계** | 필요 | 한투. 종목별 외국인·기관 순매수 수량/금액 + 시세 |
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
- `.env` 는 `.gitignore` 에 포함되어 있습니다. 앱키와 봇 토큰을 커밋하지 마세요.
- 텔레그램 봇의 자동 전송은 **평일 08:50~15:40** 에만 동작합니다. 장 시작/마감 요약은
  예정 시각(09:05 / 15:35)을 놓쳐도 30분 안에 봇이 살아나면 한 번 따라잡아 보냅니다.
- 이 프로그램은 정보 조회용입니다. 주문·매매 기능은 없으며, 투자 판단의 책임은 사용자에게 있습니다.

### 서버에서 24시간 돌리기

`krflow bot` 은 롱폴링 방식이라 공인 IP나 웹훅 설정이 필요 없습니다. 리눅스 서버라면
systemd 로 올려두면 됩니다.

```ini
# /etc/systemd/system/krflow-bot.service
[Unit]
Description=krflow telegram bot
After=network-online.target

[Service]
WorkingDirectory=/opt/krflow
ExecStart=/opt/krflow/.venv/bin/krflow bot --provider kiwoom
Restart=always
RestartSec=10
User=krflow

[Install]
WantedBy=multi-user.target
```

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
  cache.py           소스 호출을 주기당 1회로 묶는 스냅샷 캐시
  fmt.py             표시 포맷 (콘솔·웹·텔레그램 공용)
  providers/         kiwoom · kis · naver · krx · mock
  bot/telegram.py    텔레그램 봇 (롱폴링 + 스케줄러)
  bot/render.py      텔레그램 메시지·인라인 키보드
  bot/store.py       채팅방별 설정·구독 영속화
  ui/console.py      rich 터미널 대시보드
  ui/web.py          표준 라이브러리 기반 웹 대시보드
```

새 소스를 붙이려면 `providers/base.py` 의 `Provider` 를 상속해 `fetch()` 가
`Snapshot` 을 돌려주도록 만들고 `providers/__init__.py` 의 `create()` 에 등록하면 됩니다.
