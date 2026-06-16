#!/usr/bin/env python3
"""
=============================================================================
  fake_exporter.py -- Faux exporter HTTP pour simuler les alertes Grafana
  Projet : E-Service Linux -- Livrable L3
  Auteurs : Thales & MBA ONDO Dieudonne (INGC2 - IAI Libreville)
=============================================================================

  Lance un serveur HTTP sur le port 9200 qui expose des metriques au format
  Prometheus. Couvre les deux dashboards :
    - Golden Signals (latence, trafic, erreurs, saturation)
    - USE Method     (CPU, memoire, disque, reseau, load, erreurs reseau)

  UTILISATION :
    python3 fake_exporter.py --mode all
    python3 fake_exporter.py --mode cpu
    python3 fake_exporter.py --mode mem
    python3 fake_exporter.py --mode disk
    python3 fake_exporter.py --mode latency
    python3 fake_exporter.py --mode errors
    python3 fake_exporter.py --mode normal

  Arret : Ctrl+C
  Apres arret : retirer le job fake-exporter de prometheus.yml puis
                sudo systemctl reload prometheus
=============================================================================
"""

import argparse
import time
import math
from http.server import BaseHTTPRequestHandler, HTTPServer


# =============================================================================
#  Valeurs simulees par mode
# =============================================================================

