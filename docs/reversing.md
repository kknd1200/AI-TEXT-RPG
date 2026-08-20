# 어떻게 알아냈나

나중에 다시 파고들 때를 위한 기록입니다.

## APK 구조

```
com.ensony.battlemonster3 / label "Monster3K" / versionName 1.0.4
├── classes.dex          KT 올레마켓 결제 SDK + JNI 브리지 (게임 로직 아님)
├── lib/armeabi[-v7a]/libjccvt.so   ← 게임 본체 (두 파일 내용 동일)
└── assets/              맵(.mif/.mdt), 스프라이트(.ani/.fbm), 이벤트(.cht/.qst),
                         아이템 테이블(item_*.dat), 사운드(.ogg) 등 1474개
```

원래 피처폰(J2ME/GNEX)용 게임을 JCCVT 라는 변환기로 안드로이드 네이티브로
옮긴 물건입니다. 그래서 게임 로직 전체가 `libjccvt.so` 안의 ARM 코드입니다.

## 결정적인 행운: 심볼이 살아 있음

`libjccvt.so` 에 `.symtab` 이 그대로 남아 있습니다 (심볼 6313개).
함수 이름이 원본 그대로라 사실상 주석 달린 소스를 읽는 것과 비슷합니다.

```bash
python3 tools/dump_symbols.py libjccvt.so Net_ Online_Unknown
```

- `Net_*REQUEST` / `Net_*RECEIVE` — 명령별 송수신
- `Online_Unknown_*` — **미지의 섬** 화면들 ("unknown" = 미지)
- `EFC_net*` / `MC_net*` — 소켓 계층
- `EFC_fsRead* / EFC_fsWrite*` — 직렬화 헬퍼

## 접속 정보 찾기

`strings` 로 `218.50.3.88` 을 발견했지만, 이 문자열을 가리키는 포인터가
파일 어디에도 없었습니다. PIC 코드라 문자열 주소를 `.got` 기준 오프셋
(GOTOFF) 으로 들고 있기 때문입니다. `문자열주소 - .got주소` 를 계산해서
`.text` 를 뒤지니 `EFC_netSET` 한 곳에서 나왔습니다.

```bash
python3 tools/disasm.py libjccvt.so EFC_netSET
```

```
ldr r0, [pc, #0x28]   ; GOT+ -> "218.50.3.88"
adds r0, r4, r0
bl  MC_utilInetAddrInt
str r0, [r5, #4]      ; NetData->addr
ldr r0, [pc, #0x18]   ; =0x139a (5018)
bl  MC_utilHtons
strh r0, [r5, #8]     ; NetData->port
```

`MC_netSocket` 이 `socket(AF_INET, SOCK_STREAM, 0)` 을 부르므로 TCP 입니다.

## 패킷 포맷

`Net_SetPACKET1` 이 헤더를 쓰는 순서를 그대로 읽으면 됩니다. 버퍼를
`payload + 0x2f` 크기로 잡고, 길이 필드에 `payload + 0x22` 를 넣습니다.
0x2f - 0x22 = 13 이 길이 필드 앞부분 크기와 정확히 맞아떨어집니다.

응답은 `Net_dataRECEIVE` 가 `'E','N','S'` 를 한 바이트씩 비교하며 스캔한 뒤
`u16` 명령 ID, `u16` 길이를 읽고 `Net_SetRECEIVE` 로 결과 코드를 확인합니다.

## 명령 ID와 페이로드 레이아웃 자동 추출

각 `Net_*REQUEST` 는 `EFC_fsWrite*` 를 순서대로 부른 뒤 마지막에
`Net_SetPACKET1/2` 를 호출하고, 그때 `r0` 가 명령 ID입니다.
`Net_*RECEIVE` 는 `EFC_fsRead*` 를 순서대로 부릅니다.
그래서 Thumb 코드를 훑으며 레지스터 상수만 따라가면 레이아웃이 그대로 나옵니다.

```bash
python3 tools/extract_protocol.py libjccvt.so
python3 tools/extract_protocol.py libjccvt.so --filter unknown
```

이 출력이 [protocol.md](protocol.md) 표의 원본이고,
`server/ensserver/handlers.py` 도 여기에 맞춰 작성돼 있습니다.

## 화면 ↔ 명령 연결

어떤 UI가 어떤 패킷을 보내는지는 호출 그래프로 확인했습니다.
예를 들어 `Online_Unknown_Target_mRun → Net_unknown_4REQUEST`(0x124),
`Online_Unknown_List_mKeyPressed → Net_unknown_3REQUEST`(0x123) 처럼
미지의 섬 화면이 정확히 0x121~0x127 을 쓴다는 걸 이걸로 확정했습니다.

## 다음에 파볼 것

- `Online_netDrawMessage` @0x4e381 — 결과 코드별 화면 문구. 여기서
  에러 코드 표를 뽑을 수 있습니다.
- `OnlineCanvas_Link` @0x4dce5 — 화면 전환 테이블. 0x121/0x122/0x126 을
  언제 보내는지 정확한 순서가 여기 있습니다.
- `assets/item_*.dat`, `evt*.qst` — 아이템/퀘스트 테이블. 서버가 아이템을
  검증하려면 필요합니다.
