# Projet ITSM Predictive — Guide complet

Ce README regroupe **toutes les étapes** du projet, dans l'ordre. Au fur et à mesure qu'on
avance, de nouvelles sections seront ajoutées ici — un seul fichier à suivre, pas besoin
d'en chercher plusieurs.

## Structure du dossier

```
itsm_project/
├── README.md                 -> ce fichier (guide complet, toutes les étapes)
├── docker-compose.yml        -> lance PostgreSQL en local
├── requirements.txt          -> librairies Python nécessaires
├── data/
│   └── (ton fichier CSV va ici)
├── scripts/
│   └── load_csv_to_bronze.py -> Étape 1 : ingestion
└── dbt_project/
    ├── dbt_project.yml
    ├── profiles.yml
    ├── macros/
    └── models/
        ├── silver/            -> Étape 2 : nettoyage
        └── gold/               -> Étape 3 : à venir
```

## Pré-requis généraux

1. **Docker Desktop** installé : https://www.docker.com/products/docker-desktop/
2. **Python 3.10+** installé
3. Toutes les librairies : `pip install -r requirements.txt`
   *(installe pandas, sqlalchemy, psycopg2-binary, dbt-core, dbt-postgres)*

---

## Étape 1 — Ingestion des données brutes (couche Bronze)

**Ce que ça fait :** copie le CSV original tel quel dans PostgreSQL, sans rien modifier.
Sert de sauvegarde fidèle de la source.

### 1.1 Lancer la base de données

Place ton fichier `ITSM_Dataset.csv` dans `data/`, renommé `ITSM_Dataset_raw.csv`.

