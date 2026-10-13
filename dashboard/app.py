"""
dashboard/app.py
----------------
Application interactive Streamlit pour QualityTrack.
Permet d'analyser la maitrise statistique des procedes (SPC),
de visualiser les cartes de controle et les indicateurs qualite d'usine.
"""

import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy import stats

from database.db import SessionLocal
from database.models import Product, Batch, Measurement
from core.capabilities import compute_capabilities
from core.control_charts import compute_xbar_r_chart
from core.nelson_rules import check_nelson_rules


# Configuration de la page Streamlit
st.set_page_config(
    page_title="QualityTrack - Maitrise Statistique des Procedes",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


def get_db_session():
    return SessionLocal()


# ==============================================================================
# VUE 1 : ANALYSE SPC & CAPABILITE
# ==============================================================================
def render_spc_view(db):
    st.title("📊 Analyse SPC & Capabilite Procede")
    st.caption("Suivi statistique en temps reel, cartes de controle de Shewhart et regles de Nelson.")

    # Selection du Produit et du Lot dans la barre laterale
    products = db.query(Product).all()
    if not products:
        st.warning("Aucun produit trouve dans la base. Veuillez executer seed_data.py.")
        return

    product_dict = {f"{p.name} ({p.unit})": p for p in products}
    selected_prod_label = st.sidebar.selectbox("Selectionner un Produit :", list(product_dict.keys()))
    product = product_dict[selected_prod_label]

    batches = db.query(Batch).filter(Batch.product_id == product.id).all()
    if not batches:
        st.warning(f"Aucun lot enregistre pour le produit {product.name}.")
        return

    batch_dict = {f"{b.reference} (Op: {b.operator or 'N/A'}, Machine: {b.machine or 'N/A'})": b for b in batches}
    selected_batch_label = st.sidebar.selectbox("Selectionner un Lot :", list(batch_dict.keys()))
    batch = batch_dict[selected_batch_label]

    subgroup_size = st.sidebar.slider("Taille des sous-groupes :", min_value=2, max_value=10, value=5)

    # Recuperation des mesures chronologiques
    measurements = (
        db.query(Measurement)
        .filter(Measurement.batch_id == batch.id)
        .order_by(Measurement.sequence.asc())
        .all()
    )

    if len(measurements) < 2 * subgroup_size:
        st.warning(f"Nombre de mesures insuffisant dans ce lot ({len(measurements)}) pour des sous-groupes de {subgroup_size}.")
        return

    values = [m.value for m in measurements]
    data_arr = np.array(values)

    # Calculs statistiques
    cap_res = compute_capabilities(data_arr, lsl=product.lsl, usl=product.usl, subgroup_size=subgroup_size)
    chart_res = compute_xbar_r_chart(data_arr, subgroup_size=subgroup_size)
    nelson_res = check_nelson_rules(
        chart_res.subgroup_means,
        center_line=chart_res.x_bar_bar,
        ucl=chart_res.ucl_xbar,
        lcl=chart_res.lcl_xbar,
    )

    # --- BANDEAU DES KPIS ---
    st.markdown("### 🎯 Indicateurs de Capabilite")
    col1, col2, col3, col4, col5 = st.columns(5)

    col1.metric("Nb Mesures (N)", f"{cap_res.n}", f"{chart_res.n_subgroups} ss-groupes")
    col2.metric("Moyenne", f"{cap_res.mean:.4f} {product.unit}", f"Cible: {product.target or 'N/A'}")
    col3.metric("Cp (Potentiel)", f"{cap_res.cp:.3f}", delta="Court terme")
    col4.metric(
        "Cpk (Reel)",
        f"{cap_res.cpk:.3f}",
        delta="Conforme (>=1.33)" if cap_res.is_capable else "Alerte (<1.33)",
        delta_color="normal" if cap_res.is_capable else "inverse",
    )
    col5.metric("Ppk (Global)", f"{cap_res.ppk:.3f}", delta="Long terme")

    st.divider()

    # --- CARTES DE CONTROLE X-BAR & R ---
    st.markdown("### 📈 Cartes de Controle de Shewhart (X-bar / R)")
    c_left, c_right = st.columns(2)

    # 1. Carte X-bar
    with c_left:
        fig_xbar = go.Figure()
        sg_indices = list(range(1, chart_res.n_subgroups + 1))

        # Ligne de la moyenne
        fig_xbar.add_trace(go.Scatter(
            x=sg_indices, y=chart_res.subgroup_means,
            mode="lines+markers", name="X-bar",
            line=dict(color="#1f77b4", width=2),
            marker=dict(size=7),
        ))

        # Points en anomalie Nelson / Hors limites
        anomalies_indices = set(chart_res.out_of_control_xbar)
        for v in nelson_res.violations:
            anomalies_indices.update(v.indices)

        if anomalies_indices:
            anom_x = [i + 1 for i in sorted(anomalies_indices) if i < chart_res.n_subgroups]
            anom_y = [chart_res.subgroup_means[i - 1] for i in anom_x]
            fig_xbar.add_trace(go.Scatter(
                x=anom_x, y=anom_y,
                mode="markers", name="Anomalie / Nelson",
                marker=dict(color="#d62728", size=11, symbol="circle-open-dot", line=dict(width=2)),
            ))

        # Lignes UCL, CL, LCL
        fig_xbar.add_hline(y=chart_res.ucl_xbar, line_dash="dash", line_color="red", annotation_text=f"UCL={chart_res.ucl_xbar:.3f}")
        fig_xbar.add_hline(y=chart_res.x_bar_bar, line_dash="solid", line_color="green", annotation_text=f"CL={chart_res.x_bar_bar:.3f}")
        fig_xbar.add_hline(y=chart_res.lcl_xbar, line_dash="dash", line_color="red", annotation_text=f"LCL={chart_res.lcl_xbar:.3f}")

        fig_xbar.update_layout(
            title="Carte X-bar (Moyennes des sous-groupes)",
            xaxis_title="Sous-groupe", yaxis_title=f"Valeur ({product.unit})",
            height=380, margin=dict(l=20, r=20, t=40, b=20),
        )
        st.plotly_chart(fig_xbar, use_container_width=True)

    # 2. Carte R (Etendues)
    with c_right:
        fig_r = go.Figure()
        fig_r.add_trace(go.Scatter(
            x=sg_indices, y=chart_res.subgroup_ranges,
            mode="lines+markers", name="R (Etendue)",
            line=dict(color="#ff7f0e", width=2),
            marker=dict(size=7),
        ))

        fig_r.add_hline(y=chart_res.ucl_r, line_dash="dash", line_color="red", annotation_text=f"UCL={chart_res.ucl_r:.3f}")
        fig_r.add_hline(y=chart_res.r_bar, line_dash="solid", line_color="green", annotation_text=f"CL={chart_res.r_bar:.3f}")
        if chart_res.lcl_r > 0:
            fig_r.add_hline(y=chart_res.lcl_r, line_dash="dash", line_color="red", annotation_text=f"LCL={chart_res.lcl_r:.3f}")

        fig_r.update_layout(
            title="Carte R (Dispersion intra-sous-groupes)",
            xaxis_title="Sous-groupe", yaxis_title=f"Etendue ({product.unit})",
            height=380, margin=dict(l=20, r=20, t=40, b=20),
        )
        st.plotly_chart(fig_r, use_container_width=True)

    st.divider()

    # --- HISTOGRAMME DE DISTRIBUTION & TOLERANCES ---
    st.markdown("### 🔔 Distribution des Mesures & Respect des Tolerances")
    c_hist, c_nelson = st.columns([3, 2])

    with c_hist:
        fig_dist = go.Figure()

        # Histogramme
        fig_dist.add_trace(go.Histogram(
            x=values,
            nbinsx=15,
            histnorm="probability density",
            name="Mesures reelles",
            marker_color="#a6c8e0",
            opacity=0.75,
        ))

        # Courbe de Gauss theorique
        x_norm = np.linspace(min(values) - 0.05, max(values) + 0.05, 200)
        y_norm = stats.norm.pdf(x_norm, loc=cap_res.mean, scale=cap_res.std_lt)
        fig_dist.add_trace(go.Scatter(
            x=x_norm, y=y_norm,
            mode="lines",
            name="Loi Normale",
            line=dict(color="#1f77b4", width=2.5),
        ))

        # Lignes LSL, Cible, USL
        fig_dist.add_vline(x=product.lsl, line_dash="dash", line_color="red", annotation_text=f"LSL={product.lsl}")
        fig_dist.add_vline(x=product.usl, line_dash="dash", line_color="red", annotation_text=f"USL={product.usl}")
        if product.target:
            fig_dist.add_vline(x=product.target, line_dash="dot", line_color="green", annotation_text=f"Cible={product.target}")

        fig_dist.update_layout(
            title="Histogramme avec courbe normale vs Tolerances LSL / USL",
            xaxis_title=f"Valeur mesuree ({product.unit})",
            yaxis_title="Densite",
            height=360, margin=dict(l=20, r=20, t=40, b=20),
        )
        st.plotly_chart(fig_dist, use_container_width=True)

    # 3. Panneau des alertes Nelson
    with c_nelson:
        st.subheader("⚠️ Detection des Causes Assignables")
        if not nelson_res.has_violations and chart_res.is_in_control:
            st.success("✅ Aucune anomalie detectee. Procede sous controle statistique.")
        else:
            if not chart_res.is_in_control:
                st.error(f"🚨 Points hors limites de controle : {len(chart_res.out_of_control_xbar)} point(s) sur X-bar.")
            if nelson_res.has_violations:
                for v in nelson_res.violations:
                    with st.expander(f"Regle {v.rule} : {v.description}", expanded=True):
                        st.write(f"**Sous-groupes concernes :** {[i + 1 for i in v.indices]}")


# ==============================================================================
# VUE 2 : INDICATEURS USINE (SYNTHESE GLOBALE)
# ==============================================================================
def render_kpi_view(db):
    st.title("🏭 Indicateurs Qualite Usine")
    st.caption("Synthese globale de la performance de fabrication, conformite et taux de rebuts.")

    batches = db.query(Batch).all()
    if not batches:
        st.info("Aucune donnee de production.")
        return

    records = []
    for b in batches:
        meas = db.query(Measurement).filter(Measurement.batch_id == b.id).all()
        if not meas:
            continue
        total = len(meas)
        conforming = sum(1 for m in meas if m.is_conforming)
        non_conforming = total - conforming
        fpy = (conforming / total) * 100 if total > 0 else 100.0

        records.append({
            "Lot": b.reference,
            "Produit": b.product.name,
            "Operateur": b.operator or "N/A",
            "Machine": b.machine or "N/A",
            "Pieces controlees": total,
            "Conformes": conforming,
            "Rebuts": non_conforming,
            "Taux de conformite (%)": round(fpy, 2),
            "Date": b.produced_at.strftime("%Y-%m-%d"),
        })

    df = pd.DataFrame(records)

    # Métriques globales
    total_parts = df["Pieces controlees"].sum()
    total_scrap = df["Rebuts"].sum()
    global_fpy = ((total_parts - total_scrap) / total_parts) * 100 if total_parts > 0 else 100.0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Pieces Controlees", f"{total_parts}")
    col2.metric("Total Rebuts / Non-conformes", f"{total_scrap}", delta_color="inverse")
    col3.metric("Taux de Conformite Global (FPY)", f"{global_fpy:.2f} %")
    col4.metric("Nombre de Lots Analyses", f"{len(df)}")

    st.divider()

    # Graphique de comparaison par lot
    st.subheader("📊 Performance Qualite par Lot de Fabrication")
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["Lot"], y=df["Taux de conformite (%)"],
        text=df["Taux de conformite (%)"].apply(lambda v: f"{v}%"),
        textposition="auto",
        marker_color=["#2ca02c" if v >= 98 else "#d62728" for v in df["Taux de conformite (%)"]],
    ))
    fig.update_layout(
        title="Taux de conformite (%) par Lot (Vert: >=98%, Rouge: <98%)",
        yaxis=dict(range=[90, 101]),
        height=380,
    )
    st.plotly_chart(fig, use_container_width=True)

    # Tableau recapitulatif
    st.subheader("📋 Bilan Detaile")
    st.dataframe(df, use_container_width=True)


# ==============================================================================
# POINT D'ENTREE DE L'APPLICATION
# ==============================================================================
def main():
    db = get_db_session()
    try:
        st.sidebar.title("QualityTrack ⚙️")
        page = st.sidebar.radio(
            "Navigation :",
            ["Maitrise Statistique (SPC)", "Indicateurs Usine & KPI"],
        )

        if page == "Maitrise Statistique (SPC)":
            render_spc_view(db)
        else:
            render_kpi_view(db)

    finally:
        db.close()


if __name__ == "__main__":
    main()
