# Projet 01 — Stack Prometheus + Grafana sur Infrastructure Linux

**E-Service Linux — IAI ING2 — Année académique 2025-2026**
Monitoring & Observabilité Linux

---

## Contenu du package

```
projet01-monitoring/
├── README.md                          Ce fichier
│
├── prometheus/
│   ├── prometheus.yml                 Config Prometheus (collecte 3 nœuds + webapp)
│   └── alert.rules.yml                Règles d'alerte Prometheus → AlertManager
│
├── alertmanager/
│   └── alertmanager.yml               Routage Slack + e-mail, inhibition, groupement
│
├── grafana/
│   ├── provisioning/
│   │   ├── datasources/datasources.yml    [L3] Datasource Prometheus as-code
│   │   ├── dashboards/dashboards.yml       [L3] Chargement auto des dashboards
│   │   └── alerting/
│   │       ├── rules.yaml                   [L4] 5 alertes natives Grafana
│   │       ├── contactpoints.yaml           [L4] Point de contact Slack
│   │       └── policies.yaml                [L4] Politique de notification
│   └── dashboards/
│       ├── use-method.json                  [L2] Dashboard USE
│       └── golden-signals.json              [L2] Dashboard Golden Signals
│
├── node_exporter/
│   └── node_exporter.service          Unité systemd Node Exporter
│
├── webapp/
│   ├── app.py                         Application instrumentée (Golden Signals)
│   ├── requirements.txt               Dépendances Python
│   └── generer_trafic.py              Injecteur de charge pour la démo
│
├── scripts/
│   ├── install_node_exporter.sh       Installe Node Exporter (3 nœuds)
│   ├── install_prometheus.sh          Installe Prometheus + AlertManager
│   ├── install_grafana.sh             Installe Grafana + provisioning
│   ├── install_webapp.sh              Déploie boutique-api
│   ├── gen_dashboards.py              (re)génère les 2 dashboards JSON
│   └── gen_grafana_alerts.py          (re)génère les alertes natives
│
└── docs/
    ├── Rapport_Architecture.docx       [L1] Rapport d'architecture
    └── Guide_Deploiement.docx          Guide pas-à-pas + zones de captures
```

## Correspondance avec les livrables attendus

| Livrable | Fichiers concernés |
|----------|--------------------|
| L1 — Rapport d'architecture        | `docs/Rapport_Architecture.docx` |
| L2 — Dashboards JSON (USE + Golden)| `grafana/dashboards/*.json` |
| L3 — Provisioning Grafana          | `grafana/provisioning/datasources/` et `dashboards/` |
| L4 — 5 règles d'alerte             | `grafana/provisioning/alerting/*.yaml` |
| L5 — Démonstration live            | Plan détaillé dans le Guide de déploiement |

## Ordre de déploiement recommandé

1. Préparer les 3 VM (cf. Guide de déploiement, section VirtualBox)
2. `install_node_exporter.sh` sur les 3 nœuds
3. `install_webapp.sh` sur srv-web01
4. `install_prometheus.sh` sur srv-monitor
5. `install_grafana.sh` sur srv-monitor
6. Lancer `generer_trafic.py` pour alimenter les courbes Golden Signals
