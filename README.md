
# ITSM Decision-Support System

An end-to-end predictive analytics pipeline on ~100,000 IT Service Management (ITSM) tickets: data modeling with dbt, SLA-risk prediction, ticket clustering, similar-incident search, and a rule-based decision engine, all exposed through a multi-page Streamlit app.

Built during an internship in an enterprise IT department. **All data in this repository is synthetic.**

## Features

- **Data warehouse**: PostgreSQL (Docker) with dbt Bronze / Silver / Gold layers
- **Risk prediction**: CatBoost and Random Forest predicting long-resolution tickets
- **Clustering**: K-Prototypes (mixed numeric/categorical) on ticket attributes
- **Similar-incident search**: TF-IDF + cosine similarity (fully offline)
- **Decision engine**: combines ML risk, SLA urgency and priority into alerts, priority uplifts, reroutes and recommended actions
- **Streamlit app**: Executive Overview, Operational Queue, Clusters, Similar Incidents

## Architecture

```
Synthetic generator ──► PostgreSQL ──► dbt (Bronze → Silver → Gold)
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

## Results (dataset v2)

| Component | Metric | Value |
|---|---|---|
| CatBoost (business features) | ROC-AUC / PR-AUC | 0.771 / 0.447 |
| K-Prototypes, k = 5 | Silhouette / Davies-Bouldin / Calinski-Harabasz | 0.279 / 1.123 / 4607 |
| Decision engine output | Critical alerts / priority uplifts / reroutes | 22,513 / 10,027 / 4,778 |

K-Prototypes outperformed K-Means on all three clustering metrics. The decision-engine counts come from the first (v1) dataset run.

## Methodology notes

Issues found and fixed along the way:

- **Zero-variance target**: no ticket breached its SLA in the first dataset, so the target became `long_resolution_flag` (resolution time above the 75th percentile, 75/25 split).
- **Data leakage**: raw resolution time was almost fully determined by priority (ROC-AUC = 1.000). Fixed with seeded noise (±60 min, seeded on `ticket_id`) to build `resolution_minutes_realistic`.
- **Redundant risk score**: the raw score tracked priority almost exactly, so `risk_level` is computed as a percentile within each priority group.
- **Duplicate tickets**: a pagination bug inflated tickets by ~33%; fixed by adding Ticket ID as an `ORDER BY` tie-breaker.
- **Dataset v2**: realistic duration noise, real SLA breaches (30–37% by priority) and 2,560 unique descriptions (vs. 800) for a cleaner evaluation.

## Limitations

- Synthetic data: results show the pipeline works, not real-world performance.
- Similar-incident search can return near-duplicates (similarity ≈ 0.97–1.00) because descriptions repeat across tickets.
- Embedding-based search is not included in the offline build.



## Project structure

```
├── docker-compose.yml
├── generate_dataset_v2.py
├── dbt/                 # Bronze / Silver / Gold models
├── decision_engine.py
├── app/                 # Streamlit multi-page app
├── requirements.txt
└── .env.example
```

## Screenshots

<img width="931" height="200" alt="Screenshot 2026-10-02 145200" src="https://github.com/user-attachments/assets/648811e5-abb1-42a3-a968-070c529ec403" />
<img width="923" height="200" alt="Screenshot 2026-10-02 145224" src="https://github.com/user-attachments/assets/8c55eebb-4500-4cc0-b70c-e254eee4db27" />
<img width="933" height="200" alt="Screenshot 2026-10-02 145300" src="https://github.com/user-attachments/assets/ab06534b-80af-449d-aba0-3cc025c640ab" />
<img width="927" height="200" alt="Screenshot 2026-10-02 145922" src="https://github.com/user-attachments/assets/c93ebbb9-8d00-4df8-88af-72bc482a8ae4" />


## Author

Ahmed Mofadel, Industrial Engineering (Data Science), ESITH, Morocco

## License

MIT
