#!/usr/bin/env python3
# =============================================================================
#  gen_grafana_alerts.py — Génère le provisioning de l'alerting unifié Grafana
#  Livrable L4 : 5 alertes natives avec seuils contextuels (WARNING + CRITICAL)
#                et notification Slack.
#
#  Produit 3 fichiers dans grafana/provisioning/alerting/ :
#     - rules.yaml            : les 5 règles d'alerte
#     - contactpoints.yaml    : le point de contact Slack
#     - policies.yaml         : la politique de routage des notifications
#
#  Doc : https://grafana.com/docs/grafana/latest/alerting/set-up/provision-alerting-resources/
# =============================================================================
import yaml

DS_UID = "prometheus-eservice"   # doit correspondre à l'uid de la datasource


def rule(uid, title, expr, op, threshold, severity, dur, summary, desc):
    """
    Construit une règle d'alerte Grafana complète.
      - refId A : requête PromQL instantanée vers Prometheus
      - refId C : expression de seuil (threshold) qui compare A au seuil
      Le champ 'condition' pointe vers C : l'alerte se déclenche si C est vrai.
    """
    return {
        "uid": uid,
        "title": title,
        "condition": "C",
        "for": dur,
        "noDataState": "NoData",      # comportement si pas de données
        "execErrState": "Error",      # comportement si erreur d'exécution
        "labels": {"severity": severity},
        "annotations": {"summary": summary, "description": desc},
        "data": [
            {
                "refId": "A",
                "relativeTimeRange": {"from": 600, "to": 0},
                "datasourceUid": DS_UID,
                "model": {
                    "refId": "A",
                    "editorMode": "code",
                    "expr": expr,
                    "instant": True,
                    "range": False,
                    "intervalMs": 1000,
                    "maxDataPoints": 43200,
                },
            },
            {
                "refId": "C",
                "relativeTimeRange": {"from": 600, "to": 0},
                "datasourceUid": "__expr__",   # moteur d'expressions interne Grafana
                "model": {
                    "refId": "C",
                    "type": "threshold",
                    "expression": "A",
                    "conditions": [{
                        "type": "query",
                        "evaluator": {"type": op, "params": [threshold]},
                    }],
                },
            },
        ],
    }


# ----------------------------------------------------------------------------
# Les 5 alertes natives (seuils justifiés d'après le cours : slides 11-13, 21-22)
# ----------------------------------------------------------------------------
rules = [
    # 1. CPU élevé — WARNING à 85% (USE : Utilization, seuil cours = 80%)
    rule("alert-cpu-warning", "1. CPU élevé (WARNING)",
         '100 - (avg by (hostname) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)',
         "gt", 85, "warning", "5m",
         "CPU > 85% sur {{ $labels.hostname }}",
         "Utilisation CPU supérieure à 85% pendant 5 min. Seuil USE recommandé : 80%."),

    # 2. Mémoire saturée — CRITICAL à 90% (USE : Saturation)
    rule("alert-mem-critical", "2. Mémoire saturée (CRITICAL)",
         '(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100',
         "gt", 90, "critical", "5m",
         "Mémoire > 90% sur {{ $labels.hostname }}",
         "RAM utilisée à plus de 90% pendant 5 min : risque d'OOM-killer et de swap."),

    # 3. Disque faible — WARNING à 15% d'espace libre (USE : Saturation)
    rule("alert-disk-warning", "3. Espace disque faible (WARNING)",
         '(node_filesystem_avail_bytes{mountpoint="/"} '
         '/ node_filesystem_size_bytes{mountpoint="/"}) * 100',
         "lt", 15, "warning", "10m",
         "Disque / < 15% libre sur {{ $labels.hostname }}",
         "Moins de 15% d'espace libre sur la partition racine pendant 10 min."),

    # 4. Latence P95 — WARNING à 500 ms (Golden Signals : Latence)
    rule("alert-latency-warning", "4. Latence P95 dégradée (WARNING)",
         'histogram_quantile(0.95, sum(rate('
         'http_request_duration_seconds_bucket[5m])) by (le))',
         "gt", 0.5, "warning", "3m",
         "Latence P95 > 500 ms sur boutique-api",
         "Le 95e percentile de latence dépasse 0,5 s. Seuil Golden Signals = 500 ms."),

    # 5. Taux d'erreurs 5xx — CRITICAL à 5% (RED / Golden Signals : Erreurs)
    rule("alert-errors-critical", "5. Taux d'erreurs HTTP élevé (CRITICAL)",
         '(sum(rate(http_requests_total{status=~"5.."}[5m])) '
         '/ sum(rate(http_requests_total[5m]))) * 100',
         "gt", 5, "critical", "2m",
         "Taux d'erreurs 5xx > 5% sur boutique-api",
         "Plus de 5% de réponses 5xx pendant 2 min. Seuil Golden Signals = 0,1%-5%."),
]

alert_rules = {
    "apiVersion": 1,
    "groups": [{
        "orgId": 1,
        "name": "eservice-alertes",
        "folder": "E-Service Linux",
        "interval": "1m",     # fréquence d'évaluation du groupe
        "rules": rules,
    }],
}

# ----------------------------------------------------------------------------
# Point de contact Slack (où partent les notifications)
# ----------------------------------------------------------------------------
contact_points = {
    "apiVersion": 1,
    "contactPoints": [{
        "orgId": 1,
        "name": "slack-eservice",
        "receivers": [{
            "uid": "slack-eservice-recv",
            "type": "slack",
            "settings": {
                # Remplacez par VOTRE webhook entrant Slack.
                "url": "https://hooks.slack.com/services/XXXX/YYYY/ZZZZ",
                "recipient": "#monitoring",
                "title": "{{ .CommonLabels.alertname }} — {{ .CommonLabels.severity }}",
                "text": "{{ range .Alerts }}{{ .Annotations.summary }}\n"
                        "{{ .Annotations.description }}\n{{ end }}",
            },
            "disableResolveMessage": False,
        }],
    }],
}

# ----------------------------------------------------------------------------
# Politique de notification : tout part vers Slack, regroupé par alerte+hôte.
# ----------------------------------------------------------------------------
policies = {
    "apiVersion": 1,
    "policies": [{
        "orgId": 1,
        "receiver": "slack-eservice",
        "group_by": ["alertname", "hostname"],
        "group_wait": "30s",
        "group_interval": "5m",
        "repeat_interval": "4h",
        "routes": [{
            # Le critique est ré-notifié plus souvent (escalade).
            "receiver": "slack-eservice",
            "object_matchers": [["severity", "=", "critical"]],
            "group_wait": "10s",
            "repeat_interval": "1h",
        }],
    }],
}

for fname, data in [("rules.yaml", alert_rules),
                    ("contactpoints.yaml", contact_points),
                    ("policies.yaml", policies)]:
    with open(f"grafana/provisioning/alerting/{fname}", "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False, width=100)
    print(f"OK : grafana/provisioning/alerting/{fname}")
