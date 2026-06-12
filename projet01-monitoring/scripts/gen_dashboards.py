#!/usr/bin/env python3
# =============================================================================
#  gen_dashboards.py — Génère les deux dashboards Grafana (livrable L2)
#  Produit deux fichiers JSON importables tels quels dans Grafana 10.x / 11.x :
#     - use-method.json        (méthode USE : Utilization, Saturation, Errors)
#     - golden-signals.json    (Latence, Trafic, Erreurs, Saturation)
#
#  On construit les dashboards comme des dictionnaires Python puis on les
#  sérialise en JSON : cela garantit un JSON syntaxiquement valide.
# =============================================================================
import json

# Référence à la datasource Prometheus provisionnée.
# "${DS_PROMETHEUS}" est résolu à l'import ; en provisioning on cible le type.
DS = {"type": "prometheus", "uid": "${DS_PROMETHEUS}"}


# ----------------------------------------------------------------------------
# Fabriques de variables de template (sélecteurs dynamiques du dashboard)
# ----------------------------------------------------------------------------
def var_query(name, label, query, multi=False, include_all=True):
    """Crée une variable de type 'query' (liste de valeurs issues de Prometheus)."""
    return {
        "name": name,
        "label": label,
        "type": "query",
        "datasource": DS,
        "definition": query,
        "query": {"query": query, "refId": name},
        "refresh": 2,              # 2 = rafraîchit à chaque changement de plage de temps
        "sort": 1,                 # tri alphabétique
        "multi": multi,            # autorise la sélection multiple
        "includeAll": include_all, # ajoute l'option "All"
        "current": {},
        "hide": 0,
    }


# ----------------------------------------------------------------------------
# Fabriques de panels
# ----------------------------------------------------------------------------
def target(expr, legend="", ref="A"):
    """Crée une cible (requête PromQL) pour un panel."""
    return {
        "datasource": DS,
        "expr": expr,
        "legendFormat": legend,
        "refId": ref,
        "editorMode": "code",
        "range": True,
    }


def gauge_panel(pid, title, expr, gridPos, unit="percent",
                thresholds=None, legend="{{hostname}}"):
    """Jauge (gauge) avec seuils colorés — idéale pour Utilization/Saturation."""
    if thresholds is None:
        thresholds = [
            {"color": "green", "value": None},
            {"color": "yellow", "value": 70},
            {"color": "red", "value": 85},
        ]
    return {
        "id": pid,
        "type": "gauge",
        "title": title,
        "datasource": DS,
        "gridPos": gridPos,
        "targets": [target(expr, legend)],
        "fieldConfig": {
            "defaults": {
                "unit": unit,
                "min": 0,
                "max": 100,
                "thresholds": {"mode": "absolute", "steps": thresholds},
            },
            "overrides": [],
        },
        "options": {
            "showThresholdLabels": False,
            "showThresholdMarkers": True,
            "orientation": "auto",
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
        },
    }


def timeseries_panel(pid, title, targets, gridPos, unit="short",
                     legend_placement="bottom"):
    """Graphe temporel (timeseries) — pour Disk I/O, Réseau, Trafic, Latence."""
    return {
        "id": pid,
        "type": "timeseries",
        "title": title,
        "datasource": DS,
        "gridPos": gridPos,
        "targets": targets,
        "fieldConfig": {
            "defaults": {
                "unit": unit,
                "custom": {
                    "drawStyle": "line",
                    "lineInterpolation": "smooth",
                    "fillOpacity": 10,
                    "showPoints": "never",
                    "lineWidth": 2,
                },
                "color": {"mode": "palette-classic"},
            },
            "overrides": [],
        },
        "options": {
            "legend": {"displayMode": "table", "placement": legend_placement,
                       "calcs": ["mean", "max"]},
            "tooltip": {"mode": "multi", "sort": "desc"},
        },
    }


def stat_panel(pid, title, expr, gridPos, unit="short",
               legend="{{hostname}}", color_mode="value"):
    """Indicateur unique (stat) — pour compteurs : Trafic, Connexions actives."""
    return {
        "id": pid,
        "type": "stat",
        "title": title,
        "datasource": DS,
        "gridPos": gridPos,
        "targets": [target(expr, legend)],
        "fieldConfig": {
            "defaults": {
                "unit": unit,
                "color": {"mode": "palette-classic"},
                "thresholds": {"mode": "absolute",
                               "steps": [{"color": "green", "value": None}]},
            },
            "overrides": [],
        },
        "options": {
            "colorMode": color_mode,
            "graphMode": "area",
            "justifyMode": "auto",
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
        },
    }


