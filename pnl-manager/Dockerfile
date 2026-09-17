# 단일 컨테이너 배포 — 프런트엔드를 빌드해 백엔드가 같은 오리진에서 서빙한다.
# 포트가 하나여서 관리형 호스팅(Fly.io·Render·Railway 등)에 그대로 올라간다.

# ── 1단계: 프런트엔드 빌드
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── 2단계: 실행 이미지
FROM python:3.12-slim AS app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PNL_DATA_DIR=/data \
    PNL_STATIC_DIR=/app/static \
    PNL_SECURE_COOKIES=1

WORKDIR /app

COPY backend/requirements.txt backend/requirements-postgres.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-postgres.txt

COPY backend/app ./app
COPY backend/scripts ./scripts
COPY --from=web /web/dist ./static

# 업로드 이미지와 SQLite 파일이 놓이는 경로. 클라우드에서는 영속 볼륨을 마운트한다.
RUN mkdir -p /data/uploads && \
    useradd --create-home --uid 10001 pnl && \
    chown -R pnl:pnl /data /app
USER pnl

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"

# PORT는 관리형 호스팅이 주입하는 경우가 많아 그대로 따른다.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
