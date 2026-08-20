# 서버 띄우고 접속하기

## 1. 서버 실행

파이썬 3.10 이상만 있으면 됩니다. 외부 패키지 필요 없습니다.

```bash
python3 server/main.py                       # 0.0.0.0:5018
python3 server/main.py --db /var/lib/ens.db --record packets.jsonl -v
```

- `--port` : 기본 5018. 클라이언트에 박혀 있는 포트라 바꾸면 클라이언트도 같이 패치해야 합니다.
- `--db` : SQLite 파일 경로 (기본 `ens.db`).
- `--record` : 오간 패킷을 전부 JSONL 로 기록. 필드 의미를 더 파낼 때 씁니다.

방화벽에서 TCP 5018 을 열어 주세요. 집에서 돌린다면 공유기 포트포워딩,
밖에서 붙게 하려면 고정 IP 나 저렴한 VPS 하나면 충분합니다
(동시 접속이 수십 명 수준이면 가장 싼 인스턴스로도 남습니다).

## 2. 클라이언트를 내 서버로 돌리기

클라이언트는 서버 주소 `218.50.3.88` 과 포트 5018 을 **네이티브 코드 안에
상수로** 들고 있습니다. 게다가 문자열을 `inet_addr()` 에 넘기기 때문에
도메인 이름은 쓸 수 없고 IPv4 주소여야 합니다.

```bash
python3 tools/patch_client.py 원본.apk 203.0.113.10 -o monster3k-private.apk
python3 tools/patch_client.py 원본.apk 192.168.0.42 --port 5018
```

패처가 하는 일은 [protocol.md](protocol.md) 와 스크립트 상단 주석에
적어 뒀습니다. 요약하면 `EFC_netSET` 에서 문자열 조회를 없애고
주소 상수를 직접 넣는 방식이라, **길이 제한 없이 아무 IPv4 나** 넣을 수 있습니다.
`lib/armeabi` 와 `lib/armeabi-v7a` 두 개를 모두 고칩니다.

### 서명

APK 를 고치면 원래 서명은 깨집니다. 패처는 서명 파일을 지운 채로 내보내니
직접 다시 서명해야 설치됩니다.

```bash
# 키스토어가 없다면 한 번만
keytool -genkey -v -keystore ens.jks -keyalg RSA -keysize 2048 \
        -validity 10000 -alias ens

# Android SDK build-tools 의 apksigner 사용
zipalign -p -f 4 monster3k-private.apk monster3k-aligned.apk
apksigner sign --ks ens.jks --out monster3k-signed.apk monster3k-aligned.apk
apksigner verify monster3k-signed.apk
```

`apksigner` 가 없으면 [uber-apk-signer](https://github.com/patrickfav/uber-apk-signer)
같은 단일 JAR 도구가 편합니다.

기존에 설치된 원본 앱과는 서명이 달라서 **덮어쓰기 설치가 안 됩니다.**
원본을 지우고 설치하거나(세이브가 날아갈 수 있음), 패키지명을 바꾼 별도
빌드를 쓰세요.

## 3. 플레이어 식별자 (중요)

이 게임의 계정은 **단말 전화번호**입니다. `EFC_mainInitialize` 가 시스템 속성
`PHONENUMBER` 를 읽어 21바이트 식별자로 쓰고, 모델명에 `Emulator` 가 들어 있으면
**`01123456789` 로 고정**해 버립니다.

즉:

- 에뮬레이터 여러 대로 접속하면 **전부 같은 플레이어**가 됩니다.
- 요즘 안드로이드는 `getLine1Number()` 가 대부분 빈 값이라
  `NET_NOT_FOUND_PHONENUMBER` 로 막힐 수 있습니다.

해결 방법은 두 가지입니다.

1. **사람마다 다른 APK 를 빌드** — 지금 패처가 건드리는 것과 같은 방식으로
   기본 번호 문자열을 각자 다르게 바꿔 배포. 가장 손이 덜 갑니다.
2. **자바 쪽을 고치기** — `PHONENUMBER` 응답은 `MC_knlGetSystemProperty` →
   JNI → `com.ensony.battlemonster3.Monster3K.getPhoneNumber()` 로 올라갑니다.
   apktool 로 smali 를 고쳐서 `Settings.Secure.ANDROID_ID` 나 설정 파일 값을
   돌려주게 하면 설치마다 자동으로 고유해집니다. (이쪽은 아직 이 저장소에
   구현돼 있지 않습니다.)

## 4. 서버 없이 동작 확인

단말 없이 서버만 검증하려면 동봉된 가짜 클라이언트를 쓰세요.
게임과 **동일한 헤더**로 패킷을 만듭니다.

```bash
python3 server/main.py --db /tmp/test.db &

python3 tools/fake_client.py --phone 01011112222 walkthrough
python3 tools/fake_client.py --phone 01033334444 walkthrough
python3 tools/fake_client.py --phone 01011112222 send 0x122
```

두 번째 플레이어의 walkthrough 에서 `island_count` 가 1 이상으로 나오고
`island_target` 이 상대 식별자를 돌려주면, 서로가 보이는 상태입니다.

테스트:

```bash
python3 -m pytest tests -q
```
