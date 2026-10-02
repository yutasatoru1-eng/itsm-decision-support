"""
decision_engine.py
-------------------
ETAPE 8 : moteur de decision (regles metier).

Combine le score de risque (CatBoost), la pression SLA et la priorite pour
produire : urgence SLA, severite d'alerte, action recommandee, et des files
operationnelles (priority uplift, reroute, notify, problem candidate).

Regles inspirees du rapport de reference (approche interpretable, pas de ML
ici : des if/else transparents, faciles a expliquer a un jury).
"""

import pandas as pd
from sqlalchemy import create_engine
import joblib

DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME = "postgres", "itsm_pwd", "localhost", "5433", "itsm_db"
CAT_FEATURES = ["priority", "topic", "agent_group", "source"]
NUM_FEATURES = ["priority_rank", "created_hour", "description_length", "has_solution"]

SPECIALIST_ROUTE = {"Network Issue": "Network Ops", "Software Bug": "Development", "Hardware Failure": "IT Support"}


def sla_urgency(window):
    if pd.isna(window):
        return "UNKNOWN"
    if window <= 60:
        return "VERY_URGENT"
    if window <= 180:
        return "URGENT"
    return "NORMAL"


def alert_severity(risk, sla, priority):
    if priority == "Critical" and sla == "VERY_URGENT" and risk in ("MEDIUM", "HIGH"):
        return "CRITICAL"
    if risk == "HIGH" and sla in ("VERY_URGENT", "URGENT"):
        return "CRITICAL"
    if risk == "HIGH":
        return "HIGH"
    if risk == "MEDIUM" and sla == "VERY_URGENT":
        return "HIGH"
    if risk == "MEDIUM" and sla == "URGENT":
        return "MEDIUM"
    if risk == "LOW" and sla == "VERY_URGENT" and priority in ("Critical", "High"):
        return "HIGH"
    if risk == "LOW" and sla == "VERY_URGENT":
        return "MEDIUM"
    if risk == "LOW" and sla == "URGENT" and priority in ("Critical", "High"):
        return "MEDIUM"
    return "LOW"


RECOMMENDED_ACTION = {
    "CRITICAL": "Escalade immédiate, assigner un owner senior",
    "HIGH": "Prioriser ce ticket, assigner un owner clair",
    "MEDIUM": "Surveiller de près, revoir avant échéance SLA",
    "LOW": "Traitement normal",
}


def main():
    engine = create_engine(f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
    print("1) Lecture gold + clusters...")
    cols = ["ticket_id", "status"] + CAT_FEATURES + NUM_FEATURES + ["sla_window_minutes", "resolution_minutes_realistic"]
    df = pd.read_sql(f"SELECT {', '.join(cols)} FROM gold.gold_itsm_tickets", engine)
    clusters = pd.read_sql("SELECT * FROM gold.ticket_clusters", engine)
    df = df.merge(clusters, on="ticket_id", how="left")

    print("2) Scoring CatBoost...")
    model = joblib.load("catboost_long_resolution.joblib")
    df["risk_score"] = model.predict_proba(df[CAT_FEATURES + NUM_FEATURES])[:, 1]
    # Risque relatif AU SEIN de chaque priorite (percentile intra-groupe) :
    # le score brut est presque une redite de priority (Critical~0, Low~0.6),
    # donc redondant avec priority elle-meme. Le percentile intra-groupe
    # redonne un signal independant : "risque eleve PAR RAPPORT aux tickets
    # de meme priorite", exploitable dans le moteur de decision.
    df["risk_percentile"] = df.groupby("priority")["risk_score"].rank(pct=True)
    df["risk_level"] = pd.cut(df["risk_percentile"], bins=[0, 0.5, 0.8, 1.0], labels=["LOW", "MEDIUM", "HIGH"], include_lowest=True)

    print("3) Application des regles du moteur de decision...")
    df["sla_urgency"] = df["sla_window_minutes"].apply(sla_urgency)
    df["alert_severity"] = df.apply(lambda r: alert_severity(r["risk_level"], r["sla_urgency"], r["priority"]), axis=1)
    df["recommended_action"] = df["alert_severity"].map(RECOMMENDED_ACTION)

    df["priority_uplift"] = (df["risk_level"] == "HIGH") & (df["priority"].isin(["Low", "Medium"]))
    df["reroute_to"] = df.apply(
        lambda r: SPECIALIST_ROUTE.get(r["topic"]) if r["risk_level"] == "HIGH" and r["agent_group"] in ("IT Support", "Customer Service") else None,
        axis=1
    )
    df["notify_flag"] = df["alert_severity"].isin(["HIGH", "CRITICAL"])
    df["problem_candidate"] = df["risk_level"] == "HIGH"

    print("\n4) Synthese :")
    print(f"   Alertes CRITICAL : {(df['alert_severity']=='CRITICAL').sum()}")
    print(f"   Priority uplift  : {df['priority_uplift'].sum()}")
    print(f"   Reroute recos    : {df['reroute_to'].notna().sum()}")
    print(f"   Notify           : {df['notify_flag'].sum()}")

    df.to_sql("final_scored_tickets", engine, schema="gold", if_exists="replace", index=False)
    print("\n5) Sauvegarde -> table gold.final_scored_tickets")


if __name__ == "__main__":
    main()
