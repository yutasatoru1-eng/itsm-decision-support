"""
train_model.py
---------------
ETAPE 4 : entrainement du modele de prediction (risque de resolution longue).

La cible (gold.gold_itsm_tickets.long_resolution_flag) est desormais basee sur une
duree de resolution "realiste" (bruit deterministe +/-60 min ajoute dans le modele
dbt Gold), pour eviter le leakage total observe avec la duree brute (priority
determinait resolution_minutes a ~6 min pres -> score parfait, non representatif).

Deux modeles compares :
  A "business" : priority, topic, agent_group, source (+ priority_rank, created_hour,
      description_length, has_solution) -> RETENU comme modele officiel
  B "conservateur" : sans priority/topic -> garde a titre de comparaison
"""

import pandas as pd
from sqlalchemy import create_engine
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score, average_precision_score, confusion_matrix
from catboost import CatBoostClassifier
import joblib

DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME = "postgres", "itsm_pwd", "localhost", "5433", "itsm_db"

MODELS = {
    "business (priority/topic/agent_group/source)": {
        "cat": ["priority", "topic", "agent_group", "source"],
        "num": ["priority_rank", "created_hour", "description_length", "has_solution"],
    },
}
TARGET = "long_resolution_flag"
ALL_COLS = sorted(set(sum([m["cat"] + m["num"] for m in MODELS.values()], [])))


def evaluate(name, X_train, y_train, X_test, y_test, cat_features):
    cat_model = CatBoostClassifier(iterations=300, depth=6, learning_rate=0.1,
                                    cat_features=cat_features, verbose=False, random_state=42)
    cat_model.fit(X_train, y_train)
    cat_proba = cat_model.predict_proba(X_test)[:, 1]

    X_train_rf = pd.get_dummies(X_train, columns=cat_features) if cat_features else X_train
    X_test_rf = pd.get_dummies(X_test, columns=cat_features) if cat_features else X_test
    X_test_rf = X_test_rf.reindex(columns=X_train_rf.columns, fill_value=0)
    rf_model = RandomForestClassifier(n_estimators=300, max_depth=10, random_state=42, n_jobs=-1)
    rf_model.fit(X_train_rf, y_train)
    rf_proba = rf_model.predict_proba(X_test_rf)[:, 1]

    print(f"\n=== Modele {name} ===")
    for algo, proba in [("CatBoost", cat_proba), ("Random Forest", rf_proba)]:
        roc = roc_auc_score(y_test, proba)
        pr = average_precision_score(y_test, proba)
        tn, fp, fn, tp = confusion_matrix(y_test, (proba >= 0.5).astype(int)).ravel()
        print(f"   {algo:15s} ROC-AUC={roc:.3f}  PR-AUC={pr:.3f}  TP={tp} FP={fp} FN={fn} TN={tn}")
    return cat_model


def main():
    engine = create_engine(f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
    print("1) Lecture de gold.gold_itsm_tickets...")
    df = pd.read_sql(
        f"SELECT {', '.join(ALL_COLS + [TARGET, 'created_time'])} FROM gold.gold_itsm_tickets", engine
    )
    df = df.sort_values("created_time")
    split_idx = int(len(df) * 0.8)
    train_df, test_df = df.iloc[:split_idx], df.iloc[split_idx:]
    print(f"   -> Train: {len(train_df)} | Test: {len(test_df)}")

    best_model = None
    for name, cfg in MODELS.items():
        cols = cfg["cat"] + cfg["num"]
        X_train, y_train = train_df[cols].copy(), train_df[TARGET]
        X_test, y_test = test_df[cols].copy(), test_df[TARGET]
        for c in cfg["cat"]:
            X_train[c] = X_train[c].fillna("Unknown")
            X_test[c] = X_test[c].fillna("Unknown")
        model = evaluate(name, X_train, y_train, X_test, y_test, cfg["cat"])
        if "business" in name:
            best_model = model

    joblib.dump(best_model, "catboost_long_resolution.joblib")
    print("\nModele officiel retenu = A (business: priority/topic/agent_group/source)")
    print("-> catboost_long_resolution.joblib")


if __name__ == "__main__":
    main()
