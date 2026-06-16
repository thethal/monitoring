#!/usr/bin/env python3
"""
=============================================================================
  fake_exporter.py — Faux exporter HTTP pour simuler les alertes Grafana
  Projet : E-Service Linux — Livrable L3
  Auteurs : Thales & MBA ONDO Dieudonné (INGC2 - IAI Libreville)
=============================================================================

  Ce script lance un petit serveur HTTP sur le port 9200 qui expose
  des métriques au format Prometheus. Prometheus vient scraper ce serveur
  exactement comme il scraperait un vrai Node Exporter ou une vraie app.

  UTILISATION :
    # Déclencher toutes les alertes
    python3 fake_exporter.py --mode all

    # Déclencher une seule alerte
    python3 fake_exporter.py --mode cpu
    python3 fake_exporter.py --mode mem
    python3 fake_exporter.py --mode disk
    python3 fake_exporter.py --mode latency
    python3 fake_exporter.py --mode errors

    # Exposer des valeurs normales (aucune alerte)
    python3 fake_exporter.py --mode normal

    # Changer le port ou le hostname exposé
    python3 fake_exporter.py --mode all --port 9200 --hostname srv-web01

  Arrêt : Ctrl+C
=============================================================================
"""

import argparse
import time
from http.server import BaseHTTPRequestHandler, HTTPServer


# =============================================================================
#  Valeurs simulées par mode
# =============================================================================

MODES = {
    "normal": {
        "cpu_idle_ratio":       0.70,   # 30% de CPU utilisé   → pas d'alerte
        "mem_available_ratio":  0.50,   # 50% de RAM libre     → pas d'alerte
        "mem_total_bytes":      8 * 1024**3,
        "disk_avail_ratio":     0.60,   # 60% d'espace libre   → pas d'alerte
        "disk_size_bytes":      50 * 1024**3,
        "latency_p95_seconds":  0.15,   # 150 ms               → pas d'alerte
        "error_rate_pct":       0.5,    # 0.5% d'erreurs 5xx   → pas d'alerte
        "total_requests":       10000,
    },
    "cpu": {
        "cpu_idle_ratio":       0.08,   # 92% de CPU utilisé   → WARNING > 85%
        "mem_available_ratio":  0.50,
        "mem_total_bytes":      8 * 1024**3,
        "disk_avail_ratio":     0.60,
        "disk_size_bytes":      50 * 1024**3,
        "latency_p95_seconds":  0.15,
        "error_rate_pct":       0.5,
        "total_requests":       10000,
    },
    "mem": {
        "cpu_idle_ratio":       0.70,
        "mem_available_ratio":  0.07,   # 93% de RAM utilisée  → CRITICAL > 90%
        "mem_total_bytes":      8 * 1024**3,
        "disk_avail_ratio":     0.60,
        "disk_size_bytes":      50 * 1024**3,
        "latency_p95_seconds":  0.15,
        "error_rate_pct":       0.5,
        "total_requests":       10000,
    },
    "disk": {
        "cpu_idle_ratio":       0.70,
        "mem_available_ratio":  0.50,
        "mem_total_bytes":      8 * 1024**3,
        "disk_avail_ratio":     0.10,   # 10% d'espace libre   → WARNING < 15%
        "disk_size_bytes":      50 * 1024**3,
        "latency_p95_seconds":  0.15,
        "error_rate_pct":       0.5,
        "total_requests":       10000,
    },
    "latency": {
        "cpu_idle_ratio":       0.70,
        "mem_available_ratio":  0.50,
        "mem_total_bytes":      8 * 1024**3,
        "disk_avail_ratio":     0.60,
        "disk_size_bytes":      50 * 1024**3,
        "latency_p95_seconds":  0.75,   # 750 ms               → WARNING > 500 ms
        "error_rate_pct":       0.5,
        "total_requests":       10000,
    },
    "errors": {
        "cpu_idle_ratio":       0.70,
        "mem_available_ratio":  0.50,
        "mem_total_bytes":      8 * 1024**3,
        "disk_avail_ratio":     0.60,
        "disk_size_bytes":      50 * 1024**3,
        "latency_p95_seconds":  0.15,
        "error_rate_pct":       8.0,    # 8% d'erreurs 5xx     → CRITICAL > 5%
        "total_requests":       10000,
    },
    "all": {
        "cpu_idle_ratio":       0.08,   # → WARNING  CPU
        "mem_available_ratio":  0.07,   # → CRITICAL Mémoire
        "mem_total_bytes":      8 * 1024**3,
        "disk_avail_ratio":     0.10,   # → WARNING  Disque
        "disk_size_bytes":      50 * 1024**3,
        "latency_p95_seconds":  0.75,   # → WARNING  Latence P95
        "error_rate_pct":       8.0,    # → CRITICAL Erreurs 5xx
        "total_requests":       10000,
    },
}


# =============================================================================
#  Génération du payload Prometheus (format text exposition)
# =============================================================================

