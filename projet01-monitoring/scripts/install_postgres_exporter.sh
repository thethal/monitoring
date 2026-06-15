#!/usr/bin/env bash
# =============================================================================
#  install_postgres_exporter.sh — Installe postgres_exporter sur srv-db01
#  Usage :  sudo bash install_postgres_exporter.sh
# =============================================================================
set -euo pipefail

VERSION="0.15.0"
ARCH="linux-amd64"
DB_PASSWORD="12345678"

echo "==> Téléchargement de postgres_exporter ${VERSION}"
cd /tmp
wget -q "https://github.com/prometheus-community/postgres_exporter/releases/download/v${VERSION}/postgres_exporter-${VERSION}.${ARCH}.tar.gz"
tar xzf "postgres_exporter-${VERSION}.${ARCH}.tar.gz"

echo "==> Installation du binaire"
cp "postgres_exporter-${VERSION}.${ARCH}/postgres_exporter" /usr/local/bin/
chmod +x /usr/local/bin/postgres_exporter

echo "==> Création du service systemd"
cat > /etc/systemd/system/postgres_exporter.service <<EOF
[Unit]
Description=Prometheus PostgreSQL Exporter
After=network-online.target postgresql.service

[Service]
User=postgres
Environment="DATA_SOURCE_NAME=postgresql://exporter:${DB_PASSWORD}@localhost:5432/postgres?sslmode=disable"
ExecStart=/usr/local/bin/postgres_exporter
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

echo "==> Démarrage du service"
systemctl daemon-reload
systemctl enable --now postgres_exporter

sleep 3
echo "==> Vérification :"
systemctl is-active postgres_exporter \
    && echo "  postgres_exporter : http://$(hostname -I | awk '{print $1}'):9187/metrics" \
    || echo "  ❌ postgres_exporter inactif — vérifier : journalctl -u postgres_exporter"
echo "==> Terminé."