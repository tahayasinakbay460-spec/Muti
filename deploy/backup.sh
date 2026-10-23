#!/bin/sh
# Veritabanının günlük yedeği. Son 14 gün saklanır, eskiler silinir.
# Her gece 04:00'te kendiliğinden çalışması için (crontab -e ile eklenir):
#   0 4 * * * /root/Muti/deploy/backup.sh >> /root/Muti/deploy/backups/backup.log 2>&1
# Geri yüklemek için:
#   gunzip -c backups/muti-TARIH.sql.gz | docker compose exec -T db psql -U muti muti
set -e
cd "$(dirname "$0")"
mkdir -p backups
docker compose exec -T db pg_dump -U muti muti | gzip > "backups/muti-$(date +%Y-%m-%d_%H%M).sql.gz"
find backups -name 'muti-*.sql.gz' -mtime +14 -delete
echo "$(date) yedek alındı"
