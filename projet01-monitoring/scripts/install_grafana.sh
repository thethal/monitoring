#!/usr/bin/env bash
# =============================================================================
#  install_grafana.sh — Installe Grafana et déploie le provisioning as-code
#  À exécuter sur srv-monitor (192.168.56.10).
#  Usage :  sudo bash install_grafana.sh
#
#  Le provisioning copie automatiquement : datasource Prometheus, dashboards
#  (USE + Golden Signals) et alertes natives (L4). Aucun clic requis ensuite.
# =============================================================================
set -euo pipefail
SRC="$(dirname "$0")/.."   # racine du projet

echo "==> Ajout du dépôt officiel Grafana"
apt-get install -y apt-transport-https wget gnupg >/dev/null
mkdir -p /etc/apt/keyrings
wget -q -O - https://apt.grafana.com/gpg.key | gpg --dearmor | tee /etc/apt/keyrings/grafana.gpg >/dev/null
echo "deb [signed-by=/etc/apt/keyrings/grafana.gpg] https://apt.grafana.com stable main" \
    > /etc/apt/sources.list.d/grafana.list

echo "==> Installation de Grafana"
apt-get update -qq
apt-get install -y grafana >/dev/null

echo "==> Déploiement du provisioning as-code (livrables L2, L3, L4)"
# 1. Datasource Prometheus.
cp "${SRC}/grafana/provisioning/datasources/datasources.yml" \
   /etc/grafana/provisioning/datasources/

# 2. Fichier de chargement des dashboards.
cp "${SRC}/grafana/provisioning/dashboards/dashboards.yml" \
   /etc/grafana/provisioning/dashboards/

# 3. Dossier des dashboards JSON + dépôt des deux dashboards.
mkdir -p /var/lib/grafana/dashboards
cp "${SRC}/grafana/dashboards/use-method.json"     /var/lib/grafana/dashboards/
cp "${SRC}/grafana/dashboards/golden-signals.json" /var/lib/grafana/dashboards/

# 4. Alerting unifié (5 alertes natives + contact Slack + politique).
mkdir -p /etc/grafana/provisioning/alerting
cp "${SRC}/grafana/provisioning/alerting/"*.yaml /etc/grafana/provisioning/alerting/

# Droits pour l'utilisateur grafana.
chown -R grafana:grafana /var/lib/grafana/dashboards /etc/grafana/provisioning

echo "==> Démarrage de Grafana"
systemctl daemon-reload
systemctl enable --now grafana-server

sleep 5
echo "==> Vérification :"
systemctl is-active grafana-server && echo "  Grafana : http://192.168.56.10:3000  (admin/admin au 1er login)"
echo "==> Terminé. Les dashboards apparaissent dans le dossier 'E-Service Linux'."
