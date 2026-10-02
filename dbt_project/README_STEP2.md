# Étape 2 : Nettoyage des données (couche Silver) avec dbt

Cette étape prend les données brutes de la couche **Bronze** (créée à l'Étape 1) et produit
une version propre dans la couche **Silver**, directement en SQL, à l'aide de **dbt**
(l'outil utilisé dans le rapport de référence).

## C'est quoi dbt, en une phrase ?

dbt (data build tool) permet d'écrire du nettoyage de données comme des requêtes SQL
classiques (`SELECT ... FROM ...`), et de les organiser, versionner et ré-exécuter facilement
— au lieu d'avoir des scripts Python dispersés partout.

## Ce que le modèle Silver fait concrètement

Le fichier `models/silver/silver_itsm_tickets.sql` :
- retire les espaces superflus dans les champs texte
- transforme les valeurs vides en vrai `NULL`
- convertit les dates (texte `"04/07/2024 12:42"`) en vrais `TIMESTAMP`
- ajoute `priority_rank` (Low=1, Medium=2, High=3, Critical=4) pour trier facilement
- ajoute `has_solution` (vrai/faux) selon que le champ Solution Used est rempli
- supprime les doublons de `ticket_id` s'il y en a (sécurité)

## Pré-requis

1. Avoir terminé l'Étape 1 (la table `bronze.itsm_tickets_raw` doit exister)
2. `pip install -r requirements.txt` (le fichier a été mis à jour, il installe maintenant
   aussi `dbt-core` et `dbt-postgres`)

## Comment lancer

Le projet dbt est dans le dossier `dbt_project/`. Deux façons de lui donner les
infos de connexion à ta base : soit via variables d'environnement, soit en modifiant
directement `profiles.yml`.

### Option simple : modifier profiles.yml directement

Ouvre `dbt_project/profiles.yml` et vérifie que le port correspond bien à celui que tu utilises
(5433 si tu as suivi le fix du conflit de port, sinon adapte).

### Lancer dbt

```powershell
cd dbt_project
dbt debug --profiles-dir .
```

Tu dois voir `All checks passed!` — ça confirme que dbt arrive à se connecter à ta base.

Puis, pour vraiment construire la couche Silver :

```powershell
dbt run --profiles-dir .
```

Tu dois voir quelque chose comme :
```
1 of 1 OK created sql table model silver.silver_itsm_tickets ... [SELECT 100000 in 2.05s]
Completed successfully
```

## Vérifier le résultat

Dans pgAdmin (comme à l'Étape 1), déplie :
```
postgres → Databases → itsm_db → Schemas → silver → Tables → silver_itsm_tickets
```
Clic droit → View/Edit Data → All Rows.

Ou en SQL direct (Query Tool) :
```sql
SELECT COUNT(*) FROM silver.silver_itsm_tickets;
-- doit renvoyer 100000

SELECT ticket_id, priority, priority_rank, created_time, has_solution
FROM silver.silver_itsm_tickets
LIMIT 5;
-- created_time doit s'afficher comme une vraie date, pas du texte
```

## Remarque sur l'avertissement dbt

Si tu vois ce warning en lançant `dbt run`, c'est normal et sans danger — il annonce juste
que la couche Gold n'existe pas encore (on la construit à l'Étape 3) :
```
Configuration paths exist in your dbt_project.yml file which do not apply to any resources.
- models.itsm_dbt.gold
```

## Prochaine étape

Une fois `silver.silver_itsm_tickets` validé chez toi, on passe à l'**Étape 3 : couche Gold**
— là où on ajoute les vraies variables utiles pour le Machine Learning (durées de résolution,
variables temporelles, encodage des catégories) directement en SQL.
