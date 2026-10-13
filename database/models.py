"""
database/models.py
------------------
Definition des tables de la base de donnees via SQLAlchemy ORM.

Trois tables organisees hierarchiquement :

  Product (produit controle)
    |-- Batch (lot de fabrication)
          |-- Measurement (mesure individuelle)

Chaque Measurement appartient a un Batch, chaque Batch appartient a un Product.
Cette structure permet de retrouver toutes les mesures d un lot ou d un produit
avec une simple requete SQL.
"""

from datetime import datetime
from sqlalchemy import (
    Integer, Float, String, DateTime, ForeignKey, Text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.db import Base


class Product(Base):
    """
    Represente un produit ou une caracteristique controlee.

    Exemple : "Diametre exterieur bague", unite="mm", lsl=9.85, usl=10.15
    """
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="mm")

    # Tolerances (Specification Limits)
    lsl: Mapped[float] = mapped_column(Float, nullable=False)   # Lower Spec Limit
    usl: Mapped[float] = mapped_column(Float, nullable=False)   # Upper Spec Limit
    target: Mapped[float | None] = mapped_column(Float, nullable=True)  # Valeur nominale

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relation 1-to-many : un produit peut avoir plusieurs lots
    batches: Mapped[list["Batch"]] = relationship(
        "Batch", back_populates="product", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Product(name='{self.name}', LSL={self.lsl}, USL={self.usl})>"


class Batch(Base):
    """
    Represente un lot de fabrication (ou une session de production).

    Un lot regroupe un ensemble de mesures realisees dans un contexte defini :
    meme machine, meme operateur, meme matiere premiere, meme periode.
    """
    __tablename__ = "batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    reference: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id"), nullable=False)

    operator: Mapped[str | None] = mapped_column(String(50), nullable=True)
    machine: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    produced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relations
    product: Mapped["Product"] = relationship("Product", back_populates="batches")
    measurements: Mapped[list["Measurement"]] = relationship(
        "Measurement", back_populates="batch", cascade="all, delete-orphan"
    )

    @property
    def n_measurements(self) -> int:
        return len(self.measurements)

    def __repr__(self) -> str:
        return f"<Batch(ref='{self.reference}', product_id={self.product_id})>"


class Measurement(Base):
    """
    Represente une mesure individuelle (un point de controle).

    C est la table la plus granulaire : chaque ligne = une valeur mesuree
    sur une piece, a un instant donne, dans le cadre d un lot.
    """
    __tablename__ = "measurements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[int] = mapped_column(Integer, ForeignKey("batches.id"), nullable=False)

    value: Mapped[float] = mapped_column(Float, nullable=False)   # Valeur mesuree
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)  # Ordre chronologique

    # Statut de conformite (calcule a l insertion)
    is_conforming: Mapped[bool | None] = mapped_column(nullable=True)

    measured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relation
    batch: Mapped["Batch"] = relationship("Batch", back_populates="measurements")

    def __repr__(self) -> str:
        return f"<Measurement(value={self.value}, seq={self.sequence}, batch_id={self.batch_id})>"
