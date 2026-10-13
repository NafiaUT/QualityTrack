"""
api/main.py
-----------
API REST FastAPI pour QualityTrack.
Permet d'exposer les services d'analyse SPC, la gestion des produits/lots
et les indicateurs usine a des applications tierces (ERP, MES, automates).
"""

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from datetime import datetime
import numpy as np

from database.db import get_db, init_db
from database.models import Product, Batch, Measurement
from core.capabilities import compute_capabilities
from core.control_charts import compute_xbar_r_chart
from core.nelson_rules import check_nelson_rules


# Initialisation des tables au demarrage si besoin
init_db()

app = FastAPI(
    title="QualityTrack API",
    description="API de Maitrise Statistique des Procedes (SPC) et de suivi qualite industrielle.",
    version="1.0.0",
)

# Activation CORS pour integration web
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================================
# SCHEMAS PYDANTIC (VALIDATION DES DONNEES)
# ==============================================================================
class ProductBase(BaseModel):
    name: str = Field(..., examples=["Axe de transmission"])
    description: Optional[str] = Field(None, examples=["Diametre externe"])
    unit: str = Field("mm", examples=["mm"])
    lsl: float = Field(..., examples=[19.85])
    usl: float = Field(..., examples=[20.15])
    target: Optional[float] = Field(None, examples=[20.00])


class ProductCreate(ProductBase):
    pass