def heatmap_panel(pid, title, expr, gridPos, legend="{{hostname}}"):
    """Heatmap calculée à partir d'une série (ex : distribution d'usage RAM)."""
    return {
        "id": pid,
        "type": "heatmap",
        "title": title,
        "datasource": DS,
        "gridPos": gridPos,
        "targets": [target(expr, legend)],
        "options": {
            "calculate": True,                       # bucketise la série en heatmap
            "calculation": {"yBuckets": {"mode": "size", "value": "10"}},
            "color": {"scheme": "Spectral", "mode": "scheme", "steps": 64},
            "yAxis": {"unit": "percent", "min": "0", "max": "100"},
            "legend": {"show": True},
            "tooltip": {"show": True, "yHistogram": False},
        },
        "fieldConfig": {"defaults": {"custom": {"hideFrom":
                        {"tooltip": False, "viz": False, "legend": False}}},
                        "overrides": []},
    }


def text_panel(pid, title, content, gridPos):
    """Panel texte (markdown) — pour annoter le dashboard."""
    return {
        "id": pid,
        "type": "text",
        "title": title,
        "gridPos": gridPos,
        "options": {"mode": "markdown", "content": content},
    }


def row(pid, title, y):
    """Bandeau de regroupement (row) pour organiser visuellement les panels."""
    return {"id": pid, "type": "row", "title": title, "collapsed": False,
            "gridPos": {"h": 1, "w": 24, "x": 0, "y": y}, "panels": []}


def build_dashboard(uid, title, tags, variables, panels, refresh="10s"):
    """Assemble le modèle de dashboard complet."""
    return {
        "uid": uid,
        "title": title,
        "tags": tags,
        "timezone": "browser",
        "schemaVersion": 39,
        "version": 1,
        "refresh": refresh,
        "time": {"from": "now-1h", "to": "now"},
        "templating": {"list": variables},
        "annotations": {"list": [{
            "builtIn": 1, "type": "dashboard", "name": "Annotations & Alerts",
            "enable": True, "datasource": {"type": "grafana", "uid": "-- Grafana --"},
            "iconColor": "rgba(0, 211, 255, 1)",
        }]},
        "panels": panels,
        "__inputs": [{
            "name": "DS_PROMETHEUS", "label": "Prometheus", "description": "",
            "type": "datasource", "pluginId": "prometheus", "pluginName": "Prometheus",
        }],
    }


# ============================================================================
#  DASHBOARD 1 — MÉTHODE USE (Utilization, Saturation, Errors)
#  Source de données : Node Exporter (job="node")
# ============================================================================
use_vars = [
    var_query("environment", "Environnement",
              "label_values(node_uname_info, environment)"),
    var_query("job", "Job", "label_values(up, job)"),
    var_query("instance", "Instance (serveur)",
              'label_values(node_uname_info{environment="$environment"}, hostname)',
              multi=True),
]

