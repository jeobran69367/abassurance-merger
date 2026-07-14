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
- `src/ingestion/` — Bus Kafka (peek/commit) + producteur
- `src/spark/` — Job Spark de traitement/consolidation vers le data lake (simulation HDFS locale)
- `src/ml/` — Entraînement et sérialisation du modèle de prédiction du risque client
- `src/api/` — API FastAPI (authentification admin/user + endpoint de prédiction)
- `tests/` — Tests unitaires et d'intégration (pytest) + couverture

---

## Lancement pas à pas (local)

### 1. Prérequis

- Python 3.10, 3.11 ou 3.12 (recommandé — voir la note 3.13 dans le Dépannage ci-dessous).
- macOS, Linux ou Windows (WSL conseillé sous Windows).

### 2. Récupérer le projet et créer un environnement virtuel

```bash
git clone https://github.com/<ton-pseudo>/abassurance-merger.git
cd abassurance-merger

python3 -m venv venv
source venv/bin/activate        # Windows : venv\Scripts\activate
```

### 3. Installer les dépendances

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Lancer la pipeline de bout en bout (simulation locale)

```bash
python -m src.ingestion.kafka_producer   # publie les échantillons sur les topics Kafka
python -m src.spark.spark_job            # consolide vers le data lake (data/hdfs_sim/)
python -m src.ml.train_model             # entraîne le modèle de risque client
```

Sortie attendue à la dernière étape des trois commandes :
```
Publié 5 clients AbAssurance et 5 clients AssurePlus sur Kafka.
9 clients consolidés, 1 en quarantaine (voir data/hdfs_sim/quarantine.log).
Modèle entraîné. ROC AUC = 0.9xx (train=4000, test=1000)
```
(1 client en quarantaine est normal et volontaire : `data/sample_ap_users.csv` contient un
numéro de téléphone invalide pour démontrer la règle de validation — voir `docs/MCD.md`.)

### 5. Lancer l'API

```bash
uvicorn src.api.main:app --reload
```

Puis ouvrir **http://127.0.0.1:8000** pour la petite application web de démo (écran de
connexion + formulaire de prédiction du risque), ou http://127.0.0.1:8000/docs pour la
documentation Swagger interactive. Authentifie-toi via `POST /token` (ou directement dans
l'écran de connexion de l'application) avec un des
comptes ci-dessous, clique sur "Authorize" en haut à droite avec le token reçu, puis teste
`POST /predict/risk-client`.

| Rôle  | Login   | Mot de passe |
|-------|---------|--------------|
| admin | admin   | Admin@2026   |
| user  | user    | User@2026    |

### 6. Lancer les tests et la couverture

```bash
pytest --cov=src --cov-report=term-missing
flake8 src tests
```

Résultat attendu : tous les tests passent, couverture globale ≈ 91-92 %, 0 erreur flake8.

---

## Dépannage — problèmes déjà rencontrés et leur résolution

Cette section documente les problèmes réellement rencontrés lors de la mise en route du projet,
et comment ils ont été résolus, pour éviter à quiconque relance le projet de perdre du temps.

### `ImportError: Unable to find a usable engine: pyarrow, fastparquet` en lançant `spark_job`