MODES = {
    "normal": {
        "cpu_idle_ratio":      0.70,   # CPU  30%        OK
        "mem_available_ratio": 0.50,   # RAM  50% libre  OK
        "mem_total_bytes":     8 * 1024**3,
        "disk_avail_ratio":    0.60,   # 60% libre       OK
        "disk_size_bytes":     50 * 1024**3,
        "latency_p95_seconds": 0.15,   # 150 ms          OK
        "error_rate_pct":      0.5,    # 0.5%            OK
        "total_requests":      10000,
        "in_progress":         5,
        "load1":               0.40,
        "load5":               0.35,
        "load15":              0.30,
        "disk_read_bps":       2 * 1024**2,   # 2 MB/s
        "disk_write_bps":      1 * 1024**2,   # 1 MB/s
        "net_rx_bps":          500 * 1024,    # 500 KB/s
        "net_tx_bps":          200 * 1024,    # 200 KB/s
        "net_err_rx_pps":      0.0,
        "net_err_tx_pps":      0.0,
    },
    "cpu": {
        "cpu_idle_ratio":      0.08,   # CPU 92%  -> WARNING > 85%
        "mem_available_ratio": 0.50,
        "mem_total_bytes":     8 * 1024**3,
        "disk_avail_ratio":    0.60,
        "disk_size_bytes":     50 * 1024**3,
        "latency_p95_seconds": 0.15,
        "error_rate_pct":      0.5,
        "total_requests":      10000,
        "in_progress":         5,
        "load1":               3.80,   # load eleve coherent avec CPU haut
        "load5":               3.50,
        "load15":              3.00,
        "disk_read_bps":       2 * 1024**2,
        "disk_write_bps":      1 * 1024**2,
        "net_rx_bps":          500 * 1024,
        "net_tx_bps":          200 * 1024,
        "net_err_rx_pps":      0.0,
        "net_err_tx_pps":      0.0,
    },
    "mem": {
        "cpu_idle_ratio":      0.70,
        "mem_available_ratio": 0.07,   # RAM 93%  -> CRITICAL > 90%
        "mem_total_bytes":     8 * 1024**3,
        "disk_avail_ratio":    0.60,
        "disk_size_bytes":     50 * 1024**3,
        "latency_p95_seconds": 0.15,
        "error_rate_pct":      0.5,
        "total_requests":      10000,
        "in_progress":         5,
        "load1":               1.20,
        "load5":               1.10,
        "load15":              1.00,
        "disk_read_bps":       5 * 1024**2,   # swap actif -> + de lectures disque
        "disk_write_bps":      4 * 1024**2,
        "net_rx_bps":          500 * 1024,
        "net_tx_bps":          200 * 1024,
        "net_err_rx_pps":      0.0,
        "net_err_tx_pps":      0.0,
    },
    "disk": {
        "cpu_idle_ratio":      0.70,
        "mem_available_ratio": 0.50,
        "mem_total_bytes":     8 * 1024**3,
        "disk_avail_ratio":    0.10,   # 10% libre -> WARNING < 15%
        "disk_size_bytes":     50 * 1024**3,
        "latency_p95_seconds": 0.15,
        "error_rate_pct":      0.5,
        "total_requests":      10000,
        "in_progress":         5,
        "load1":               0.50,
        "load5":               0.45,
        "load15":              0.40,
        "disk_read_bps":       8 * 1024**2,   # disque presque plein -> I/O eleve
        "disk_write_bps":      6 * 1024**2,
        "net_rx_bps":          500 * 1024,
        "net_tx_bps":          200 * 1024,
        "net_err_rx_pps":      0.0,
        "net_err_tx_pps":      0.0,
    },
    "latency": {
        "cpu_idle_ratio":      0.70,
        "mem_available_ratio": 0.50,
        "mem_total_bytes":     8 * 1024**3,
        "disk_avail_ratio":    0.60,
        "disk_size_bytes":     50 * 1024**3,
        "latency_p95_seconds": 0.75,   # 750 ms -> WARNING > 500 ms
        "error_rate_pct":      0.5,
        "total_requests":      10000,
        "in_progress":         45,     # beaucoup de req en attente
        "load1":               1.80,
        "load5":               1.60,
        "load15":              1.40,
        "disk_read_bps":       2 * 1024**2,
        "disk_write_bps":      1 * 1024**2,
        "net_rx_bps":          800 * 1024,
        "net_tx_bps":          600 * 1024,
        "net_err_rx_pps":      0.0,
        "net_err_tx_pps":      0.0,
    },
    "errors": {
        "cpu_idle_ratio":      0.70,
        "mem_available_ratio": 0.50,
        "mem_total_bytes":     8 * 1024**3,
        "disk_avail_ratio":    0.60,
        "disk_size_bytes":     50 * 1024**3,
        "latency_p95_seconds": 0.15,
        "error_rate_pct":      8.0,    # 8% erreurs 5xx -> CRITICAL > 5%
        "total_requests":      10000,
        "in_progress":         5,
        "load1":               0.50,
        "load5":               0.45,
        "load15":              0.40,
        "disk_read_bps":       2 * 1024**2,
        "disk_write_bps":      1 * 1024**2,
        "net_rx_bps":          500 * 1024,
        "net_tx_bps":          200 * 1024,
        "net_err_rx_pps":      12.0,   # erreurs reseau coherentes
        "net_err_tx_pps":      4.0,
    },
    "all": {
        "cpu_idle_ratio":      0.08,   # -> WARNING  CPU
        "mem_available_ratio": 0.07,   # -> CRITICAL Memoire
        "mem_total_bytes":     8 * 1024**3,
        "disk_avail_ratio":    0.10,   # -> WARNING  Disque
        "disk_size_bytes":     50 * 1024**3,
        "latency_p95_seconds": 0.75,   # -> WARNING  Latence P95
        "error_rate_pct":      8.0,    # -> CRITICAL Erreurs 5xx
        "total_requests":      10000,
        "in_progress":         45,
        "load1":               4.20,
        "load5":               3.80,
        "load15":              3.50,
        "disk_read_bps":       9 * 1024**2,
        "disk_write_bps":      7 * 1024**2,
        "net_rx_bps":          900 * 1024,
        "net_tx_bps":          700 * 1024,
        "net_err_rx_pps":      12.0,
        "net_err_tx_pps":      4.0,
    },
}


# =============================================================================
#  Generation du payload Prometheus
# =============================================================================