use_panels = [
    text_panel(1, "", "## Méthode **USE** — Utilization · Saturation · Errors\n"
                  "Source : *Node Exporter*. Sélectionnez l'environnement et le(s) "
                  "serveur(s) via les menus en haut.",
               {"h": 3, "w": 24, "x": 0, "y": 0}),

    row(2, "Utilization — Taux d'utilisation des ressources", 3),

    # CPU Gauge (Utilization) : 100 - %idle
    gauge_panel(10, "CPU — Utilisation (%)",
                '100 - (avg by (hostname) '
                '(rate(node_cpu_seconds_total{hostname=~"$instance", mode="idle"}[5m])) * 100)',
                {"h": 8, "w": 8, "x": 0, "y": 4}),

    # RAM Gauge (Utilization)
    gauge_panel(11, "Mémoire — Utilisation (%)",
                '(1 - (node_memory_MemAvailable_bytes{hostname=~"$instance"} '
                '/ node_memory_MemTotal_bytes{hostname=~"$instance"})) * 100',
                {"h": 8, "w": 8, "x": 8, "y": 4}),

    # Disque racine (Utilization)
    gauge_panel(12, "Disque / — Utilisation (%)",
                '(1 - (node_filesystem_avail_bytes{hostname=~"$instance", mountpoint="/"} '
                '/ node_filesystem_size_bytes{hostname=~"$instance", mountpoint="/"})) * 100',
                {"h": 8, "w": 8, "x": 16, "y": 4}),

    row(3, "Saturation — Travail en attente", 12),

    # Memory Heatmap (Saturation) : distribution du % d'usage RAM dans le temps
    heatmap_panel(20, "Mémoire — Heatmap d'utilisation (%)",
                  '(1 - (node_memory_MemAvailable_bytes{hostname=~"$instance"} '
                  '/ node_memory_MemTotal_bytes{hostname=~"$instance"})) * 100',
                  {"h": 9, "w": 12, "x": 0, "y": 13}),

    # Load average (Saturation : file d'attente CPU)
    timeseries_panel(21, "Charge système (load average 1/5/15 min)",
                     [target('node_load1{hostname=~"$instance"}', "load1 {{hostname}}", "A"),
                      target('node_load5{hostname=~"$instance"}', "load5 {{hostname}}", "B"),
                      target('node_load15{hostname=~"$instance"}', "load15 {{hostname}}", "C")],
                     {"h": 9, "w": 12, "x": 12, "y": 13}, unit="short"),

    row(4, "Disque & Réseau (débits)", 22),

    # Disk I/O Graph
    timeseries_panel(30, "Disque — Débit I/O (lecture/écriture)",
                     [target('rate(node_disk_read_bytes_total{hostname=~"$instance"}[5m])',
                             "lecture {{hostname}} {{device}}", "A"),
                      target('rate(node_disk_written_bytes_total{hostname=~"$instance"}[5m])',
                             "écriture {{hostname}} {{device}}", "B")],
                     {"h": 8, "w": 12, "x": 0, "y": 23}, unit="Bps"),

    # Network Stat
    timeseries_panel(31, "Réseau — Trafic entrant/sortant",
                     [target('rate(node_network_receive_bytes_total'
                             '{hostname=~"$instance", device!="lo"}[5m])',
                             "RX {{hostname}} {{device}}", "A"),
                      target('rate(node_network_transmit_bytes_total'
                             '{hostname=~"$instance", device!="lo"}[5m])',
                             "TX {{hostname}} {{device}}", "B")],
                     {"h": 8, "w": 12, "x": 12, "y": 23}, unit="Bps"),

    row(5, "Errors — Erreurs réseau & disponibilité", 31),

    # Errors : paquets réseau en erreur (USE → Errors)
    timeseries_panel(40, "Réseau — Paquets en erreur (RX/TX)",
                     [target('rate(node_network_receive_errs_total'
                             '{hostname=~"$instance", device!="lo"}[5m])',
                             "err RX {{hostname}}", "A"),
                      target('rate(node_network_transmit_errs_total'
                             '{hostname=~"$instance", device!="lo"}[5m])',
                             "err TX {{hostname}}", "B")],
                     {"h": 8, "w": 12, "x": 0, "y": 32}, unit="pps"),

    # Disponibilité des cibles (up)
    stat_panel(41, "Disponibilité des nœuds (up)",
               'up{job="node", hostname=~"$instance"}',
               {"h": 8, "w": 12, "x": 12, "y": 32}, unit="bool_on_off",
               color_mode="background"),
]

use_dashboard = build_dashboard(
    "use-method-eservice", "USE Method — Infrastructure Linux (E-Service)",
    ["use", "infrastructure", "node-exporter", "eservice"],
    use_vars, use_panels)


# ============================================================================
#  DASHBOARD 2 — GOLDEN SIGNALS (Latence, Trafic, Erreurs, Saturation)
#  Source de données : application web instrumentée (job="webapp")
# ============================================================================
gs_vars = [
    var_query("environment", "Environnement",
              "label_values(http_requests_total, environment)"),
    var_query("service", "Service",
              'label_values(http_requests_total{environment="$environment"}, service)'),
    var_query("instance", "Instance",
              'label_values(http_requests_total{service="$service"}, instance)',
              multi=True),
]