def build_metrics(hostname: str, v: dict) -> str:
    """
    Retourne une chaîne au format Prometheus text exposition.
    Ces métriques reprennent exactement les noms utilisés dans alerts.yml.
    """
    lines = []

    # ── Temps unix courant (utilisé pour les compteurs)
    now = time.time()

    # ─────────────────────────────────────────────────────────────────────────
    # 1. CPU — node_cpu_seconds_total{mode="idle"}
    #    Règle PromQL : 100 - (avg by(hostname)(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)
    #
    #    On simule deux CPUs (cpu="0" et cpu="1") dont le ratio idle correspond
    #    à cpu_idle_ratio. Prometheus calcule rate() sur la fenêtre [5m],
    #    donc on expose un compteur dont l'incrément par seconde = idle_ratio.
    #    Valeur du compteur = idle_ratio * timestamp (croissance linéaire).
    # ─────────────────────────────────────────────────────────────────────────
    idle = v["cpu_idle_ratio"]
    user = (1 - idle) * 0.7
    sys_ = (1 - idle) * 0.3

    lines += [
        "# HELP node_cpu_seconds_total Seconds the CPUs spent in each mode.",
        "# TYPE node_cpu_seconds_total counter",
        f'node_cpu_seconds_total{{hostname="{hostname}",cpu="0",mode="idle"}}   {idle  * now:.2f}',
        f'node_cpu_seconds_total{{hostname="{hostname}",cpu="0",mode="user"}}   {user  * now:.2f}',
        f'node_cpu_seconds_total{{hostname="{hostname}",cpu="0",mode="system"}} {sys_  * now:.2f}',
        f'node_cpu_seconds_total{{hostname="{hostname}",cpu="1",mode="idle"}}   {idle  * now:.2f}',
        f'node_cpu_seconds_total{{hostname="{hostname}",cpu="1",mode="user"}}   {user  * now:.2f}',
        f'node_cpu_seconds_total{{hostname="{hostname}",cpu="1",mode="system"}} {sys_  * now:.2f}',
    ]

    # ─────────────────────────────────────────────────────────────────────────
    # 2. Mémoire — node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes
    #    Règle PromQL : (1 - (MemAvailable / MemTotal)) * 100
    # ─────────────────────────────────────────────────────────────────────────
    mem_total = v["mem_total_bytes"]
    mem_avail = mem_total * v["mem_available_ratio"]

    lines += [
        "# HELP node_memory_MemTotal_bytes Memory information field MemTotal.",
        "# TYPE node_memory_MemTotal_bytes gauge",
        f'node_memory_MemTotal_bytes{{hostname="{hostname}"}} {mem_total:.0f}',
        "# HELP node_memory_MemAvailable_bytes Memory information field MemAvailable.",
        "# TYPE node_memory_MemAvailable_bytes gauge",
        f'node_memory_MemAvailable_bytes{{hostname="{hostname}"}} {mem_avail:.0f}',
    ]

    # ─────────────────────────────────────────────────────────────────────────
    # 3. Disque — node_filesystem_avail_bytes / node_filesystem_size_bytes
    #    Règle PromQL : (avail / size) * 100   avec mountpoint="/"
    # ─────────────────────────────────────────────────────────────────────────
    disk_size  = v["disk_size_bytes"]
    disk_avail = disk_size * v["disk_avail_ratio"]

    lines += [
        "# HELP node_filesystem_size_bytes Filesystem size in bytes.",
        "# TYPE node_filesystem_size_bytes gauge",
        f'node_filesystem_size_bytes{{hostname="{hostname}",mountpoint="/",fstype="ext4"}} {disk_size:.0f}',
        "# HELP node_filesystem_avail_bytes Filesystem space available to non-root users.",
        "# TYPE node_filesystem_avail_bytes gauge",
        f'node_filesystem_avail_bytes{{hostname="{hostname}",mountpoint="/",fstype="ext4"}} {disk_avail:.0f}',
    ]

    # ─────────────────────────────────────────────────────────────────────────
    # 4. Latence — http_request_duration_seconds (histogram)
    #    Règle PromQL : histogram_quantile(0.95, sum(rate(bucket[5m])) by (le))
    #
    #    On construit un histogram cohérent avec p95 ≈ latency_p95_seconds.
    #    Les buckets sont remplis de façon à ce que 95% des requêtes
    #    tombent en-dessous de la valeur simulée.
    # ─────────────────────────────────────────────────────────────────────────
    p95   = v["latency_p95_seconds"]
    total = v["total_requests"]

    # Distribution empirique : 50% < 100ms, 70% < 250ms, 94% < p95, 99% < 2*p95
    buckets = [
        (0.05,  int(total * 0.30)),
        (0.1,   int(total * 0.50)),
        (0.25,  int(total * 0.70)),
        (0.5,   int(total * 0.85)),
        (p95,   int(total * 0.95)),   # le bucket clé pour le P95
        (p95 * 2, int(total * 0.99)),
        ("+Inf", total),
    ]
    req_sum = sum(
        p95 * 0.30 * total * 0.30 +
        0.1  * total * 0.20 +
        0.25 * total * 0.20 +
        p95  * total * 0.10
        for _ in [1]
    )
    req_sum = p95 * total * 0.6  # approximation raisonnable

    lines += [
        "# HELP http_request_duration_seconds HTTP request latency.",
        "# TYPE http_request_duration_seconds histogram",
    ]
    for le, count in buckets:
        lines.append(
            f'http_request_duration_seconds_bucket{{hostname="{hostname}",le="{le}"}} '
            f'{int(count * now / 300)}'  # compteur croissant
        )
    lines += [
        f'http_request_duration_seconds_sum{{hostname="{hostname}"}}   {req_sum * now / 300:.2f}',
        f'http_request_duration_seconds_count{{hostname="{hostname}"}} {int(total * now / 300)}',
    ]

    # ─────────────────────────────────────────────────────────────────────────
    # 5. Erreurs HTTP — http_requests_total{status=~"5.."}
    #    Règle PromQL : (sum(rate(5xx[5m])) / sum(rate(total[5m]))) * 100
    # ─────────────────────────────────────────────────────────────────────────
    err_pct  = v["error_rate_pct"] / 100
    rps      = v["total_requests"] / 300   # requêtes/s simulées

    ok_count  = int(rps * (1 - err_pct) * now)
    err_count = int(rps * err_pct       * now)

    lines += [
        "# HELP http_requests_total Total HTTP requests by status.",
        "# TYPE http_requests_total counter",
        f'http_requests_total{{hostname="{hostname}",status="200"}} {ok_count}',
        f'http_requests_total{{hostname="{hostname}",status="500"}} {err_count}',
    ]

    return "\n".join(lines) + "\n"