def build_metrics(hostname: str, service: str, environment: str, v: dict) -> str:
    lines = []
    now = time.time()

    lbl_node = f'hostname="{hostname}",environment="{environment}"'
    lbl_app  = f'hostname="{hostname}",service="{service}",environment="{environment}"'

    # -------------------------------------------------------------------------
    # node_uname_info
    # Utilise par le template $instance du dashboard USE :
    #   label_values(node_uname_info{environment="$environment"}, hostname)
    # -------------------------------------------------------------------------
    lines += [
        "# HELP node_uname_info System information.",
        "# TYPE node_uname_info gauge",
        f'node_uname_info{{{lbl_node},nodename="{hostname}",release="6.1.0",sysname="Linux"}} 1',
    ]

    # -------------------------------------------------------------------------
    # up — disponibilite du noeud (panneau "Disponibilite des noeuds")
    #   up{job="node", hostname=~"$instance"}
    # -------------------------------------------------------------------------
    lines += [
        "# HELP up Target is up (1) or down (0).",
        "# TYPE up gauge",
        f'up{{job="node",{lbl_node}}} 1',
    ]

    # -------------------------------------------------------------------------
    # CPU — node_cpu_seconds_total
    #   USE  : 100 - (avg by(hostname)(rate(...{hostname=~"$instance",mode="idle"}[5m]))*100)
    #   GS   : 100 - (avg(rate(...{hostname="srv-web01",mode="idle"}[5m]))*100)
    # -------------------------------------------------------------------------
    idle = v["cpu_idle_ratio"]
    user = (1 - idle) * 0.70
    sys_ = (1 - idle) * 0.30

    lines += [
        "# HELP node_cpu_seconds_total Seconds the CPUs spent in each mode.",
        "# TYPE node_cpu_seconds_total counter",
    ]
    for cpu in ("0", "1"):
        lines += [
            f'node_cpu_seconds_total{{{lbl_node},cpu="{cpu}",mode="idle"}}   {idle * now:.2f}',
            f'node_cpu_seconds_total{{{lbl_node},cpu="{cpu}",mode="user"}}   {user * now:.2f}',
            f'node_cpu_seconds_total{{{lbl_node},cpu="{cpu}",mode="system"}} {sys_ * now:.2f}',
        ]

    # -------------------------------------------------------------------------
    # Memoire
    # -------------------------------------------------------------------------
    mem_total = v["mem_total_bytes"]
    mem_avail = mem_total * v["mem_available_ratio"]

    lines += [
        "# HELP node_memory_MemTotal_bytes Total RAM.",
        "# TYPE node_memory_MemTotal_bytes gauge",
        f'node_memory_MemTotal_bytes{{{lbl_node}}} {mem_total:.0f}',
        "# HELP node_memory_MemAvailable_bytes Available RAM.",
        "# TYPE node_memory_MemAvailable_bytes gauge",
        f'node_memory_MemAvailable_bytes{{{lbl_node}}} {mem_avail:.0f}',
    ]

    # -------------------------------------------------------------------------
    # Disque — espace
    # -------------------------------------------------------------------------
    disk_size  = v["disk_size_bytes"]
    disk_avail = disk_size * v["disk_avail_ratio"]

    lines += [
        "# HELP node_filesystem_size_bytes Filesystem size in bytes.",
        "# TYPE node_filesystem_size_bytes gauge",
        f'node_filesystem_size_bytes{{{lbl_node},mountpoint="/",fstype="ext4"}} {disk_size:.0f}',
        "# HELP node_filesystem_avail_bytes Filesystem space available.",
        "# TYPE node_filesystem_avail_bytes gauge",
        f'node_filesystem_avail_bytes{{{lbl_node},mountpoint="/",fstype="ext4"}} {disk_avail:.0f}',
    ]

    # -------------------------------------------------------------------------
    # Disque — debit I/O (panneau "Debit I/O lecture/ecriture" du dashboard USE)
    #   rate(node_disk_read_bytes_total{hostname=~"$instance"}[5m])
    # -------------------------------------------------------------------------
    read_bps  = v["disk_read_bps"]
    write_bps = v["disk_write_bps"]

    lines += [
        "# HELP node_disk_read_bytes_total Bytes read from disk.",
        "# TYPE node_disk_read_bytes_total counter",
        f'node_disk_read_bytes_total{{{lbl_node},device="sda"}} {read_bps * now:.0f}',
        "# HELP node_disk_written_bytes_total Bytes written to disk.",
        "# TYPE node_disk_written_bytes_total counter",
        f'node_disk_written_bytes_total{{{lbl_node},device="sda"}} {write_bps * now:.0f}',
    ]

    # -------------------------------------------------------------------------
    # Reseau — debit RX/TX (panneau "Trafic entrant/sortant")
    #   rate(node_network_receive_bytes_total{hostname=~"$instance",device!="lo"}[5m])
    # -------------------------------------------------------------------------
    rx_bps = v["net_rx_bps"]
    tx_bps = v["net_tx_bps"]

    lines += [
        "# HELP node_network_receive_bytes_total Network bytes received.",
        "# TYPE node_network_receive_bytes_total counter",
        f'node_network_receive_bytes_total{{{lbl_node},device="eth0"}} {rx_bps * now:.0f}',
        "# HELP node_network_transmit_bytes_total Network bytes transmitted.",
        "# TYPE node_network_transmit_bytes_total counter",
        f'node_network_transmit_bytes_total{{{lbl_node},device="eth0"}} {tx_bps * now:.0f}',
    ]

    # -------------------------------------------------------------------------
    # Reseau — erreurs (panneau "Paquets en erreur RX/TX")
    #   rate(node_network_receive_errs_total{hostname=~"$instance",device!="lo"}[5m])
    # -------------------------------------------------------------------------
    err_rx = v["net_err_rx_pps"]
    err_tx = v["net_err_tx_pps"]

    lines += [
        "# HELP node_network_receive_errs_total Network receive errors.",
        "# TYPE node_network_receive_errs_total counter",
        f'node_network_receive_errs_total{{{lbl_node},device="eth0"}} {err_rx * now:.0f}',
        "# HELP node_network_transmit_errs_total Network transmit errors.",
        "# TYPE node_network_transmit_errs_total counter",
        f'node_network_transmit_errs_total{{{lbl_node},device="eth0"}} {err_tx * now:.0f}',
    ]

    # -------------------------------------------------------------------------
    # Load average (panneau "Charge systeme load average 1/5/15 min")
    #   node_load1/5/15{hostname=~"$instance"}
    # -------------------------------------------------------------------------
    lines += [
        "# HELP node_load1 1m load average.",
        "# TYPE node_load1 gauge",
        f'node_load1{{{lbl_node}}} {v["load1"]}',
        "# HELP node_load5 5m load average.",
        "# TYPE node_load5 gauge",
        f'node_load5{{{lbl_node}}} {v["load5"]}',
        "# HELP node_load15 15m load average.",
        "# TYPE node_load15 gauge",
        f'node_load15{{{lbl_node}}} {v["load15"]}',
    ]

    # -------------------------------------------------------------------------
    # Latence HTTP — histogram (Golden Signals)
    #   histogram_quantile(0.95, sum(rate(bucket{service="$service"}[5m])) by (le))
    # -------------------------------------------------------------------------
    p95   = v["latency_p95_seconds"]
    total = v["total_requests"]

    buckets = [
        ("0.05",       int(total * 0.30)),
        ("0.1",        int(total * 0.50)),
        ("0.25",       int(total * 0.70)),
        ("0.5",        int(total * 0.85)),
        (str(p95),     int(total * 0.95)),
        (str(p95 * 2), int(total * 0.99)),
        ("+Inf",       total),
    ]
    req_sum = p95 * total * 0.6

    lines += [
        "# HELP http_request_duration_seconds HTTP request latency histogram.",
        "# TYPE http_request_duration_seconds histogram",
    ]
    for le, count in buckets:
        lines.append(
            f'http_request_duration_seconds_bucket{{{lbl_app},le="{le}"}} '
            f'{int(count * now / 300)}'
        )
    lines += [
        f'http_request_duration_seconds_sum{{{lbl_app}}}   {req_sum * now / 300:.2f}',
        f'http_request_duration_seconds_count{{{lbl_app}}} {int(total * now / 300)}',
    ]

    # -------------------------------------------------------------------------
    # Requetes HTTP — compteurs (Golden Signals trafic + erreurs)
    #   sum(rate(http_requests_total{service="$service"}[1m])) by (method)
    #   sum(rate(http_requests_total{service,status=~"5.."}[5m])) / sum(...)
    # -------------------------------------------------------------------------
    err_pct = v["error_rate_pct"] / 100
    rps     = v["total_requests"] / 300

    ok_get  = int(rps * (1 - err_pct) * 0.70 * now)
    ok_post = int(rps * (1 - err_pct) * 0.30 * now)
    err_500 = int(rps * err_pct * 0.80 * now)
    err_502 = int(rps * err_pct * 0.20 * now)

    lines += [
        "# HELP http_requests_total Total HTTP requests by method and status.",
        "# TYPE http_requests_total counter",
        f'http_requests_total{{{lbl_app},method="GET",status="200"}}  {ok_get}',
        f'http_requests_total{{{lbl_app},method="POST",status="200"}} {ok_post}',
        f'http_requests_total{{{lbl_app},method="GET",status="500"}}  {err_500}',
        f'http_requests_total{{{lbl_app},method="GET",status="502"}}  {err_502}',
    ]

    # -------------------------------------------------------------------------
    # Requetes en cours — gauge (Golden Signals saturation)
    #   http_requests_in_progress{service="$service"}
    # -------------------------------------------------------------------------
    lines += [
        "# HELP http_requests_in_progress Current in-flight HTTP requests.",
        "# TYPE http_requests_in_progress gauge",
        f'http_requests_in_progress{{{lbl_app}}} {v["in_progress"]}',
    ]

    return "\n".join(lines) + "\n"