class ProductOut(ProductBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class BatchBase(BaseModel):
    reference: str = Field(..., examples=["LOT-2026-001"])
    operator: Optional[str] = Field(None, examples=["Martin"])
    machine: Optional[str] = Field(None, examples=["Tour CNC-02"])
    notes: Optional[str] = None


class BatchCreate(BatchBase):
    product_id: int


class BatchOut(BatchBase):
    id: int
    product_id: int
    produced_at: datetime
    n_measurements: int
    model_config = ConfigDict(from_attributes=True)


class MeasurementCreate(BaseModel):
    value: float = Field(..., examples=[20.012])


class MeasurementBatchCreate(BaseModel):
    values: List[float] = Field(..., examples=[[20.01, 20.03, 19.99, 20.02, 20.00]])


class NelsonViolationOut(BaseModel):
    rule: int
    indices: List[int]
    description: str


class CapabilityOut(BaseModel):
    cp: float
    cpk: float
    pp: float
    ppk: float
    mean: float
    std_court_terme: float
    std_long_terme: float
    is_capable: bool


class ControlChartOut(BaseModel):
    subgroup_size: int
    n_subgroups: int
    x_bar_bar: float
    r_bar: float
    ucl_xbar: float
    lcl_xbar: float
    ucl_r: float
    lcl_r: float
    out_of_control_xbar: List[int]
    out_of_control_r: List[int]
    is_in_control: bool


class SPCAnalysisOut(BaseModel):
    batch_reference: str
    product_name: str
    total_measurements: int
    capabilities: CapabilityOut
    control_charts: ControlChartOut
    nelson_violations: List[NelsonViolationOut]


class PlantSummaryOut(BaseModel):
    total_parts: int
    total_scrap: int
    first_pass_yield_pct: float
    total_batches: int


# ==============================================================================
# ENDPOINTS REST
# ==============================================================================
@app.get("/api/v1/health", tags=["System"])
def health_check():
    """Verifie que l API est operationnelle."""
    return {"status": "ok", "app": "QualityTrack", "version": "1.0.0"}


# --- PRODUITS ---
@app.get("/api/v1/products", response_model=List[ProductOut], tags=["Products"])
def list_products(db: Session = Depends(get_db)):
    """Liste tous les produits controles avec leurs tolerances."""
    return db.query(Product).all()


@app.post("/api/v1/products", response_model=ProductOut, status_code=201, tags=["Products"])
def create_product(payload: ProductCreate, db: Session = Depends(get_db)):
    """Cree un nouveau produit et ses specifications de controle."""
    if payload.lsl >= payload.usl:
        raise HTTPException(status_code=400, detail="LSL doit etre strictement inferieur a USL")

    existing = db.query(Product).filter(Product.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Le produit '{payload.name}' existe deja")

    product = Product(**payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


# --- LOTS ---
@app.get("/api/v1/products/{product_id}/batches", response_model=List[BatchOut], tags=["Batches"])
def list_batches_by_product(product_id: int, db: Session = Depends(get_db)):
    """Liste les lots associes a un produit donne."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produit non trouve")
    return product.batches


@app.post("/api/v1/batches", response_model=BatchOut, status_code=201, tags=["Batches"])
def create_batch(payload: BatchCreate, db: Session = Depends(get_db)):
    """Enregistre un nouveau lot de production."""
    product = db.query(Product).filter(Product.id == payload.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produit non trouve")

    existing = db.query(Batch).filter(Batch.reference == payload.reference).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Le lot '{payload.reference}' existe deja")

    batch = Batch(**payload.model_dump())
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


# --- INGESTION DE MESURES ---
@app.post("/api/v1/batches/{batch_id}/measurements", status_code=201, tags=["Measurements"])
def add_measurements(
    batch_id: int,
    payload: MeasurementBatchCreate,
    db: Session = Depends(get_db)
):
    """
    Ingere une serie de mesures pour un lot (ex: sortie d automate de controle).
    Calcule automatiquement la conformite par rapport au LSL/USL du produit.
    """
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Lot non trouve")

    product = batch.product
    current_count = db.query(Measurement).filter(Measurement.batch_id == batch.id).count()

    for idx, val in enumerate(payload.values):
        is_ok = bool(product.lsl <= val <= product.usl)
        db.add(Measurement(
            batch_id=batch.id,
            value=val,
            sequence=current_count + idx + 1,
            is_conforming=is_ok,
        ))

    db.commit()
    return {"message": f"{len(payload.values)} mesures ajoutees avec succes au lot {batch.reference}"}


# --- ANALYSE STATISTIQUE & SPC ---
@app.get("/api/v1/batches/{batch_id}/spc", response_model=SPCAnalysisOut, tags=["SPC"])
def analyze_batch_spc(
    batch_id: int,
    subgroup_size: int = Query(5, ge=2, le=10, description="Taille des sous-groupes pour l estimation court terme"),
    db: Session = Depends(get_db)
):
    """
    Effectue l analyse complete de maitrise statistique des procedes pour un lot :
    - Indicateurs de capabilite (Cp, Cpk, Pp, Ppk)
    - Limites de controle Shewhart (X-bar et R)
    - Detection des causes assignables selon les 4 regles de Nelson
    """
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Lot non trouve")

    measurements = (
        db.query(Measurement)
        .filter(Measurement.batch_id == batch.id)
        .order_by(Measurement.sequence.asc())
        .all()
    )

    if len(measurements) < 2 * subgroup_size:
        raise HTTPException(
            status_code=400,
            detail=f"Mesures insuffisantes ({len(measurements)}) pour la taille de sous-groupe {subgroup_size}",
        )

    values = np.array([m.value for m in measurements])
    product = batch.product

    # Calculs statistiques via notre module core
    cap = compute_capabilities(values, lsl=product.lsl, usl=product.usl, subgroup_size=subgroup_size)
    chart = compute_xbar_r_chart(values, subgroup_size=subgroup_size)
    nelson = check_nelson_rules(
        chart.subgroup_means,
        center_line=chart.x_bar_bar,
        ucl=chart.ucl_xbar,
        lcl=chart.lcl_xbar,
    )

    return SPCAnalysisOut(
        batch_reference=batch.reference,
        product_name=product.name,
        total_measurements=cap.n,
        capabilities=CapabilityOut(
            cp=cap.cp,
            cpk=cap.cpk,
            pp=cap.pp,
            ppk=cap.ppk,
            mean=cap.mean,
            std_court_terme=cap.std_st,
            std_long_terme=cap.std_lt,
            is_capable=cap.is_capable,
        ),
        control_charts=ControlChartOut(
            subgroup_size=chart.subgroup_size,
            n_subgroups=chart.n_subgroups,
            x_bar_bar=chart.x_bar_bar,
            r_bar=chart.r_bar,
            ucl_xbar=chart.ucl_xbar,
            lcl_xbar=chart.lcl_xbar,
            ucl_r=chart.ucl_r,
            lcl_r=chart.lcl_r,
            out_of_control_xbar=chart.out_of_control_xbar,
            out_of_control_r=chart.out_of_control_r,
            is_in_control=chart.is_in_control,
        ),
        nelson_violations=[
            NelsonViolationOut(rule=v.rule, indices=v.indices, description=v.description)
            for v in nelson.violations
        ],
    )


# --- SYNTHESE QUALITE USINE ---
@app.get("/api/v1/kpi/plant-summary", response_model=PlantSummaryOut, tags=["KPI"])
def get_plant_summary(db: Session = Depends(get_db)):
    """Retourne la synthese globale des performances qualite de l usine."""
    measurements = db.query(Measurement).all()
    batches_count = db.query(Batch).count()

    total = len(measurements)
    if total == 0:
        return PlantSummaryOut(
            total_parts=0, total_scrap=0, first_pass_yield_pct=100.0, total_batches=batches_count
        )

    conforming = sum(1 for m in measurements if m.is_conforming)
    scrap = total - conforming
    fpy = (conforming / total) * 100.0

    return PlantSummaryOut(
        total_parts=total,
        total_scrap=scrap,
        first_pass_yield_pct=round(fpy, 2),
        total_batches=batches_count,
    )
