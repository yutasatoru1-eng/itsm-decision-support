
# ITSM Decision-Support System

An end-to-end predictive analytics pipeline on ~100,000 IT Service Management (ITSM) tickets: data modeling with dbt, long-resolution risk prediction, ticket clustering, similar-incident search, and a rule-based decision engine, all exposed through a multi-page Streamlit app.

Built during an internship in an enterprise IT department. **All data in this repository is synthetic.**

## Features

- **Data warehouse**: PostgreSQL (Docker) with dbt Bronze / Silver / Gold layers
- **Risk prediction**: CatBoost and Random Forest predicting long-resolution tickets, with two model variants (business and conservative)
- **Clustering**: K-Prototypes (mixed numeric/categorical) on ticket attributes
- **Similar-incident search**: TF-IDF + cosine similarity (fully offline)
- **Decision engine**: combines ML risk, SLA urgency and priority into alerts, priority uplifts, reroutes and recommended actions
- **Streamlit app**: Executive Overview, Operational Queue, Clusters, Similar Incidents

## Architecture

```
Synthetic CSV ──► PostgreSQL ──► dbt (Bronze → Silver → Gold)
                                      │
               ┌──────────────────────┼──────────────────────┐
               ▼                      ▼                      ▼
         CatBoost / RF         K-Prototypes             TF-IDF search
         (risk scores)         (ticket clusters)        (similar incidents)
               └──────────────────────┬──────────────────────┘
                                      ▼
                              Decision engine
                           (gold.final_scored_tickets)
                                      ▼
                              Streamlit dashboard
```

## Tech stack

Python · PostgreSQL · Docker · dbt · CatBoost · scikit-learn · K-Prototypes · TF-IDF · Streamlit

## Results

**Risk prediction** (target: `long_resolution_flag`, resolution time above the 75th percentile, 75/25 train/test split):

| Model | Features | ROC-AUC | PR-AUC |
|---|---|---|---|
| A: CatBoost | business (priority, topic, agent group, source) | 0.833 | 0.546 |
| A: Random Forest | business | 0.832 | 0.540 |
| B: CatBoost | conservative (no priority / topic) | 0.739 | 0.467 |
| B: Random Forest | conservative | 0.713 | 0.447 |

**Clustering**: K-Prototypes with k = 5, trained on a 10,000-row sample then applied to all 100,000 tickets. Silhouette 0.279, Davies-Bouldin 1.123, Calinski-Harabasz 4607, better than K-Means on all three metrics.

**Decision engine output**: 22,513 critical alerts, 10,027 priority uplifts, 4,778 reassignment recommendations.

## Methodology notes

Issues found and fixed along the way:

- **Zero-variance target**: no ticket breached its SLA in the dataset, so the target became `long_resolution_flag` (resolution time above the 75th percentile).
- **Data leakage**: raw resolution time was almost fully determined by priority (ROC-AUC = 1.000). Fixed in the Gold dbt model with seeded noise (±60 min, seeded on `ticket_id`) to build `resolution_minutes_realistic`.
- **Redundant risk score**: the raw score tracked priority almost exactly, so `risk_level` is computed as a percentile within each priority group.
- **Duplicate tickets**: a pagination bug inflated tickets by ~33%; fixed by adding Ticket ID as an `ORDER BY` tie-breaker.
- **Status leakage**: features derived from ticket status were removed from the models.

## Limitations

- Synthetic data: results show the pipeline works, not real-world performance.
- Only 800 unique descriptions are repeated across 100k rows, so similar-incident search often returns near-duplicates (similarity ≈ 0.97–1.00).
- Embedding-based search is not included in the offline build.




## Project structure

```
├── docker-compose.yml
├── scripts/             # data loading, modeling, clustering, decision engine
├── dbt/                 # Bronze / Silver / Gold models
├── app/                 # Streamlit multi-page app
├── requirements.txt
└── .env.example
```

## Screenshots


<img src="https://github.com/user-attachments/assets/778e1a82-eab9-4bac-9ab5-82cdefeabacf" alt="Executive Overview" width="800" />
<img src="https://github.com/user-attachments/assets/bbdeebee-2a5b-4f30-8cfb-7885e4028b5d" alt="Operational Queue" width="800" />
<img src="https://github.com/user-attachments/assets/26f7b53e-70a6-4ac7-9ea9-2d47d69a828f" alt="Clusters" width="800" />
<img src="https://github.com/user-attachments/assets/a186f930-3c31-43e8-9f76-a0af7dc1783d" alt="Similar Incidents" width="800" />



## Author

Ahmed Mofadel, IT Engineering (Data Science), ESITH, Morocco

## License

MIT
