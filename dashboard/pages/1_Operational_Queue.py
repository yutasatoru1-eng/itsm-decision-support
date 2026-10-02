"""
pages/1_Operational_Queue.py
------------------------------
File operationnelle : recherche un ticket, affiche le detail complet
(risque, urgence SLA, severite, action recommandee, contexte de cluster),
et une table filtrable de tous les tickets triee par risque.
"""

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine

DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME = "postgres", "itsm_pwd", "localhost", "5433", "itsm_db"
st.set_page_config(page_title="Operational Queue", layout="wide", page_icon="📋")


@st.cache_data(ttl=600)
def load_data():
    engine = create_engine(f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
    return pd.read_sql("SELECT * FROM gold.final_scored_tickets", engine)


df = load_data()

st.title("📋 Operational Risk Queue")

search = st.text_input("🔍 Rechercher un Ticket ID (ex: TCKT-100012)")

if search:
    match = df[df["ticket_id"].str.contains(search, case=False, na=False)]
    if match.empty:
        st.warning("Aucun ticket trouvé.")
    else:
        row = match.iloc[0]
        st.subheader(f"Ticket {row['ticket_id']}")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Statut", row["status"])
        c2.metric("Priorité", row["priority"])
        c3.metric("Urgence SLA", row["sla_urgency"])
        c4.metric("Sévérité alerte", row["alert_severity"])

        sev_color = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}
        st.markdown(f"### {sev_color.get(row['alert_severity'], '')} Action recommandée : {row['recommended_action']}")

        c5, c6, c7 = st.columns(3)
        c5.metric("Score de risque (relatif à sa priorité)", f"{row['risk_percentile']:.0%}")
        c6.metric("Cluster", f"#{int(row['cluster'])}" if pd.notna(row["cluster"]) else "N/A")
        c7.metric("Réaffectation suggérée", row["reroute_to"] if pd.notna(row["reroute_to"]) else "—")

        st.divider()
        st.write(f"**Topic :** {row['topic']}  |  **Agent Group :** {row['agent_group']}  |  **Source :** {row['source']}")
        st.write(f"**Durée de résolution :** {row['resolution_minutes_realistic']:.0f} min  |  **Fenêtre SLA :** {row['sla_window_minutes']:.0f} min")
else:
    st.caption("Entre un Ticket ID ci-dessus pour voir le détail complet, ou explore la file ci-dessous.")

st.divider()
st.subheader("File triée par risque")

f1, f2, f3 = st.columns(3)
sev_f = f1.multiselect("Sévérité", ["CRITICAL", "HIGH", "MEDIUM", "LOW"])
prio_f = f2.multiselect("Priorité", sorted(df["priority"].unique()))
uplift_only = f3.checkbox("Priority uplift uniquement")

table = df.copy()
if sev_f:
    table = table[table["alert_severity"].isin(sev_f)]
if prio_f:
    table = table[table["priority"].isin(prio_f)]
if uplift_only:
    table = table[table["priority_uplift"]]

table = table.sort_values("risk_percentile", ascending=False)
st.dataframe(
    table[["ticket_id", "status", "priority", "topic", "alert_severity", "risk_percentile",
           "sla_urgency", "recommended_action", "reroute_to"]].head(500),
    use_container_width=True,
)
st.caption(f"{len(table):,} tickets correspondants (500 premiers affichés)")