**Cause :** le fallback pandas (utilisé quand PySpark n'est pas installé) a besoin de `pyarrow`
pour écrire au format Parquet. Cette dépendance avait été classée par erreur comme optionnelle
dans une version antérieure de `requirements.txt`.

**Statut :** corrigé (commit `fix: ajoute pyarrow à requirements.txt`, tag `v1.0.1`). Un simple
`pip install -r requirements.txt` à jour suffit désormais ; si l'erreur réapparaît malgré tout :
`pip install pyarrow`.

### `python -m src.spark.spark_job` affiche "0 clients consolidés" après une exécution précédente en échec

**Cause :** une version antérieure du bus Kafka simulé supprimait les messages dès leur lecture,
avant même de savoir si la consolidation allait réussir. Si le job plantait après la lecture
(par ex. à cause du bug pyarrow ci-dessus), les messages étaient perdus sans possibilité de rejeu.

**Statut :** corrigé (commit `fix: sémantique peek/commit sur le bus Kafka`, tag `v1.0.2`). Le bus
Kafka (`src/ingestion/kafka_bus.py`) utilise maintenant `peek()` (lecture non destructive) et
`commit()` (retrait des messages uniquement après succès), à l'image du fonctionnement réel d'un
consumer Kafka qui ne valide son offset qu'après traitement effectif. Si le problème se reproduit
malgré tout : relancer simplement `python -m src.ingestion.kafka_producer` pour republier les
échantillons, puis `python -m src.spark.spark_job`.

### `pip install` échoue sur `numpy`/`pandas`/`scikit-learn` sous macOS

**Cause probable :** version de Python très récente (3.13+) sans wheel précompilé disponible pour
certaines libs, ce qui force une compilation depuis les sources.

**Solution :** installer les outils de compilation (`xcode-select --install` sur macOS) **ou**,
plus simple, utiliser Python 3.11/3.12 pour le venv :
```bash
brew install python@3.12
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### `pip install` échoue avec "externally-managed-environment"

**Cause :** tentative d'installation hors d'un environnement virtuel sur un Python système protégé
(comportement par défaut sur les Mac/Linux récents).

**Solution :** vérifier que le venv est bien actif — le prompt du terminal doit afficher `(venv)`.
Si besoin : `source venv/bin/activate` avant de relancer `pip install`.

### `uvicorn --reload` plante avec `ImportError: numpy.core.multiarray failed to import` (conflit Anaconda/venv)

**Symptôme :** le prompt affiche `(venv) (base)` en même temps (Anaconda est actif en plus du
venv du projet). `python -m src.ml.train_model` fonctionne très bien, mais `uvicorn --reload`
plante avec des erreurs NumPy/pandas incohérentes.

**Cause :** le rechargement automatique d'uvicorn (`--reload`) relance le serveur dans un
sous-processus. Sur macOS, quand Anaconda (`base`) est actif en plus du venv, ce sous-processus
va chercher les paquets dans l'installation Anaconda (`/opt/anaconda3/...`) au lieu du venv du
projet, provoquant un conflit entre les versions de NumPy/pandas installées dans les deux
environnements.

**Solution immédiate :** lancer l'API sans rechargement automatique :
```bash
uvicorn src.api.main:app
```

**Solution durable :** sortir complètement d'Anaconda avant de travailler sur le projet, puis
recréer le venv à partir d'un Python "propre" :
```bash
conda deactivate
conda deactivate   # parfois nécessaire deux fois selon la configuration du shell
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
Le prompt ne doit plus afficher `(base)`, seulement `(venv)`.

---

## Convention de nommage des branches

Ce repository suit un modèle **Git Flow simplifié**, adapté au fonctionnement itératif du projet :

| Branche              | Rôle                                                                 | Convention                          |
|----------------------|-----------------------------------------------------------------------|--------------------------------------|
| `main`               | Code stable, déployé en production. Jamais de commit direct.        | —                                    |
| `develop`            | Branche d'intégration continue de toutes les fonctionnalités.       | —                                    |
| `feature/<sujet>`    | Développement d'une nouvelle fonctionnalité, partie de `develop`.   | `feature/us-2.1-2.2-kafka-ingestion` |
| `bugfix/<sujet>`     | Correction d'un bug détecté sur `develop`.                           | `bugfix/kafka-consume-commit-semantics` |
| `hotfix/<sujet>`     | Correction urgente partant de `main` (bug en production).           | `hotfix/api-auth-token`             |
| `release/<version>`  | Stabilisation avant fusion dans `main`, versionnée en semver.        | `release/1.0.2`                     |

Règles associées :
- Toute fonctionnalité est développée dans une branche `feature/*` créée depuis `develop`, puis
  fusionnée via Pull Request (revue de code obligatoire, CI verte requise : lint + tests).
- `develop` est fusionnée dans `main` uniquement via une branche `release/*`, taguée en semver.
- Les noms sont en **kebab-case**, en anglais, préfixés par le type de branche.
- Les messages de commit suivent la convention [Conventional Commits](https://www.conventionalcommits.org/)
  (`feat(US-x.y):` pour une fonctionnalité rattachée à une User Story du backlog Trello,
  `fix:`, `docs:`, `test:`, `chore(release):`).

## Historique des versions

| Tag | Contenu |
|---|---|
| `v1.0.0` | EPIC 1/2/3/5 livrés : unification des données, ingestion Kafka, ETL/Spark, modèle IA de risque client + API |
| `v1.0.1` | Correctif : dépendance `pyarrow` manquante pour l'écriture Parquet |
| `v1.0.2` | Correctif : sémantique peek/commit sur le bus Kafka (perte de messages en cas d'échec) |
