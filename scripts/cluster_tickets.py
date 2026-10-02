"""
cluster_tickets.py
-------------------
ETAPE 5 : clustering (K-Prototypes) pour regrouper les tickets par profils similaires.

K-Prototypes gere directement le melange de variables numeriques (duree, heure...)
et categorielles (priority, topic...), contrairement a K-Means qui exige un encodage.
Compare a K-Means (baseline) sur un echantillon, comme dans le rapport de reference.
"""

import pandas as pd
from sqlalchemy import create_engine
from kmodes.kprototypes import KPrototypes
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score, davies_bouldin_score, calinski_harabasz_score
import joblib

DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME = "postgres", "itsm_pwd", "localhost", "5433", "itsm_db"

CAT_COLS = ["priority", "topic", "agent_group", "source"]
NUM_COLS = ["resolution_minutes", "created_hour", "description_length"]
SAMPLE_SIZE = 10000


def main():
    engine = create_engine(f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
    print("1) Lecture d'un echantillon de gold.gold_itsm_tickets...")
    df = pd.read_sql(
        f"SELECT ticket_id, {', '.join(CAT_COLS + NUM_COLS)} FROM gold.gold_itsm_tickets "
        f"WHERE resolution_minutes IS NOT NULL ORDER BY random() LIMIT {SAMPLE_SIZE}",
        engine
    )
    df = df.dropna(subset=CAT_COLS + NUM_COLS).reset_index(drop=True)
    print(f"   -> {len(df)} lignes echantillonnees")

    # K-Prototypes : numeriques standardises + categorielles brutes
    # Le scaler est conserve (fit sur l'echantillon) pour etre reapplique tel quel
    # a l'ensemble des 100 000 tickets plus bas -> memes unites/echelle qu'a l'entrainement.
    scaler = StandardScaler()
    X_num = scaler.fit_transform(df[NUM_COLS])
    X_cat = df[CAT_COLS].astype(str).values
    X_mixed = pd.concat(
        [pd.DataFrame(X_num, columns=NUM_COLS), pd.DataFrame(X_cat, columns=CAT_COLS)], axis=1
    ).values
    cat_idx = list(range(len(NUM_COLS), len(NUM_COLS) + len(CAT_COLS)))

    print("\n2) Comparaison K-Prototypes (k=4, k=5) vs K-Means (k=5)...")
    results = []
    for k in [4, 5]:
        kp = KPrototypes(n_clusters=k, init="Cao", n_init=3, random_state=42, verbose=0)
        labels = kp.fit_predict(X_mixed, categorical=cat_idx)
        sil = silhouette_score(X_num, labels)
        db = davies_bouldin_score(X_num, labels)
        ch = calinski_harabasz_score(X_num, labels)
        results.append(("K-Prototypes", k, sil, db, ch))
        if k == 5:
            df["cluster"] = labels
            joblib.dump(kp, "kprototypes_k5.joblib")
            joblib.dump(scaler, "scaler_kprototypes_k5.joblib")

    km = KMeans(n_clusters=5, random_state=42, n_init=10)
    X_km = pd.get_dummies(df[NUM_COLS + CAT_COLS], columns=CAT_COLS)
    labels_km = km.fit_predict(X_km)
    sil = silhouette_score(X_num, labels_km)
    db = davies_bouldin_score(X_num, labels_km)
    ch = calinski_harabasz_score(X_num, labels_km)
    results.append(("K-Means", 5, sil, db, ch))

    print(f"\n{'Methode':15s}{'k':5s}{'Silhouette':12s}{'DaviesBouldin':15s}{'CalinskiHarabasz':18s}")
    for name, k, sil, db, ch in results:
        print(f"{name:15s}{k:<5d}{sil:<12.4f}{db:<15.4f}{ch:<18.2f}")

    print("\n3) Profil des clusters (K-Prototypes k=5) :")
    profile = df.groupby("cluster").agg(
        tickets=("ticket_id", "count"),
        avg_resolution_min=("resolution_minutes", "mean"),
        top_priority=("priority", lambda x: x.mode()[0]),
        top_topic=("topic", lambda x: x.mode()[0]),
    ).round(1)
    print(profile.to_string())

    df.to_csv("clustered_tickets_sample.csv", index=False)
    print("\n4) Sauvegarde -> clustered_tickets_sample.csv, kprototypes_k5.joblib")

    # --- Appliquer le clustering (deja entraine) a TOUS les tickets ---
    print("\n5) Application du clustering k=5 a l'ensemble des 100 000 tickets...")
    kp_final = joblib.load("kprototypes_k5.joblib")
    scaler_final = joblib.load("scaler_kprototypes_k5.joblib")
    full = pd.read_sql(f"SELECT ticket_id, {', '.join(CAT_COLS + NUM_COLS)} FROM gold.gold_itsm_tickets", engine)
    full = full.dropna(subset=CAT_COLS + NUM_COLS).reset_index(drop=True)
    # transform() (pas fit_transform) : reutilise la moyenne/ecart-type de l'echantillon
    # d'entrainement, sinon les distances ne sont plus sur la meme echelle que le modele appris.
    X_num_full = scaler_final.transform(full[NUM_COLS])
    X_cat_full = full[CAT_COLS].astype(str).values
    X_full = pd.concat(
        [pd.DataFrame(X_num_full, columns=NUM_COLS), pd.DataFrame(X_cat_full, columns=CAT_COLS)], axis=1
    ).values
    full["cluster"] = kp_final.predict(X_full, categorical=cat_idx)
    full[["ticket_id", "cluster"]].to_sql("ticket_clusters", engine, schema="gold", if_exists="replace", index=False)
    print(f"   -> {len(full)} tickets assignes a un cluster -> table gold.ticket_clusters")


if __name__ == "__main__":
    main()
