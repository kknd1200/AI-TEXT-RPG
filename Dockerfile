# 클라우드 호스팅(Railway · Render · Fly.io · Koyeb 등)용 이미지.
# 내 PC에 아무것도 설치하지 않고 GitHub 저장소만 연결하면 배포된다.
#
# 필요한 환경변수는 각 서비스의 대시보드에서 설정한다:
#   KIWOOM_APP_KEY / KIWOOM_APP_SECRET
#   TELEGRAM_BOT_TOKEN / TELEGRAM_ALLOWED_CHAT_IDS

FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY krflow ./krflow

RUN pip install --no-cache-dir -e .

# 컨테이너 파일시스템은 재시작 시 날아가므로 토큰·구독 캐시는 /tmp 에 둔다.
ENV KRFLOW_HOME=/tmp/krflow \
    PYTHONUNBUFFERED=1

# $PORT 가 주입되면 bot 이 헬스체크 서버를 함께 띄운다 (웹 서비스 요건 충족용).
CMD ["krflow", "bot", "--provider", "kiwoom"]
