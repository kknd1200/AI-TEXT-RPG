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

## 리소스 포맷 (.fbm / .ani / item_mon.dat)

웹 게임에 원작 그래픽을 쓰려고 나중에 추가로 푼 것들이다.
구현은 `tools/fbm.py`, `tools/ani.py`, `tools/rip_monsters.py`, `tools/rip_tiles.py`.

### .fbm — 이미지 묶음

```
0      u8   버전
1      u8   프레임 수 N
2..    u32×N  각 프레임의 파일 오프셋

프레임 헤더 9바이트:
 +0 u8  피벗 X (= w/2)      +1 u8  피벗 Y (= h/2)     +2 u8  플래그
 +3 u16 너비                +5 u16 높이
 +7 u8  1이면 팔레트가 뒤따름, 0이면 앞 프레임 팔레트를 그대로 씀
 +8 u8  팔레트 개수 - 1     (팔레트가 없으면 이 바이트는 쓰레기값)
팔레트: RGB0 4바이트 × 개수, 0번은 항상 #ff00ff = 투명
픽셀:   8비트 인덱스
```

두 군데서 막혔었다.

- **행 스트라이드가 4바이트 정렬이다.** 너비를 그대로 스트라이드로 쓰면
  이미지가 대각선으로 밀린다. 팔레트가 있는 프레임은 `9 + 4×팔레트 + 정렬폭×높이`가
  파일 길이와 **정확히** 맞아떨어져서 이걸로 확인했다.
- **행 순서가 아래에서 위다** (BMP식). 안 뒤집으면 그림이 거꾸로 나온다.

팔레트가 없는 프레임도 헤더는 9바이트 그대로다. `+8`을 픽셀로 읽으면
팔레트 범위를 넘는 인덱스가 나와서 금방 티가 난다.

### .ani — 파트 조립

```
0..3  "ANI\0"      4 u8 버전      5 u8 엔트리 수 N      6.. u32×N 엔트리 오프셋
엔트리 0 = 프레임 목록: u8 M, u32×M 프레임 오프셋
프레임: u16 ?, u8 레코드 수 K, 그 뒤 10바이트 레코드 × K
레코드: [0] 0  [1..2] s16 x  [3] 0  [4..5] s16 y
        [6] 플래그  [7] .fbm 파트 번호  [8] ?  [9] 1
```

`[6]`은 비트 0이 "그린다", 비트 1이 "좌우 반전". 첫 레코드는 늘 `[6]==0`인
메타 레코드라 그리면 안 된다 — 안 걸러내면 몸통이 두 번 겹쳐 그려진다.
파트는 자기 피벗을 기준으로 (x, y)에 놓인다.

다만 **몬스터 스프라이트는 .ani 조립을 쓰지 않았다.** 프레임 0이 무기나
이펙트 파트까지 끌어와서 지저분해지는 개체가 많았는데, 어차피 각 .fbm 안에
전투용 전신 스프라이트가 파트 하나로 들어 있어서 그걸 골라 쓰는 편이 훨씬 깨끗했다
(`tools/rip_monsters.py`의 `best_sprite`).

### item_mon.dat — 몬스터 이름과 고유기술

```
0     u8   몬스터 수 (132)
1..   u32×132  레코드 오프셋
레코드: [길이+이름] [0x01] [u32 자기참조] [길이+"기술명/설명"] [0x00] [u32] [0×4]
```

문자열은 CP949. 속성과 능력치는 이 파일에 없다 — 웹 게임에서는 이름 규칙으로
속성을 배정하고 능력치는 따로 계산한다.

### 맵 타일셋

맵마다 `mN_0` ~ `mN_7.fbm` 여러 장으로 나뉘어 있다. 첫 필드 맵 기준으로

| 페이지 | 내용 |
|---|---|
| `m0_0` | 잔디 변주, 수풀, 꽃 (13×3) |
| `m0_1` | 연못 가장자리 |
| `m0_2` | 절벽·바위 |
| `m0_3` | 길 가장자리 |
| `m0_4` | 투명 배경 오버레이 — 키풀, 바위, 꽃, 결정 (7×7) |
| `m0_5` | 흙길·모래 |
| `m0_6` | 물 |
| `m0_7` | 절벽과 물의 경계 |

타일은 16×16이고, 맵 데이터 `.mdt`는 `u8 너비, u8 높이` 뒤에 타일 인덱스가 이어진다
(첫 맵은 40×30).

## 다음에 파볼 것

- `Online_netDrawMessage` @0x4e381 — 결과 코드별 화면 문구. 여기서
  에러 코드 표를 뽑을 수 있습니다.
- `OnlineCanvas_Link` @0x4dce5 — 화면 전환 테이블. 0x121/0x122/0x126 을
  언제 보내는지 정확한 순서가 여기 있습니다.
- `assets/item_*.dat`, `evt*.qst` — 아이템/퀘스트 테이블. 서버가 아이템을
  검증하려면 필요합니다.
