# Canlı sunucunun tarifi. Railway (ya da başka bir sunucu) bu dosyadan bir "kutu" (image)
# kurar: içinde Python, kütüphaneler, backend ve frontend kodu hazır durur.
FROM python:3.12-slim

# Python çıktıyı bekletmeden yazsın (loglar anında görünsün), .pyc dosyası üretmesin.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app/backend

# Önce yalnızca requirements: kod değişip kütüphaneler değişmediyse bu katman önbellekten gelir,
# her yayında paketler baştan indirilmez.
COPY backend/requirements.txt .
RUN pip install -r requirements.txt

COPY backend/ .
COPY frontend/ /app/frontend/

# Root (yönetici) olmayan bir kullanıcıyla çalış: kod bir açık yüzünden ele geçirilse bile
# sunucunun geri kalanına dokunamasın.
RUN useradd --create-home muti && chown -R muti /app
USER muti

ENV ENVIRONMENT=production \
    FRONTEND_DIR=/app/frontend \
    DEMO_MODE=false \
    ADMIN_CAN_READ_MESSAGES=false \
    LOG_JSON=true

# 1) Veritabanını güncelle (yeni migration varsa uygular, veri silinmez)
# 2) Sunucuyu aç. PORT'u Railway verir. --proxy-headers: Railway'in önündeki vekil sunucu
#    gerçek kullanıcı IP'sini X-Forwarded-For başlığıyla iletir (hız sınırı buna bakar).
CMD alembic upgrade head && \
    uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} \
      --proxy-headers --forwarded-allow-ips='*' --no-access-log
