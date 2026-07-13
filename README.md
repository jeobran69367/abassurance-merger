# AbAssurance ⨯ AssurePlus — Plateforme Big Data & IA de fusion des SI

Projet réalisé dans le cadre du Bloc 3 (Bachelor Concepteur Développeur en IA) : fusion des
systèmes d'information d'AbAssurance (Oracle) et AssurePlus (SQL Server) suite à l'acquisition,
avec mise en place d'une plateforme Big Data (Kafka → Talend/ETL → Hadoop → Spark) et d'un
modèle d'IA de **prédiction du risque client**.

## Sommaire

- `docs/MCD.md` — Modèle Conceptuel de Données unifié + mapping Oracle/SQL Server
- `docs/architecture.md` — Architecture cible détaillée du pipeline
- `src/cleaning/` — Règles et scripts de data cleaning
- `src/etl/` — Mapping et migration des deux bases sources vers le modèle unifié
- `src/ingestion/` — Producteur/consommateur Kafka (flux de changements)
- `src/spark/` — Job Spark de traitement/consolidation vers le data lake (simulation HDFS locale)
- `src/ml/` — Entraînement et sérialisation du modèle de prédiction du risque client
- `src/api/` — API FastAPI (authentification admin/user + endpoint de prédiction)
- `tests/` — Tests unitaires (pytest) + couverture

## Convention de nommage des branches

Ce repository suit un modèle **Git Flow simplifié**, adapté au fonctionnement itératif du projet :

| Branche              | Rôle                                                                 | Convention                          |
|----------------------|-----------------------------------------------------------------------|--------------------------------------|
| `main`               | Code stable, déployé en production. Jamais de commit direct.        | —                                    |
| `develop`            | Branche d'intégration continue de toutes les fonctionnalités.       | —                                    |
| `feature/<sujet>`    | Développement d'une nouvelle fonctionnalité, partie de `develop`.   | `feature/kafka-ingestion`, `feature/mcd-mapping` |
| `bugfix/<sujet>`     | Correction d'un bug détecté sur `develop`.                           | `bugfix/spark-date-parsing`         |
| `hotfix/<sujet>`     | Correction urgente partant de `main` (bug en production).           | `hotfix/api-auth-token`             |
| `release/<version>`  | Stabilisation avant fusion dans `main`, versionnée en semver.        | `release/1.2.0`                     |

Règles associées :
- Toute fonctionnalité est développée dans une branche `feature/*` créée depuis `develop`, puis
  fusionnée via Pull Request (revue de code obligatoire, CI verte requise : lint + tests).
- `develop` est fusionnée dans `main` uniquement via une branche `release/*`.
- Les noms sont en **kebab-case**, en anglais, préfixés par le type de branche.
- Les messages de commit suivent la convention [Conventional Commits](https://www.conventionalcommits.org/)
  (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`).

## Lancer le projet en local

```bash
pip install -r requirements.txt

# Lancer la pipeline de bout en bout (simulation locale : Kafka -> ETL -> lake -> modèle)
python -m src.ingestion.kafka_producer
python -m src.spark.spark_job
python -m src.ml.train_model

# Lancer l'API de prédiction
uvicorn src.api.main:app --reload

# Lancer les tests + couverture
pytest --cov=src --cov-report=term-missing
```

## Identifiants de démonstration de l'API

| Rôle  | Login   | Mot de passe |
|-------|---------|--------------|
| admin | admin   | Admin@2026   |
| user  | user    | User@2026    |