gs_panels = [
    text_panel(1, "", "## **Golden Signals** (Google SRE) — Latence · Trafic · "
                  "Erreurs · Saturation\nSource : *application web instrumentée* "
                  "(`boutique-api`).",
               {"h": 3, "w": 24, "x": 0, "y": 0}),

    row(2, "Latence (Latency)", 3),

    # Latence P95 / P99 histogram
    timeseries_panel(10, "Latence P50 / P95 / P99 (histogram_quantile)",
                     [target('histogram_quantile(0.50, sum(rate('
                             'http_request_duration_seconds_bucket{service="$service"}[5m])) by (le))',
                             "P50", "A"),
                      target('histogram_quantile(0.95, sum(rate('
                             'http_request_duration_seconds_bucket{service="$service"}[5m])) by (le))',
                             "P95", "B"),
                      target('histogram_quantile(0.99, sum(rate('
                             'http_request_duration_seconds_bucket{service="$service"}[5m])) by (le))',
                             "P99", "C")],
                     {"h": 8, "w": 16, "x": 0, "y": 4}, unit="s"),

    # Gauge latence P95 (lecture rapide)
    gauge_panel(11, "Latence P95 (s) — seuil 0,5 s",
                'histogram_quantile(0.95, sum(rate('
                'http_request_duration_seconds_bucket{service="$service"}[5m])) by (le))',
                {"h": 8, "w": 8, "x": 16, "y": 4}, unit="s",
                thresholds=[{"color": "green", "value": None},
                            {"color": "yellow", "value": 0.3},
                            {"color": "red", "value": 0.5}],
                legend="P95"),

    row(3, "Trafic (Traffic)", 12),

    # Trafic : requêtes/seconde (counter rate)
    timeseries_panel(20, "Trafic — Requêtes par seconde (req/s)",
                     [target('sum(rate(http_requests_total{service="$service"}[1m])) by (method)',
                             "{{method}}", "A")],
                     {"h": 8, "w": 16, "x": 0, "y": 13}, unit="reqps"),

    # Stat : total req/s instantané
    stat_panel(21, "Débit total (req/s)",
               'sum(rate(http_requests_total{service="$service"}[1m]))',
               {"h": 8, "w": 8, "x": 16, "y": 13}, unit="reqps",
               legend="req/s", color_mode="value"),

    row(4, "Erreurs (Errors)", 21),

    # Taux d'erreurs 5xx (%)
    timeseries_panel(30, "Taux d'erreurs HTTP 5xx (%)",
                     [target('(sum(rate(http_requests_total'
                             '{service="$service", status=~"5.."}[5m])) '
                             '/ sum(rate(http_requests_total{service="$service"}[5m]))) * 100',
                             "% erreurs 5xx", "A")],
                     {"h": 8, "w": 16, "x": 0, "y": 22}, unit="percent"),

    # Répartition des codes HTTP
    stat_panel(31, "Taux d'erreurs actuel (%)",
               '(sum(rate(http_requests_total{service="$service", status=~"5.."}[5m])) '
               '/ sum(rate(http_requests_total{service="$service"}[5m]))) * 100',
               {"h": 8, "w": 8, "x": 16, "y": 22}, unit="percent",
               legend="erreurs", color_mode="background"),

    row(5, "Saturation", 30),

    # Saturation CPU du serveur applicatif (corrélation infra)
    gauge_panel(40, "Saturation CPU srv-web01 (%)",
                '100 - (avg(rate(node_cpu_seconds_total'
                '{hostname="srv-web01", mode="idle"}[5m])) * 100)',
                {"h": 8, "w": 8, "x": 0, "y": 31}, legend="CPU"),

    # Connexions concurrentes (saturation applicative)
    timeseries_panel(41, "Requêtes en cours (in-flight)",
                     [target('http_requests_in_progress{service="$service"}',
                             "in-flight {{instance}}", "A")],
                     {"h": 8, "w": 16, "x": 8, "y": 31}, unit="short"),
]

gs_dashboard = build_dashboard(
    "golden-signals-eservice", "Golden Signals — boutique-api (E-Service)",
    ["golden-signals", "red", "apm", "eservice"],
    gs_vars, gs_panels)


# ----------------------------------------------------------------------------
# Écriture des fichiers
# ----------------------------------------------------------------------------
with open("grafana/dashboards/use-method.json", "w", encoding="utf-8") as f:
    json.dump(use_dashboard, f, indent=2, ensure_ascii=False)

with open("grafana/dashboards/golden-signals.json", "w", encoding="utf-8") as f:
    json.dump(gs_dashboard, f, indent=2, ensure_ascii=False)

print("OK : 2 dashboards générés")
print(" - grafana/dashboards/use-method.json")
print(" - grafana/dashboards/golden-signals.json")
