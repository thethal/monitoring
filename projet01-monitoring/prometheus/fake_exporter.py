#!/usr/bin/env python3
"""
=============================================================================
  fake_exporter.py — Faux exporter HTTP pour simuler les alertes Grafana
  Projet : E-Service Linux — Livrable L3
  Auteurs : Thales & MBA ONDO Dieudonné (INGC2 - IAI Libreville)
=============================================================================

  UTILISATION :
    python3 fake_exporter.py --mode all
    python3 fake_exporter.py --mode cpu
    python3 fake_exporter.py --mode mem
    python3 fake_exporter.py --mode disk
    python3 fake_exporter.py --mode latency
    python3 fake_exporter.py --mode errors
    python3 fake_exporter.py --mode normal

  Arrêt : Ctrl+C  →  retirer le job dans prometheus.yml puis reload
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
        "cpu_idle_ratio":      0.70,   # CPU à 30%        → OK
        "mem_available_ratio": 0.50,   # RAM à 50% libre  → OK
        "mem_total_bytes":     8 * 1024**3,
        "disk_avail_ratio":    0.60,   # 60% libre        → OK
        "disk_size_bytes":     50 * 1024**3,
        "latency_p95_seconds": 0.15,   # 150 ms           → OK
        "error_rate_pct":      0.5,    # 0.5% erreurs     → OK
        "total_requests":      10000,
        "in_progress":         5,
    },
    "cpu": {
        "cpu_idle_ratio":      0.08,   # CPU à 92%        → WARNING > 85%
        "mem_available_ratio": 0.50,
        "mem_total_bytes":     8 * 1024**3,
        "disk_avail_ratio":    0.60,
        "disk_size_bytes":     50 * 1024**3,
        "latency_p95_seconds": 0.15,
        "error_rate_pct":      0.5,
        "total_requests":      10000,
        "in_progress":         5,
    },
    "mem": {
        "cpu_idle_ratio":      0.70,
        "mem_available_ratio": 0.07,   # RAM à 93%        → CRITICAL > 90%
        "mem_total_bytes":     8 * 1024**3,
        "disk_avail_ratio":    0.60,
        "disk_size_bytes":     50 * 1024**3,
        "latency_p95_seconds": 0.15,
        "error_rate_pct":      0.5,
        "total_requests":      10000,
        "in_progress":         5,
    },
    "disk": {
        "cpu_idle_ratio":      0.70,
        "mem_available_ratio": 0.50,
        "mem_total_bytes":     8 * 1024**3,
        "disk_avail_ratio":    0.10,   # 10% libre        → WARNING < 15%
        "disk_size_bytes":     50 * 1024**3,
        "latency_p95_seconds": 0.15,
        "error_rate_pct":      0.5,
        "total_requests":      10000,
        "in_progress":         5,
    },
    "latency": {
        "cpu_idle_ratio":      0.70,
        "mem_available_ratio": 0.50,
        "mem_total_bytes":     8 * 1024**3,
        "disk_avail_ratio":    0.60,
        "disk_size_bytes":     50 * 1024**3,
        "latency_p95_seconds": 0.75,   # 750 ms           → WARNING > 500 ms
        "error_rate_pct":      0.5,
        "total_requests":      10000,
        "in_progress":         45,     # beaucoup de req en cours → saturation visible
    },
    "errors": {
        "cpu_idle_ratio":      0.70,
        "mem_available_ratio": 0.50,
        "mem_total_bytes":     8 * 1024**3,
        "disk_avail_ratio":    0.60,
        "disk_size_bytes":     50 * 1024**3,
        "latency_p95_seconds": 0.15,
        "error_rate_pct":      8.0,    # 8% erreurs 5xx   → CRITICAL > 5%
        "total_requests":      10000,
        "in_progress":         5,
    },
    "all": {
        "cpu_idle_ratio":      0.08,   # → WARNING  CPU
        "mem_available_ratio": 0.07,   # → CRITICAL Mémoire
        "mem_total_bytes":     8 * 1024**3,
        "disk_avail_ratio":    0.10,   # → WARNING  Disque
        "disk_size_bytes":     50 * 1024**3,
        "latency_p95_seconds": 0.75,   # → WARNING  Latence P95
        "error_rate_pct":      8.0,    # → CRITICAL Erreurs 5xx
        "total_requests":      10000,
        "in_progress":         45,
    },
}


# =============================================================================
#  Génération du payload Prometheus (format text exposition)
# =============================================================================

def build_metrics(hostname: str, service: str, environment: str, v: dict) -> str:
    """
    Génère les métriques au format Prometheus text exposition.

    Labels utilisés par les dashboards :
      - Golden Signals : service, environment, instance, method, status
      - USE Method     : hostname, mode, mountpoint
    """
    lines = []
    now = time.time()

    # ─────────────────────────────────────────────────────────────────────────
    # 1. CPU — node_cpu_seconds_total
    #    Dashboard USE    : node_cpu_seconds_total{hostname="srv-web01", mode="idle"}
    #    Dashboard Golden : node_cpu_seconds_total{hostname="srv-web01", mode="idle"}
    # ─────────────────────────────────────────────────────────────────────────
    idle = v["cpu_idle_ratio"]
    user = (1 - idle) * 0.7
    sys_ = (1 - idle) * 0.3

    lines += [
        "# HELP node_cpu_seconds_total Seconds the CPUs spent in each mode.",
        "# TYPE node_cpu_seconds_total counter",
        f'node_cpu_seconds_total{{hostname="{hostname}",cpu="0",mode="idle"}}   {idle * now:.2f}',
        f'node_cpu_seconds_total{{hostname="{hostname}",cpu="0",mode="user"}}   {user * now:.2f}',
        f'node_cpu_seconds_total{{hostname="{hostname}",cpu="0",mode="system"}} {sys_ * now:.2f}',
        f'node_cpu_seconds_total{{hostname="{hostname}",cpu="1",mode="idle"}}   {idle * now:.2f}',
        f'node_cpu_seconds_total{{hostname="{hostname}",cpu="1",mode="user"}}   {user * now:.2f}',
        f'node_cpu_seconds_total{{hostname="{hostname}",cpu="1",mode="system"}} {sys_ * now:.2f}',
    ]

    # ─────────────────────────────────────────────────────────────────────────
    # 2. Mémoire — node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes
    # ─────────────────────────────────────────────────────────────────────────
    mem_total = v["mem_total_bytes"]
    mem_avail = mem_total * v["mem_available_ratio"]

    lines += [
        "# HELP node_memory_MemTotal_bytes Total RAM.",
        "# TYPE node_memory_MemTotal_bytes gauge",
        f'node_memory_MemTotal_bytes{{hostname="{hostname}"}} {mem_total:.0f}',
        "# HELP node_memory_MemAvailable_bytes Available RAM.",
        "# TYPE node_memory_MemAvailable_bytes gauge",
        f'node_memory_MemAvailable_bytes{{hostname="{hostname}"}} {mem_avail:.0f}',
    ]

    # ─────────────────────────────────────────────────────────────────────────
    # 3. Disque — node_filesystem_avail_bytes / node_filesystem_size_bytes
    # ─────────────────────────────────────────────────────────────────────────
    disk_size  = v["disk_size_bytes"]
    disk_avail = disk_size * v["disk_avail_ratio"]

    lines += [
        "# HELP node_filesystem_size_bytes Filesystem size in bytes.",
        "# TYPE node_filesystem_size_bytes gauge",
        f'node_filesystem_size_bytes{{hostname="{hostname}",mountpoint="/",fstype="ext4"}} {disk_size:.0f}',
        "# HELP node_filesystem_avail_bytes Filesystem space available.",
        "# TYPE node_filesystem_avail_bytes gauge",
        f'node_filesystem_avail_bytes{{hostname="{hostname}",mountpoint="/",fstype="ext4"}} {disk_avail:.0f}',
    ]

    # ─────────────────────────────────────────────────────────────────────────
    # 4. Latence — http_request_duration_seconds (histogram)
    #    Label requis par le dashboard : service, environment
    #    PromQL : histogram_quantile(0.95, sum(rate(bucket{service="$service"}[5m])) by (le))
    # ─────────────────────────────────────────────────────────────────────────
    p95   = v["latency_p95_seconds"]
    total = v["total_requests"]

    # Buckets cohérents : 95% des requêtes tombent sous p95
    buckets = [
        ("0.05",      int(total * 0.30)),
        ("0.1",       int(total * 0.50)),
        ("0.25",      int(total * 0.70)),
        ("0.5",       int(total * 0.85)),
        (str(p95),    int(total * 0.95)),
        (str(p95*2),  int(total * 0.99)),
        ("+Inf",      total),
    ]
    req_sum = p95 * total * 0.6

    base_labels = f'hostname="{hostname}",service="{service}",environment="{environment}"'

    lines += [
        "# HELP http_request_duration_seconds HTTP request latency histogram.",
        "# TYPE http_request_duration_seconds histogram",
    ]
    for le, count in buckets:
        lines.append(
            f'http_request_duration_seconds_bucket{{{base_labels},le="{le}"}} '
            f'{int(count * now / 300)}'
        )
    lines += [
        f'http_request_duration_seconds_sum{{{base_labels}}}   {req_sum * now / 300:.2f}',
        f'http_request_duration_seconds_count{{{base_labels}}} {int(total * now / 300)}',
    ]

    # ─────────────────────────────────────────────────────────────────────────
    # 5. Requêtes HTTP — http_requests_total
    #    Labels requis : service, environment, status, method
    #    PromQL trafic  : sum(rate(http_requests_total{service="$service"}[1m])) by (method)
    #    PromQL erreurs : sum(rate(...{status=~"5.."}[5m])) / sum(rate(...[5m]))
    # ─────────────────────────────────────────────────────────────────────────
    err_pct  = v["error_rate_pct"] / 100
    rps      = v["total_requests"] / 300

    ok_get   = int(rps * (1 - err_pct) * 0.70 * now)
    ok_post  = int(rps * (1 - err_pct) * 0.30 * now)
    err_500  = int(rps * err_pct * 0.80 * now)
    err_502  = int(rps * err_pct * 0.20 * now)

    lines += [
        "# HELP http_requests_total Total HTTP requests by method and status.",
        "# TYPE http_requests_total counter",
        f'http_requests_total{{hostname="{hostname}",service="{service}",environment="{environment}",method="GET",status="200"}}  {ok_get}',
        f'http_requests_total{{hostname="{hostname}",service="{service}",environment="{environment}",method="POST",status="200"}} {ok_post}',
        f'http_requests_total{{hostname="{hostname}",service="{service}",environment="{environment}",method="GET",status="500"}}  {err_500}',
        f'http_requests_total{{hostname="{hostname}",service="{service}",environment="{environment}",method="GET",status="502"}}  {err_502}',
    ]

    # ─────────────────────────────────────────────────────────────────────────
    # 6. Requêtes en cours — http_requests_in_progress (gauge)
    #    Panneau "Saturation" du dashboard Golden Signals
    #    PromQL : http_requests_in_progress{service="$service"}
    # ─────────────────────────────────────────────────────────────────────────
    lines += [
        "# HELP http_requests_in_progress Current number of HTTP requests in progress.",
        "# TYPE http_requests_in_progress gauge",
        f'http_requests_in_progress{{hostname="{hostname}",service="{service}",environment="{environment}"}} {v["in_progress"]}',
    ]

    return "\n".join(lines) + "\n"


# =============================================================================
#  Serveur HTTP minimal
# =============================================================================

class MetricsHandler(BaseHTTPRequestHandler):

    hostname    = "srv-web01"
    service     = "boutique-api"
    environment = "lab"
    mode        = "all"

    def do_GET(self):
        if self.path != "/metrics":
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"404 — utilise /metrics\n")
            return

        v       = MODES[self.mode]
        payload = build_metrics(
            self.hostname, self.service, self.environment, v
        ).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args):
        print(f"  [scrape] {self.address_string()} → {args[0]} {args[1]}")


# =============================================================================
#  Point d'entrée
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Fake exporter HTTP — simulateur d'alertes Grafana (IAI INGC2)"
    )
    parser.add_argument("--mode",        default="all",         choices=list(MODES.keys()))
    parser.add_argument("--port",        default=9200,          type=int)
    parser.add_argument("--hostname",    default="srv-web01",   help="Label hostname")
    parser.add_argument("--service",     default="boutique-api",help="Label service")
    parser.add_argument("--environment", default="lab",         help="Label environment")
    args = parser.parse_args()

    MetricsHandler.hostname    = args.hostname
    MetricsHandler.service     = args.service
    MetricsHandler.environment = args.environment
    MetricsHandler.mode        = args.mode

    v = MODES[args.mode]
    cpu_pct  = (1 - v["cpu_idle_ratio"])      * 100
    mem_pct  = (1 - v["mem_available_ratio"]) * 100
    disk_pct = v["disk_avail_ratio"]           * 100
    lat_ms   = v["latency_p95_seconds"]        * 1000
    err_pct  = v["error_rate_pct"]

    W  = "\033[93m[WARNING] \033[0m"
    C  = "\033[91m[CRITICAL]\033[0m"
    OK = "\033[92m[OK]      \033[0m"

    print("=" * 62)
    print("  Fake Exporter — E-Service Linux (IAI INGC2)")
    print("=" * 62)
    print(f"  Mode        : {args.mode}")
    print(f"  URL         : http://0.0.0.0:{args.port}/metrics")
    print(f"  Labels      : hostname={args.hostname} | service={args.service} | environment={args.environment}")
    print()
    print("  Valeurs exposées :")
    print(f"  ├─ CPU        : {cpu_pct:.0f}%      {C if cpu_pct > 85 else OK}  seuil WARNING > 85%")
    print(f"  ├─ Mémoire    : {mem_pct:.0f}%      {C if mem_pct > 90 else OK}  seuil CRITICAL > 90%")
    print(f"  ├─ Disque /   : {disk_pct:.0f}% lib {W if disk_pct < 15 else OK}  seuil WARNING < 15%")
    print(f"  ├─ Latence P95: {lat_ms:.0f} ms   {W if lat_ms > 500 else OK}  seuil WARNING > 500 ms")
    print(f"  └─ Erreurs 5xx: {err_pct:.1f}%     {C if err_pct > 5 else OK}  seuil CRITICAL > 5%")
    print()
    print("  ⏳ Délais avant FIRING (délai 'for:' des règles) :")
    print("     Erreurs 5xx → 2 min | Latence → 3 min | CPU/RAM → 5 min | Disque → 10 min")
    print()
    print("  Ctrl+C pour arrêter")
    print("-" * 62)

    server = HTTPServer(("0.0.0.0", args.port), MetricsHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n  Exporter arrêté.")
        print("  → Retire le job 'fake-exporter' de /etc/prometheus/prometheus.yml")
        print("  → sudo systemctl reload prometheus")


if __name__ == "__main__":
    main()