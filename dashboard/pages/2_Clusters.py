"""
pages/2_Clusters.py
---------------------
Profils de clusters (K-Prototypes, k=5) : volume, risque moyen, priorite
dominante, temps de resolution moyen par cluster.
"""

import pandas as pd
import streamlit as st
import plotly.express as px
from sqlalchemy import create_engine

DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME = "postgres", "itsm_pwd", "localhost", "5433", "itsm_db"
st.set_page_config(page_title="Clusters", layout="wide", page_icon="🧩")


@st.cache_data(ttl=600)
def load_data():
    engine = create_engine(f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
    return pd.read_sql("SELECT * FROM gold.final_scored_tickets", engine)


df = load_data()
st.title("🧩 Decision Intelligence — Clusters")
st.caption("Profils d'incidents détectés par K-Prototypes (k=5), appliqués aux 100 000 tickets.")

profile = df.groupby("cluster").agg(
    tickets=("ticket_id", "count"),
    avg_resolution_min=("resolution_minutes_realistic", "mean"),
    critical_alerts=("alert_severity", lambda x: (x == "CRITICAL").sum()),
    top_priority=("priority", lambda x: x.mode()[0]),
    top_topic=("topic", lambda x: x.mode()[0]),
    top_agent_group=("agent_group", lambda x: x.mode()[0]),
).reset_index().round(1)

col1, col2 = st.columns([2, 1])
with col1:
    fig = px.bar(profile, x="cluster", y="tickets", color="critical_alerts",
                 title="Volume de tickets par cluster (couleur = alertes critiques)",
                 color_continuous_scale="Reds", text="tickets")
    st.plotly_chart(fig, use_container_width=True)
with col2:
    fig2 = px.bar(profile, x="cluster", y="avg_resolution_min", title="Durée moyenne par cluster (min)",
                  color_discrete_sequence=["#1C7293"])
    st.plotly_chart(fig2, use_container_width=True)

st.subheader("Résumé des clusters")
st.dataframe(profile.rename(columns={
    "cluster": "Cluster", "tickets": "Tickets", "avg_resolution_min": "Durée moy. (min)",
    "critical_alerts": "Alertes CRITICAL", "top_priority": "Priorité dominante",
    "top_topic": "Topic dominant", "top_agent_group": "Groupe dominant",
}), use_container_width=True)