Dans le dossier `itsm_project/` :
```powershell
docker compose up -d
docker compose ps
```
Vérifie que `itsm_postgres` est **healthy**. (Chez toi, la base écoute sur le port **5433**,
pas 5432, à cause d'un conflit de port réglé précédemment.)

### 1.2 Lancer le script d'ingestion

```powershell
cd scripts
py load_csv_to_bronze.py
```

Résultat attendu :
```
5) Verification...
   -> 100000 lignes presentes dans bronze.itsm_tickets_raw.
```

### 1.3 Vérifier (optionnel)

Dans pgAdmin (http://localhost:5050, `admin@admin.com` / `admin`) :
```
postgres → Databases → itsm_db → Schemas → bronze → Tables → itsm_tickets_raw
```

---

## Étape 2 — Nettoyage des données (couche Silver) avec dbt

**Ce que ça fait :** transforme les données brutes en version propre : dates converties en
vrais timestamps, espaces retirés, valeurs vides devenues `NULL`, priorité encodée en
nombre (`priority_rank`), doublons éventuels supprimés.

C'est l'équivalent SQL de ce qu'on avait fait en pandas dans le notebook, mais réutilisable
et ré-exécutable avec **dbt**.

### 2.1 Vérifier la connexion

```powershell
cd dbt_project
dbt debug --profiles-dir .
```
Résultat attendu : `All checks passed!`

### 2.2 Construire la couche Silver

```powershell
dbt run --profiles-dir .
```

Résultat attendu :
```
1 of 1 OK created sql table model silver.silver_itsm_tickets ... [SELECT 100000 in 2.05s]
Completed successfully
```

*(Un avertissement mentionnant `models.itsm_dbt.gold` est normal à ce stade — la couche
Gold n'existe pas encore, elle arrive à l'étape 3.)*

### 2.3 Vérifier

Dans pgAdmin :
```
postgres → Databases → itsm_db → Schemas → silver → Tables → silver_itsm_tickets
```

Ou en SQL (Query Tool) :
```sql
SELECT ticket_id, priority, priority_rank, created_time, has_solution
FROM silver.silver_itsm_tickets
LIMIT 5;
```
`created_time` doit s'afficher comme une vraie date, pas du texte brut.

---

## Étape 3 — Variables pour le Machine Learning (couche Gold)

**Ce que ça fait :** transforme les données propres de Silver en variables directement
utilisables par un modèle de prédiction :

- **Durées réelles** en minutes : `first_response_minutes`, `resolution_minutes`, `close_minutes`
- **Variables temporelles** : `created_hour`, `created_dayofweek`, `created_month`, `created_date`
- **Marge SLA** (`sla_margin_resolution_min`) — gardée à titre informatif, même si on sait
  qu'elle est toujours positive dans ce dataset (aucun dépassement)
- **Longueur de la description** (`description_length`) — utile plus tard pour le module NLP
- **`long_resolution_flag`** — **la cible de prédiction**, calculée automatiquement

### Pourquoi cette cible et pas "dépassement SLA" ?

On a vérifié plus tôt que dans ce dataset, **aucun ticket ne dépasse jamais son SLA**
(la marge est toujours ≥ 0). Une cible sans variance ne peut pas être apprise par un modèle
— exactement le problème que Wijdane avait rencontré dans son PFE. On applique donc la même
solution qu'elle : remplacer "dépassement SLA" par **"risque de résolution longue"**.

**Définition retenue :** un ticket est marqué `long_resolution_flag = 1` si sa durée de
résolution dépasse le 75ᵉ percentile de l'ensemble des tickets (calculé automatiquement sur
les données, pas fixé à la main). Sinon `0`.

**Résultat obtenu (vérifié) :** répartition **75% / 25%** — une vraie cible exploitable pour
un modèle de classification, contrairement au dépassement SLA qui donnait 0% partout.

### 3.1 Construire la couche Gold

```powershell
cd dbt_project
dbt run --profiles-dir .
```

Ça reconstruit **silver** et **gold** ensemble (dbt suit automatiquement l'ordre grâce à la
référence `{{ ref('silver_itsm_tickets') }}` dans le modèle Gold). Pour ne reconstruire que
Gold :

```powershell
dbt run --profiles-dir . --select gold_itsm_tickets
```

Résultat attendu :
```
1 of 1 OK created sql table model gold.gold_itsm_tickets ... [SELECT 100000 in 1.29s]
Completed successfully
```

### 3.2 Vérifier

```sql
-- Répartition de la cible : doit donner environ 75% / 25%
SELECT long_resolution_flag, COUNT(*),
       ROUND(100.0*COUNT(*)/SUM(COUNT(*)) OVER(), 1) as pct
FROM gold.gold_itsm_tickets
GROUP BY long_resolution_flag;
```

---

## Étape 4 — Entraînement du modèle (CatBoost vs Random Forest)

**Script :** `scripts/train_model.py`

### Correction du dataset : bruit réaliste ajouté (couche Gold)

Avec la durée de résolution brute, `priority` la déterminait à ~6 min près → score
parfait (1.000), non représentatif. **Corrigé dans `gold_itsm_tickets.sql`** : un bruit
déterministe (±60 min, seedé sur `ticket_id`, reproductible) est ajouté à
`resolution_minutes_realistic`, qui sert maintenant de base au calcul de la cible
`long_resolution_flag`. Simule la variabilité réelle (charge de travail, complexité
imprévue) absente du dataset synthétique.

### Résultat final (split temporel 80/20)

**Modèle A "business" (priority, topic, agent_group, source) — retenu comme officiel**

| Modèle | ROC-AUC | PR-AUC |
|---|---|---|
### Dataset v2 (données actuellement dans data/)

`data/ITSM_Dataset_raw.csv` contient désormais la **v2** (`generate_dataset_v2.py`) :
bruit réel dans les durées (plus de déterminisme priority→durée), vrais breaches SLA
(30-37% selon priorité, au lieu de 0%), 2560 descriptions uniques (vs 800).
Résultat sur v2 : **ROC-AUC 0.771** (CatBoost) — sain, sans leakage.

| Modèle | ROC-AUC | PR-AUC |
|---|---|---|
| CatBoost | 0.833 (v1) / 0.771 (v2) | 0.546 / 0.447 |
| Random Forest | 0.832 (v1) / 0.771 (v2) | 0.540 / 0.450 |

**Modèle B "conservateur" (sans priority/topic), gardé en comparaison**

| Modèle | ROC-AUC | PR-AUC |
|---|---|---|
| CatBoost | 0.739 | 0.467 |
| Random Forest | 0.713 | 0.447 |

CatBoost et Random Forest sont proches ici (0.833 vs 0.832) — logique : peu de
catégorielles à forte cardinalité, donc l'avantage habituel de CatBoost sur l'encodage
est moins marqué. L'essentiel : score crédible, colonnes métier, pas de leakage.

### Lancer

```powershell
cd dbt_project && dbt run --profiles-dir . --select gold_itsm_tickets
cd ../scripts && python train_model.py
```

---

## Étape 5 — Clustering (K-Prototypes)

**Script :** `scripts/cluster_tickets.py`. Regroupe les tickets par profils similaires,
sur un échantillon de 10 000 lignes (mélange numérique + catégoriel, comme dans le
rapport de référence).

| Méthode | k | Silhouette | Davies-Bouldin | Calinski-Harabasz |
|---|---|---|---|---|
| K-Prototypes | 4 | 0.275 | 1.204 | 4680 |
| K-Prototypes | 5 | 0.279 | 1.123 | 4607 |
| K-Means | 5 | 0.210 | 1.668 | 3030 |

K-Prototypes retenu (meilleur sur les 3 métriques) — k=5 gardé pour la lisibilité métier.
5 profils obtenus (ex: cluster 1 = Critical/Network Issue, résolution rapide ~78 min).

### Lancer

```powershell
cd scripts
python cluster_tickets.py
```

Sauvegarde `clustered_tickets_sample.csv`, `kprototypes_k5.joblib`.

---

## Étape 6 — App multi-pages + Moteur de décision (au-delà du simple dashboard)

Plutôt qu'un dashboard isolé, l'app combine un **moteur de décision** (règles métier
interprétables) avec 4 pages connectées : Executive Overview, Operational Queue,
Clusters, Similar Incidents (NLP intégré).

### Moteur de décision — `scripts/decision_engine.py`

Combine risque ML, urgence SLA et priorité en une couche métier :

- **`sla_urgency`** : VERY_URGENT (≤60min) / URGENT (≤180min) / NORMAL, depuis `sla_window_minutes`
- **`risk_level`** : calculé en **percentile relatif à chaque priorité** (pas un seuil absolu) —
  découverte : le score brut est presque une redite de `priority` (Critical≈0, Low≈0.59),
  donc redondant. Le percentile intra-groupe restaure un signal indépendant.
- **`alert_severity`** : CRITICAL/HIGH/MEDIUM/LOW, règles combinant risque + urgence + priorité
- **`recommended_action`**, **`priority_uplift`**, **`reroute_to`**, **`notify_flag`**

**Résultats (testés) :** 22 513 alertes CRITICAL, 10 027 priority uplift, 4 778 recommandations
de réaffectation. Persisté dans `gold.final_scored_tickets`.

### Clustering appliqué à tous les tickets — `scripts/cluster_tickets.py`

K-Prototypes (k=5) entraîné sur un échantillon de 10k puis **appliqué aux 100 000 tickets**
(`.predict()`), persisté dans `gold.ticket_clusters`.

### Recherche NLP — `scripts/find_similar_tickets.py`

TF-IDF + similarité cosinus (pas d'embeddings : aucun modèle à télécharger, fonctionne
hors-ligne). **Limite connue :** seulement 800 descriptions uniques (répétées sur 100k
lignes) → résultats souvent quasi-doublons (similarité ~0.97-1.000). Intégré aussi comme
page interactive dans l'app.

### Lancer (ordre important)

```powershell
cd scripts
python train_model.py          # genere catboost_long_resolution.joblib
python cluster_tickets.py      # genere gold.ticket_clusters (K-Prototypes applique aux 100k tickets)
python decision_engine.py      # genere gold.final_scored_tickets
cd ../dashboard
streamlit run app.py
```

### Pages de l'app

| Page | Contenu |
|---|---|
| **Executive Overview** (`app.py`) | KPIs (dont alertes CRITICAL), répartition des sévérités, réaffectations |
| **Operational Queue** | Recherche par Ticket ID → détail complet (risque, urgence, action) + cluster + file filtrable |
| **Clusters** | Profils des 5 clusters (K-Prototypes) appliqués à tous les tickets, alertes par cluster |
| **Similar Incidents** | Recherche NLP (TF-IDF) interactive, avec avertissement sur la limite du dataset |

Testé : les 4 pages répondent (HTTP 200), navigation multi-pages Streamlit fonctionnelle.

---

## Livrables finaux

- **Rapport Word** : `Rapport_Stage_Ahmed_Mofadel.docx` — synthèse du projet
- **Présentation** : `Presentation_Stage_Ahmed_Mofadel.pptx` — 12 slides, chaque étape/algorithme expliqué
- **App multi-pages** : ce dépôt, `dashboard/` (Executive Overview, Operational Queue, Clusters, Similar Incidents)
