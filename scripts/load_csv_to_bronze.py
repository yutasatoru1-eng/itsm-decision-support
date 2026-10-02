"""
load_csv_to_bronze.py
----------------------
ETAPE 1 : Ingestion des donnees brutes dans la couche Bronze.

Ce script fait UNE SEULE chose : lire le fichier CSV original et le copier
tel quel dans PostgreSQL, dans un schema "bronze". On ne nettoie rien ici,
c'est fait exprès : la couche Bronze doit rester une copie fidele de la
source, pour pouvoir toujours revenir en arriere si un traitement plus tard
se revele faux.

Usage:
    python load_csv_to_bronze.py
"""

import pandas as pd
from sqlalchemy import create_engine, text

# --- Configuration de connexion a la base ---
# A adapter si tu changes d'utilisateur / mot de passe / port
DB_USER = "postgres"
DB_PASSWORD = "itsm_pwd"
DB_HOST = "localhost"
DB_PORT = "5433"
DB_NAME = "itsm_db"

RAW_CSV_PATH = "../data/ITSM_Dataset_raw.csv"
BRONZE_SCHEMA = "bronze"
BRONZE_TABLE = "itsm_tickets_raw"


def main():
    print("1) Connexion a la base de donnees...")
    engine = create_engine(
        f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )

    print("2) Creation du schema 'bronze' s'il n'existe pas...")
    with engine.connect() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {BRONZE_SCHEMA};"))
        conn.commit()

    print("3) Lecture du fichier CSV brut...")
    # encoding='utf-8-sig' seulement pour pouvoir lire le fichier correctement.
    # On ne touche a AUCUNE valeur : pas de nettoyage, pas de renommage de colonnes
    # au-dela de ce qui est strictement necessaire pour que SQL accepte les noms.
    df = pd.read_csv(RAW_CSV_PATH, encoding="utf-8-sig")
    print(f"   -> {df.shape[0]} lignes, {df.shape[1]} colonnes lues.")

    # PostgreSQL n'aime pas les espaces dans les noms de colonnes : on les
    # remplace par des underscores, MAIS on garde une trace du nom d'origine
    # dans un commentaire pour ne rien perdre.
    original_columns = df.columns.tolist()
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    print("4) Ecriture dans la table bronze.itsm_tickets_raw...")
    df.to_sql(
        BRONZE_TABLE,
        engine,
        schema=BRONZE_SCHEMA,
        if_exists="replace",  # on remplace a chaque run pour repartir propre
        index=False,
        chunksize=5000,       # on insere par paquets de 5000 lignes (plus rapide)
    )

    print("5) Verification...")
    with engine.connect() as conn:
        result = conn.execute(
            text(f"SELECT COUNT(*) FROM {BRONZE_SCHEMA}.{BRONZE_TABLE};")
        )
        count = result.scalar()
        print(f"   -> {count} lignes presentes dans bronze.{BRONZE_TABLE}.")

    print("\nTermine. Colonnes d'origine conservees pour reference :")
    for orig, new in zip(original_columns, df.columns):
        print(f"   {orig!r:45s} -> {new}")


if __name__ == "__main__":
    main()
