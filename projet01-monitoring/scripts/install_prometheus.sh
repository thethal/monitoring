#!/usr/bin/env bash
# =============================================================================
#  install_prometheus.sh — Installe Prometheus + AlertManager (srv-monitor)
#  À exécuter UNIQUEMENT sur le serveur de monitoring (192.168.56.10).
#  Usage :  sudo bash install_prometheus.sh
#
#  Pré-requis : déposer prometheus.yml, alert.rules.yml et alertmanager.yml
#  dans le même dossier que ce script (ou ajuster les chemins de copie).
# =============================================================================
set -euo pipefail

PROM_VERSION="2.53.1"     # Prometheus LTS
AM_VERSION="0.27.0"       # AlertManager
ARCH="linux-amd64"
SRC="$(cd "$(dirname "$0")/.." && pwd)"   # racine du projet (chemin absolut)

echo "==> Arrêt des services existants (si actifs)"
systemctl stop prometheus alertmanager 2>/dev/null || true

echo "==> Création des utilisateurs et répertoires"
id prometheus &>/dev/null || useradd --no-create-home --shell /usr/sbin/nologin prometheus
mkdir -p /etc/prometheus /var/lib/prometheus
mkdir -p /etc/alertmanager /var/lib/alertmanager

# --------------------------- PROMETHEUS -------------------------------------
echo "==> Installation de Prometheus ${PROM_VERSION}"
cd /tmp
wget -q "https://github.com/prometheus/prometheus/releases/download/v${PROM_VERSION}/prometheus-${PROM_VERSION}.${ARCH}.tar.gz"
tar xzf "prometheus-${PROM_VERSION}.${ARCH}.tar.gz"
cd "prometheus-${PROM_VERSION}.${ARCH}"

# Binaires + bibliothèques de consoles.
cp prometheus promtool /usr/local/bin/
cp -r consoles console_libraries /etc/prometheus/ 

# Fichiers de configuration du projet.
cp "${SRC}/prometheus/prometheus.yml"   /etc/prometheus/
cp "${SRC}/prometheus/alert.rules.yml"  /etc/prometheus/

# Droits.
chown -R prometheus:prometheus /etc/prometheus /var/lib/prometheus /usr/local/bin/prometheus /usr/local/bin/promtool

# Vérification de la configuration AVANT de démarrer (bonne pratique).
echo "==> Validation de la configuration Prometheus :"
promtool check config /etc/prometheus/prometheus.yml

# Service systemd Prometheus.
cat > /etc/systemd/system/prometheus.service <<'EOF'
[Unit]
Description=Prometheus Time Series Server
Wants=network-online.target
After=network-online.target

[Service]
User=prometheus
Group=prometheus
Type=simple
# --storage.tsdb.retention.time=30d : conserve 30 jours d'historique (capacité).
ExecStart=/usr/local/bin/prometheus \
    --config.file=/etc/prometheus/prometheus.yml \
    --storage.tsdb.path=/var/lib/prometheus/ \
    --storage.tsdb.retention.time=30d \
    --web.listen-address=:9090
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

# --------------------------- ALERTMANAGER -----------------------------------
echo "==> Installation d'AlertManager ${AM_VERSION}"
cd /tmp
wget -q "https://github.com/prometheus/alertmanager/releases/download/v${AM_VERSION}/alertmanager-${AM_VERSION}.${ARCH}.tar.gz"
tar xzf "alertmanager-${AM_VERSION}.${ARCH}.tar.gz"
cp "alertmanager-${AM_VERSION}.${ARCH}/alertmanager" /usr/local/bin/
cp "${SRC}/alertmanager/alertmanager.yml" /etc/alertmanager/
chown -R prometheus:prometheus /etc/alertmanager /var/lib/alertmanager /usr/local/bin/alertmanager

cat > /etc/systemd/system/alertmanager.service <<'EOF'
[Unit]
Description=Prometheus AlertManager
Wants=network-online.target
After=network-online.target

[Service]
User=prometheus
Group=prometheus
Type=simple
ExecStart=/usr/local/bin/alertmanager \
    --config.file=/etc/alertmanager/alertmanager.yml \
    --storage.path=/var/lib/alertmanager/ \
    --web.listen-address=:9093
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

# --------------------------- DÉMARRAGE --------------------------------------
echo "==> Démarrage des services"
systemctl daemon-reload
systemctl enable prometheus alertmanager
systemctl restart prometheus alertmanager

sleep 3
echo "==> Vérifications :"
systemctl is-active prometheus   && echo "  Prometheus   : http://192.168.56.10:9090"
systemctl is-active alertmanager && echo "  AlertManager : http://192.168.56.10:9093"
echo "==> Terminé."
