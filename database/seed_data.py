"""
database/seed_data.py
---------------------
Peuple la base de donnees avec des donnees d exemple realistes.

Simule 3 lots de production pour 2 produits differents :
  - Produit A : procede capable et stable
  - Produit B : procede avec derive progressive (usure outil)

A executer une seule fois pour initialiser la base :
  uv run python database/seed_data.py
"""

import numpy as np
from datetime import datetime, timedelta
from database.db import init_db, SessionLocal
from database.models import Product, Batch, Measurement


def seed():
    # Creation des tables
    init_db()
    db = SessionLocal()

    try:
        # Verification : si des donnees existent deja, on ne reseed pas
        if db.query(Product).count() > 0:
            print("Base deja peuplee. Aucune action effectuee.")
            return

        np.random.seed(42)

        # ------------------------------------------------------------ #
        # Produit A : Diametre exterieur (procede capable et stable)
        # ------------------------------------------------------------ #
        product_a = Product(
            name="Diametre exterieur - Ref A",
            description="Caracteristique critique de diametre sur piece tournee",
            unit="mm",
            lsl=9.85,
            usl=10.15,
            target=10.0,
        )
        db.add(product_a)
        db.flush()  # Recupere l id sans commiter

        # Lot A1 : production normale (50 mesures, procede centre)
        batch_a1 = Batch(
            reference="LOT-A-001",
            product_id=product_a.id,
            operator="Martin",
            machine="Tour CNC-01",
            produced_at=datetime.utcnow() - timedelta(days=5),
        )
        db.add(batch_a1)
        db.flush()

        mesures_a1 = np.random.normal(loc=10.01, scale=0.025, size=50)
        for i, val in enumerate(mesures_a1):
            lsl, usl = product_a.lsl, product_a.usl
            db.add(Measurement(
                batch_id=batch_a1.id,
                value=round(float(val), 4),
                sequence=i + 1,
                is_conforming=bool(lsl <= val <= usl),
                measured_at=datetime.utcnow() - timedelta(days=5, minutes=50 - i),
            ))

        # Lot A2 : production normale (50 mesures, leger decentrage)
        batch_a2 = Batch(
            reference="LOT-A-002",
            product_id=product_a.id,
            operator="Dupont",
            machine="Tour CNC-01",
            produced_at=datetime.utcnow() - timedelta(days=2),
        )
        db.add(batch_a2)
        db.flush()

        mesures_a2 = np.random.normal(loc=10.03, scale=0.028, size=50)
        for i, val in enumerate(mesures_a2):
            lsl, usl = product_a.lsl, product_a.usl
            db.add(Measurement(
                batch_id=batch_a2.id,
                value=round(float(val), 4),
                sequence=i + 1,
                is_conforming=bool(lsl <= val <= usl),
                measured_at=datetime.utcnow() - timedelta(days=2, minutes=50 - i),
            ))

        # ------------------------------------------------------------ #
        # Produit B : Longueur tige (procede avec derive progressive)
        # ------------------------------------------------------------ #
        product_b = Product(
            name="Longueur tige - Ref B",
            description="Longueur totale de tige filetee (controle final)",
            unit="mm",
            lsl=49.8,
            usl=50.2,
            target=50.0,
        )
        db.add(product_b)
        db.flush()

        # Lot B1 : derive progressive simulee (usure outil)
        batch_b1 = Batch(
            reference="LOT-B-001",
            product_id=product_b.id,
            operator="Martin",
            machine="Centre usinage-03",
            notes="Derive observee en fin de lot - outil a remplacer",
            produced_at=datetime.utcnow() - timedelta(days=1),
        )
        db.add(batch_b1)
        db.flush()

        # Mesures avec derive lineaire progressive (simule usure outil)
        base = np.random.normal(loc=50.0, scale=0.03, size=60)
        drift = np.linspace(0, 0.15, 60)  # Derive de 0 a +0.15mm sur le lot
        mesures_b1 = base + drift
        for i, val in enumerate(mesures_b1):
            lsl, usl = product_b.lsl, product_b.usl
            db.add(Measurement(
                batch_id=batch_b1.id,
                value=round(float(val), 4),
                sequence=i + 1,
                is_conforming=bool(lsl <= val <= usl),
                measured_at=datetime.utcnow() - timedelta(days=1, minutes=60 - i),
            ))

        db.commit()
        print("Base de donnees initialisee avec succes !")
        print(f"  - 2 produits crees")
        print(f"  - 3 lots crees (LOT-A-001, LOT-A-002, LOT-B-001)")
        print(f"  - {50 + 50 + 60} mesures inserees")

    except Exception as e:
        db.rollback()
        print(f"Erreur lors du seed : {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
