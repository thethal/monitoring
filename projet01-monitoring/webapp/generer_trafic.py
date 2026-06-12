#!/usr/bin/env python3
# =============================================================================
#  generer_trafic.py — Petit injecteur de charge pour la démonstration
#  Envoie des requêtes en continu vers boutique-api afin que les courbes
#  Golden Signals (trafic, latence, erreurs) soient bien visibles dans Grafana.
#
#  Usage :  python3 generer_trafic.py [http://192.168.56.11:8000] [req_par_seconde]
#  Arrêt :  Ctrl + C
# =============================================================================
import sys
import time
import random
import threading
import urllib.request

# Cible et intensité paramétrables en ligne de commande.
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://192.168.56.11:8000"
RPS = int(sys.argv[2]) if len(sys.argv) > 2 else 20   # requêtes par seconde

ENDPOINTS = ["/", "/produits", "/panier", "/paiement"]


def envoyer():
    """Envoie une requête vers un endpoint tiré au hasard (pondéré)."""
    # On visite plus souvent l'accueil et le catalogue que le paiement (réaliste).
    endpoint = random.choices(ENDPOINTS, weights=[5, 4, 2, 1])[0]
    try:
        urllib.request.urlopen(BASE + endpoint, timeout=5)
    except Exception:
        # Les erreurs 500 simulées lèvent une exception HTTP : c'est normal.
        pass


print(f"Injection de ~{RPS} req/s vers {BASE}  (Ctrl+C pour arrêter)")
try:
    while True:
        # Lance RPS requêtes réparties sur 1 seconde, en parallèle.
        for _ in range(RPS):
            threading.Thread(target=envoyer, daemon=True).start()
            time.sleep(1.0 / RPS)
except KeyboardInterrupt:
    print("\nArrêt de l'injection.")
