"""
find_similar_tickets.py
------------------------
ETAPE 7 : recherche d'incidents similaires (module NLP, type SALT).

Utilise TF-IDF (pas d'embeddings/sentence-transformers : pas de modele a
telecharger, fonctionne hors-ligne). Cherche, parmi les tickets resolus/closed,
les descriptions les plus proches d'un ticket donne, et affiche leur solution.

Limite connue : ce dataset n'a que 800 descriptions uniques (repetees sur
100k lignes) -> les "tickets similaires" sont souvent des doublons exacts,
pas des cas proches mais differents (contrairement a un dataset reel).

Usage : python find_similar_tickets.py TCKT-100012
"""

import sys
import pandas as pd
from sqlalchemy import create_engine
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME = "postgres", "itsm_pwd", "localhost", "5433", "itsm_db"


def main(ticket_id):
    engine = create_engine(f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
    print("1) Lecture des tickets resolus/closed (base de connaissances)...")
    kb = pd.read_sql(
        "SELECT ticket_id, status, priority, topic, incident_description, solution_used "
        "FROM silver.silver_itsm_tickets WHERE status IN ('Resolved','Closed') AND solution_used IS NOT NULL",
        engine
    ).drop_duplicates(subset="incident_description").reset_index(drop=True)
    print(f"   -> {len(kb)} incidents uniques dans la base (apres dedoublonnage)")

    query = pd.read_sql(
        f"SELECT ticket_id, incident_description FROM silver.silver_itsm_tickets WHERE ticket_id = '{ticket_id}'",
        engine
    )
    if query.empty:
        print(f"Ticket {ticket_id} introuvable.")
        return
    query_text = query.iloc[0]["incident_description"]

    print("2) Calcul TF-IDF + similarite cosinus...")
    vectorizer = TfidfVectorizer(stop_words="english")
    tfidf_matrix = vectorizer.fit_transform(kb["incident_description"].tolist() + [query_text])
    sims = cosine_similarity(tfidf_matrix[-1], tfidf_matrix[:-1]).flatten()

    top3_idx = sims.argsort()[::-1][:3]
    print(f"\n=== Ticket recherche : {ticket_id} ===")
    print(f"Description : {query_text[:150]}...")
    print("\n=== Top 3 incidents similaires ===")
    for rank, idx in enumerate(top3_idx, 1):
        row = kb.iloc[idx]
        print(f"\n{rank}. {row['ticket_id']}  (similarite={sims[idx]:.3f}, priority={row['priority']}, topic={row['topic']})")
        print(f"   Solution : {row['solution_used'][:150]}...")


if __name__ == "__main__":
    ticket = sys.argv[1] if len(sys.argv) > 1 else "TCKT-100012"
    main(ticket)