# =============================================================================
#  Serveur HTTP minimal
# =============================================================================

class MetricsHandler(BaseHTTPRequestHandler):
    """Handler HTTP : répond uniquement sur GET /metrics."""

    hostname = "srv-web01"
    mode     = "all"

    def do_GET(self):
        if self.path != "/metrics":
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found. Use /metrics\n")
            return

        v       = MODES[self.mode]
        payload = build_metrics(self.hostname, v).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args):
        """Affiche les requêtes de scrape dans la console."""
        print(f"  [scrape] {self.address_string()} → {args[0]} {args[1]}")


# =============================================================================
#  Point d'entrée
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Faux exporter HTTP — simulateur d'alertes Grafana (IAI INGC2)"
    )
    parser.add_argument(
        "--mode",
        default="all",
        choices=list(MODES.keys()),
        help="Scénario à simuler (défaut: all)"
    )
    parser.add_argument(
        "--port",
        default=9200, type=int,
        help="Port d'écoute du faux exporter (défaut: 9200)"
    )
    parser.add_argument(
        "--hostname",
        default="srv-web01",
        help="Valeur du label hostname dans les métriques (défaut: srv-web01)"
    )
    args = parser.parse_args()

    # Injecter les paramètres dans le handler
    MetricsHandler.hostname = args.hostname
    MetricsHandler.mode     = args.mode

    v = MODES[args.mode]
    cpu_pct  = (1 - v["cpu_idle_ratio"])       * 100
    mem_pct  = (1 - v["mem_available_ratio"])  * 100
    disk_pct = v["disk_avail_ratio"]            * 100
    lat_ms   = v["latency_p95_seconds"]         * 1000
    err_pct  = v["error_rate_pct"]

    W = "\033[93m[WARNING] \033[0m"
    C = "\033[91m[CRITICAL]\033[0m"
    OK= "\033[92m[OK]      \033[0m"

    print("=" * 60)
    print("  Fake Exporter — E-Service Linux (IAI INGC2)")
    print("=" * 60)
    print(f"  Mode     : {args.mode}")
    print(f"  Hostname : {args.hostname}")
    print(f"  URL      : http://0.0.0.0:{args.port}/metrics")
    print()
    print("  Valeurs exposées :")
    print(f"  ├─ CPU        : {cpu_pct:.0f}%      {C if cpu_pct > 85 else OK}  (seuil > 85%)")
    print(f"  ├─ Mémoire    : {mem_pct:.0f}%      {C if mem_pct > 90 else OK}  (seuil > 90%)")
    print(f"  ├─ Disque /   : {disk_pct:.0f}% lib {W if disk_pct < 15 else OK}  (seuil < 15%)")
    print(f"  ├─ Latence P95: {lat_ms:.0f} ms   {W if lat_ms > 500 else OK}  (seuil > 500 ms)")
    print(f"  └─ Erreurs 5xx: {err_pct:.1f}%     {C if err_pct > 5 else OK}  (seuil > 5%)")
    print()
    print("  ⏳ Les alertes apparaissent après le délai 'for:' de chaque règle :")
    print("     Erreurs 5xx → 2 min | Latence → 3 min | CPU/RAM → 5 min | Disque → 10 min")
    print()
    print("  Ctrl+C pour arrêter (pense à retirer le job dans prometheus.yml)")
    print("-" * 60)

    server = HTTPServer(("0.0.0.0", args.port), MetricsHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n  Exporter arrêté.")
        print("  → Retire le job 'fake-exporter' de prometheus.yml puis :")
        print("    sudo systemctl reload prometheus")


if __name__ == "__main__":
    main()
