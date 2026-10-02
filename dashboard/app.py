"""
app.py — Executive Overview
-----------------------------
Page d'accueil de l'app multi-pages. Lit gold.final_scored_tickets (deja score
par le modele + moteur de decision), affiche KPIs et graphiques generaux.

Lancer : streamlit run app.py
"""

import pandas as pd
import streamlit as st
import plotly.express as px
from sqlalchemy import create_engine

DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME = "postgres", "itsm_pwd", "localhost", "5433", "itsm_db"

st.set_page_config(page_title="ITSM Intelligence", layout="wide", page_icon="🎫")


@st.cache_data(ttl=600)
def load_data():
    engine = create_engine(f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
    return pd.read_sql("SELECT * FROM gold.final_scored_tickets", engine)


df = load_data()

st.title("🎫 ITSM Intelligence — Executive Overview")
st.caption("Monitoring global du risque, de la pression SLA, des alertes et des actions recommandées.")

# --- KPIs ---
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total tickets", f"{len(df):,}")
c2.metric("Alertes CRITICAL", f"{(df['alert_severity']=='CRITICAL').sum():,}")
c3.metric("Risque HIGH (relatif)", f"{(df['risk_level']=='HIGH').sum():,}")
c4.metric("Priority uplift", f"{df['priority_uplift'].sum():,}")
c5.metric("Durée résolution moy.", f"{df['resolution_minutes_realistic'].mean():.0f} min")

st.divider()

col1, col2 = st.columns(2)
with col1:
    sev_counts = df["alert_severity"].value_counts().reindex(["LOW", "MEDIUM", "HIGH", "CRITICAL"]).reset_index()
    sev_counts.columns = ["Sévérité", "Tickets"]
    fig1 = px.bar(sev_counts, x="Sévérité", y="Tickets", title="Répartition des alertes",
                  color="Sévérité", color_discrete_map={"LOW": "#22c55e", "MEDIUM": "#f59e0b", "HIGH": "#f97316", "CRITICAL": "#dc2626"})
    st.plotly_chart(fig1, use_container_width=True)
with col2:
    by_priority = df.groupby("priority")["resolution_minutes_realistic"].mean().reset_index()
    fig2 = px.bar(by_priority, x="priority", y="resolution_minutes_realistic",
                  title="Durée moyenne de résolution par priorité", color_discrete_sequence=["#065A82"])
    st.plotly_chart(fig2, use_container_width=True)

col3, col4 = st.columns(2)
with col3:
    by_topic = df.groupby("topic").agg(tickets=("ticket_id", "count"), critical=("alert_severity", lambda x: (x == "CRITICAL").sum())).reset_index()
    fig3 = px.bar(by_topic, x="topic", y="tickets", color="critical", title="Volume par sujet (couleur = alertes critiques)",
                  color_continuous_scale="Reds")
    st.plotly_chart(fig3, use_container_width=True)
with col4:
    reroute = df[df["reroute_to"].notna()]["reroute_to"].value_counts().reset_index()
    reroute.columns = ["Groupe cible", "Recommandations"]
    fig4 = px.bar(reroute, x="Groupe cible", y="Recommandations", title="Recommandations de réaffectation",
                  color_discrete_sequence=["#1C7293"])
    st.plotly_chart(fig4, use_container_width=True)

st.info("Navigue vers **Operational Queue**, **Clusters** ou **Similar Incidents** dans le menu à gauche.")
