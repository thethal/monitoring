#!/usr/bin/env python3
# =============================================================================
#  app.py — Application web de démonstration « boutique-api »
#  Rôle : générer un VRAI trafic HTTP instrumenté pour alimenter le dashboard
#         Golden Signals (Latence, Trafic, Erreurs) avec des données réelles.
#  Hôte : srv-web01 (192.168.56.11), expose /metrics sur le port 8000.
#
#  Dépendances :  pip install flask prometheus-client   (cf. requirements.txt)
#  Lancement     :  python3 app.py        (ou via le service systemd fourni)
#
#  Métriques exposées (format Prometheus) :
#     http_requests_total              (Counter)   -> Trafic & Erreurs (RED)
#     http_request_duration_seconds    (Histogram) -> Latence P50/P95/P99
#     http_requests_in_progress        (Gauge)     -> Saturation applicative
# =============================================================================
import random
import time
from flask import Flask, request, Response
from prometheus_client import (
    Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
)

app = Flask(__name__)

# -----------------------------------------------------------------------------
# 1. DÉFINITION DES MÉTRIQUES
# -----------------------------------------------------------------------------

# Counter : ne fait qu'augmenter. On calcule un débit avec rate() côté PromQL.
# Les labels method/endpoint/status permettent de filtrer (ex : status=~"5..").
HTTP_REQUESTS = Counter(
    "http_requests_total",
    "Nombre total de requêtes HTTP traitées",
    ["method", "endpoint", "status"],
)

# Histogram : répartit les durées en "buckets" pour calculer les percentiles.
# Les buckets (en secondes) sont choisis autour de notre seuil cible (0,5 s).
HTTP_DURATION = Histogram(
    "http_request_duration_seconds",
    "Durée de traitement des requêtes HTTP (secondes)",
    ["method", "endpoint"],
    buckets=(0.01, 0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 1.0, 2.5, 5.0),
)

# Gauge : valeur instantanée qui monte et descend (requêtes en cours).
HTTP_IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "Nombre de requêtes HTTP en cours de traitement",
    ["endpoint"],
)


# -----------------------------------------------------------------------------
# 2. SIMULATION DE CHARGE
#    Chaque endpoint simule un temps de traitement et un taux d'erreur
#    différents, afin que le dashboard Golden Signals montre des courbes variées.
# -----------------------------------------------------------------------------
ENDPOINTS = {
    "/":         {"latence": 0.05, "taux_erreur": 0.005},  # page d'accueil, rapide
    "/produits": {"latence": 0.15, "taux_erreur": 0.01},   # catalogue, moyen
    "/panier":   {"latence": 0.25, "taux_erreur": 0.02},   # panier, plus lourd
    "/paiement": {"latence": 0.40, "taux_erreur": 0.06},   # paiement, lent + erreurs
}


def traiter_requete(endpoint):
    """Simule le travail métier : un délai + parfois une erreur 500."""
    profil = ENDPOINTS[endpoint]
    # Latence aléatoire centrée sur la valeur du profil (distribution réaliste).
    delai = random.gauss(profil["latence"], profil["latence"] * 0.3)
    delai = max(0.005, delai)          # jamais négatif
    time.sleep(delai)
    # Tirage d'une erreur selon le taux configuré.
    erreur = random.random() < profil["taux_erreur"]
    return ("500" if erreur else "200"), delai


# -----------------------------------------------------------------------------
# 3. ROUTES APPLICATIVES (instrumentées)
# -----------------------------------------------------------------------------
@app.route("/")
@app.route("/produits")
@app.route("/panier")
@app.route("/paiement")
def page():
    endpoint = request.path
    HTTP_IN_PROGRESS.labels(endpoint=endpoint).inc()       # +1 requête en cours
    # Le context manager de l'histogramme mesure automatiquement la durée.
    with HTTP_DURATION.labels(method=request.method, endpoint=endpoint).time():
        status, _ = traiter_requete(endpoint)
    HTTP_REQUESTS.labels(
        method=request.method, endpoint=endpoint, status=status
    ).inc()                                                # compte la requête
    HTTP_IN_PROGRESS.labels(endpoint=endpoint).dec()       # -1 requête en cours

    if status == "500":
        return Response("Erreur interne du serveur", status=500)
    return Response(f"OK — {endpoint}", status=200)


# -----------------------------------------------------------------------------
# 4. ENDPOINT /metrics — exposé pour Prometheus
# -----------------------------------------------------------------------------
@app.route("/metrics")
def metrics():
    # generate_latest() produit toutes les métriques au format texte Prometheus.
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    # threaded=True : permet plusieurs requêtes simultanées (pour voir l'in-flight).
    # host=0.0.0.0 : écoute sur toutes les interfaces (accessible depuis le réseau).
    app.run(host="0.0.0.0", port=8000, threaded=True)