# =============================================================================
#  Serveur HTTP
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
            self.wfile.write(b"404 - utilise /metrics\n")
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
        print(f"  [scrape] {self.address_string()} -> {args[0]} {args[1]}")


# =============================================================================
#  Point d'entree
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Fake exporter HTTP -- simulateur alertes Grafana (IAI INGC2)"
    )
    parser.add_argument("--mode",        default="all",          choices=list(MODES.keys()))
    parser.add_argument("--port",        default=9200,           type=int)
    parser.add_argument("--hostname",    default="srv-web01",    help="Label hostname")
    parser.add_argument("--service",     default="boutique-api", help="Label service")
    parser.add_argument("--environment", default="lab",          help="Label environment")
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

    W  = "[WARNING] "
    C  = "[CRITICAL]"
    OK = "[OK]      "

    def badge(cond_warn, cond_crit):
        if cond_crit:  return C
        if cond_warn:  return W
        return OK

    print("=" * 62)
    print("  Fake Exporter -- E-Service Linux (IAI INGC2)")
    print("=" * 62)
    print(f"  Mode        : {args.mode}")
    print(f"  URL         : http://0.0.0.0:{args.port}/metrics")
    print(f"  hostname    : {args.hostname}")
    print(f"  service     : {args.service}")
    print(f"  environment : {args.environment}")
    print()
    print("  -- Alertes --")
    print(f"  CPU         : {cpu_pct:.0f}%      {badge(cpu_pct>85, False)}  seuil WARNING > 85%")
    print(f"  Memoire     : {mem_pct:.0f}%      {badge(False, mem_pct>90)}  seuil CRITICAL > 90%")
    print(f"  Disque /    : {disk_pct:.0f}% lib {badge(disk_pct<15, False)}  seuil WARNING < 15%")
    print(f"  Latence P95 : {lat_ms:.0f} ms   {badge(lat_ms>500, False)}  seuil WARNING > 500 ms")
    print(f"  Erreurs 5xx : {err_pct:.1f}%     {badge(False, err_pct>5)}  seuil CRITICAL > 5%")
    print()
    print("  -- USE Method --")
    print(f"  Load avg    : {v['load1']:.2f} / {v['load5']:.2f} / {v['load15']:.2f}  (1/5/15 min)")
    print(f"  Disque I/O  : read={v['disk_read_bps']//1024} KB/s  write={v['disk_write_bps']//1024} KB/s")
    print(f"  Reseau      : RX={v['net_rx_bps']//1024} KB/s  TX={v['net_tx_bps']//1024} KB/s")
    print(f"  Err reseau  : RX={v['net_err_rx_pps']} pps  TX={v['net_err_tx_pps']} pps")
    print()
    print("  Delais avant FIRING :")
    print("  Erreurs 5xx -> 2 min | Latence -> 3 min | CPU/RAM -> 5 min | Disque -> 10 min")
    print()
    print("  Ctrl+C pour arreter")
    print("-" * 62)

    server = HTTPServer(("0.0.0.0", args.port), MetricsHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Exporter arrete.")
        print("  -> Retire le job fake-exporter de /etc/prometheus/prometheus.yml")
        print("  -> sudo systemctl reload prometheus")


if __name__ == "__main__":
    main()