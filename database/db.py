"""
database/db.py
--------------
Connexion a la base de donnees et gestion des sessions SQLAlchemy.

On utilise SQLite par defaut (fichier local, aucune installation requise).
Pour basculer sur PostgreSQL, il suffit de changer DATABASE_URL dans le .env.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv

load_dotenv()

# Lecture de l URL depuis le fichier .env (SQLite par defaut)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./qualitytrack.db")

# Le moteur SQLAlchemy (gere le pool de connexions)
# connect_args est specifique a SQLite pour autoriser le multi-threading
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=False,  # Mettre True pour voir les requetes SQL en console (debug)
)

# Fabrique de sessions : chaque session = une transaction independante
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Classe de base dont heritent tous les modeles SQLAlchemy."""
    pass


def get_db():
    """
    Generateur de session a utiliser dans les routes FastAPI.

    Utilisation typique (injection de dependance FastAPI) :
        @app.get("/...")
        def route(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Cree toutes les tables en base si elles n existent pas encore."""
    from database import models  # Import local pour eviter les imports circulaires
    Base.metadata.create_all(bind=engine)
