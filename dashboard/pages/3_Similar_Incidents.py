"""
pages/3_Similar_Incidents.py
------------------------------
Recherche d'incidents similaires (TF-IDF + similarite cosinus), integree
dans l'app. Meme logique que scripts/find_similar_tickets.py, en interactif.
"""

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME = "postgres", "itsm_pwd", "localhost", "5433", "itsm_db"
st.set_page_config(page_title="Similar Incidents", layout="wide", page_icon="🔎")


@st.cache_data(ttl=600)
def load_kb():
    engine = create_engine(f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
    kb = pd.read_sql(
        "SELECT ticket_id, status, priority, topic, incident_description, solution_used "
        "FROM silver.silver_itsm_tickets WHERE status IN ('Resolved','Closed') AND solution_used IS NOT NULL",
        engine
    ).drop_duplicates(subset="incident_description").reset_index(drop=True)
    return kb


@st.cache_data(ttl=600)
def get_ticket(ticket_id):
    engine = create_engine(f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
    return pd.read_sql(f"SELECT ticket_id, incident_description FROM silver.silver_itsm_tickets WHERE ticket_id = '{ticket_id}'", engine)


st.title("🔎 Recherche d'incidents similaires")
st.caption("TF-IDF + similarité cosinus, sur les tickets résolus/closed (base de connaissances).")

kb = load_kb()
st.info(f"Base de connaissances : {len(kb):,} incidents uniques (dédoublonnés).")

st.warning("⚠️ Ce dataset n'a que 800 descriptions uniques répétées sur 100 000 lignes : "
           "les résultats sont souvent des quasi-doublons (similarité ~0.97-1.000), pas des "
           "cas proches mais distincts comme sur un dataset réel.", icon="⚠️")

ticket_id = st.text_input("Ticket ID à rechercher", value="TCKT-100012")

if st.button("Chercher des incidents similaires") and ticket_id:
    query = get_ticket(ticket_id)
    if query.empty:
        st.error(f"Ticket {ticket_id} introuvable.")
    else:
        query_text = query.iloc[0]["incident_description"]
        st.write(f"**Description :** {query_text}")

        vectorizer = TfidfVectorizer(stop_words="english")
        tfidf_matrix = vectorizer.fit_transform(kb["incident_description"].tolist() + [query_text])
        sims = cosine_similarity(tfidf_matrix[-1], tfidf_matrix[:-1]).flatten()
        top3_idx = sims.argsort()[::-1][:3]

        st.subheader("Top 3 incidents similaires")
        cols = st.columns(3)
        for col, idx in zip(cols, top3_idx):
            row = kb.iloc[idx]
            with col:
                st.metric(row["ticket_id"], f"{sims[idx]:.1%} similaire")
                st.caption(f"Priority: {row['priority']} | Topic: {row['topic']}")
                st.write("**Solution appliquée :**")
                st.write(row["solution_used"][:250] + "...")
