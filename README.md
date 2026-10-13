# QualityTrack

Outil de **Maitrise Statistique des Procedes (SPC)** et de suivi des indicateurs qualite pour l'industrie manufacturiere.

## Objectif

QualityTrack permet a une equipe qualite ou fabrication de :
- Charger des donnees de mesures issues d'une ligne de production
- Calculer les **indicateurs de capabilite** d'un procede (Cp, Cpk, Pp, Ppk)
- Generer des **cartes de controle** (X-bar/R) et detecter automatiquement les derives
- Suivre les **indicateurs qualite** mensuels (taux de rebuts, First Pass Yield, Pareto)

## Architecture

`
QualityTrack/
├── core/               # Calculs statistiques (capabilites, cartes de controle, regles de Nelson)
├── database/           # Modeles de donnees et connexion SQL
├── dashboard/          # Interface utilisateur interactive (Streamlit)
│   └── pages/          # Pages : SPC, KPI
└── tests/              # Tests unitaires des formules statistiques
`

## Installation

`ash
# Installer uv si ce n'est pas deja fait
pip install uv

# Creer l'environnement et installer toutes les dependances
uv sync

# Lancer le dashboard
uv run streamlit run dashboard/app.py

# (Optionnel) Lancer l'API REST
uv run uvicorn api.main:app --reload
`

## Commandes utiles

`ash
# Ajouter une dependance
uv add <paquet>

# Lancer les tests
uv run pytest tests/ -v

# Lancer un script
uv run python <script.py>
`

## Stack technique

- **Python 3.10+**
- **uv** — Gestionnaire de paquets et d'environnement (remplace pip + venv)
- **FastAPI** — API REST
- **SQLAlchemy + SQLite** — Base de donnees (basculable PostgreSQL via .env)
- **NumPy / SciPy / Pandas** — Calculs statistiques
- **Streamlit + Plotly** — Dashboard interactif
- **Pytest** — Tests unitaires
