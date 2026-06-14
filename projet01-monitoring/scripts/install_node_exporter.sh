#!/usr/bin/env bash
# =============================================================================
#  install_node_exporter.sh — Installe Node Exporter en service systemd
#  À exécuter sur CHACUN des 3 nœuds (srv-monitor, srv-web01, srv-db01).
#  Usage :  sudo bash install_node_exporter.sh
# =============================================================================
set -euo pipefail   # -e: stoppe à la 1re erreur ; -u: variable non définie = erreur ;
                    # -o pipefail: une erreur dans un pipe fait échouer le pipe.

VERSION="1.8.2"     # version de Node Exporter à installer
ARCH="linux-amd64"

echo "==> Installation de Node Exporter ${VERSION}"

# 1. Création d'un utilisateur système dédié, sans shell de connexion (sécurité).
if ! id node_exporter &>/dev/null; then
    useradd --no-create-home --shell /usr/sbin/nologin node_exporter
fi

# 2. Téléchargement et extraction de l'archive officielle.
cd /tmp
wget -q "https://github.com/prometheus/node_exporter/releases/download/v${VERSION}/node_exporter-${VERSION}.${ARCH}.tar.gz"
tar xzf "node_exporter-${VERSION}.${ARCH}.tar.gz"

# 3. Copie du binaire dans /usr/local/bin et attribution des droits.
cp "node_exporter-${VERSION}.${ARCH}/node_exporter" /usr/local/bin/
chown node_exporter:node_exporter /usr/local/bin/node_exporter
chmod 755 /usr/local/bin/node_exporter

# 4. Installation de l'unité systemd (fournie dans node_exporter/).
#    On suppose que le fichier node_exporter.service est dans le même dossier.
cp node_exporter/node_exporter.service /etc/systemd/system/ 2>/dev/null \
    || echo "  (placez node_exporter.service dans /etc/systemd/system/ manuellement avec sudo)"

# 5. Activation et démarrage du service.
systemctl daemon-reload
systemctl enable --now node_exporter

# 6. Vérification : la cible doit répondre sur le port 9100.
sleep 2
echo "==> Vérification :"
systemctl is-active node_exporter && echo "  Node Exporter actif sur :9100"
curl -s http://localhost:9100/metrics | head -3

echo "==> Terminé. Pensez à autoriser le port 9100 dans le pare-feu si nécessaire :"
echo "    sudo ufw allow from 192.168.56.10 to any port 9100 proto tcp"
