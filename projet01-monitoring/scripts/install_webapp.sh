#!/usr/bin/env bash
# =============================================================================
#  install_webapp.sh — Déploie l'application boutique-api en service systemd
#  À exécuter sur srv-web01 (192.168.56.11).
#  Usage :  sudo bash install_webapp.sh
# =============================================================================
set -euo pipefail
SRC="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Installation des dépendances système"
apt-get update -qq
apt-get install -y python3 python3-pip >/dev/null
pip3 install virtualenv --break-system-packages

echo "==> Déploiement de l'application dans /opt/boutique-api"
mkdir -p /opt/boutique-api
cp "${SRC}/webapp/app.py" "${SRC}/webapp/requirements.txt" /opt/boutique-api/

# Environnement virtuel Python isolé (bonne pratique).
virtualenv /opt/boutique-api/venv
/opt/boutique-api/venv/bin/pip install -q -r /opt/boutique-api/requirements.txt

# Utilisateur dédié sans privilèges.
id webapp &>/dev/null || useradd --no-create-home --shell /usr/sbin/nologin webapp
chown -R webapp:webapp /opt/boutique-api

echo "==> Création du service systemd"
cat > /etc/systemd/system/boutique-api.service <<'EOF'
[Unit]
Description=boutique-api (application web instrumentee Prometheus)
After=network-online.target

[Service]
User=webapp
Group=webapp
Type=simple
WorkingDirectory=/opt/boutique-api
# On lance via gunicorn (4 workers) pour un comportement proche de la production.
ExecStart=/opt/boutique-api/venv/bin/gunicorn --workers 4 --bind 0.0.0.0:8000 app:app
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now boutique-api

sleep 3
echo "==> Vérification :"
systemctl is-active boutique-api && echo "  boutique-api : http://192.168.56.11:8000  (/metrics pour Prometheus)"
curl -s http://localhost:8000/metrics | grep -E "http_requests_total|http_request_duration" | head -3
echo "==> Terminé."
