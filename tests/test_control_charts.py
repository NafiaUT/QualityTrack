"""
tests/test_control_charts.py
----------------------------
Tests unitaires pour les cartes de controle de Shewhart (X-bar / R).
"""

import pytest
import numpy as np
from core.control_charts import compute_xbar_r_chart, XBarRChartResult


def test_xbar_r_chart_basic_calculation():
    """Verifie le calcul des moyennes, etendues et limites de controle."""
    # 3 sous-groupes de 5 mesures avec valeurs simples
    # SG1: [10, 10, 10, 10, 10] -> Mean = 10, Range = 0
    # SG2: [12, 12, 12, 12, 12] -> Mean = 12, Range = 0
    # SG3: [11, 11, 11, 11, 11] -> Mean = 11, Range = 0
    # R_bar = 0 -> UCL = LCL = X_bar_bar = 11.0
    data = [10.0] * 5 + [12.0] * 5 + [11.0] * 5
    res = compute_xbar_r_chart(data, subgroup_size=5)

    assert isinstance(res, XBarRChartResult)
    assert res.n_subgroups == 3
    assert res.x_bar_bar == pytest.approx(11.0)
    assert res.r_bar == pytest.approx(0.0)
    assert res.ucl_xbar == pytest.approx(11.0)
    assert res.lcl_xbar == pytest.approx(11.0)


def test_detects_out_of_control_points():
    """Verifie qu un point nettement hors limites est bien detecte."""
    # 4 sous-groupes stables autour de 20.0, puis 1 sous-groupe anormal a 50.0
    sg_normal = [19.9, 20.0, 20.1, 20.0, 20.0]
    sg_anomaly = [50.0, 50.1, 49.9, 50.0, 50.2]

    data = sg_normal * 4 + sg_anomaly
    res = compute_xbar_r_chart(data, subgroup_size=5)

    assert res.is_in_control is False
    assert 4 in res.out_of_control_xbar  # Le 5eme sous-groupe (index 4) est hors limites


def test_unsupported_subgroup_size():
    """Une taille de sous-groupe non tabulee doit lever une erreur."""
    data = [10.0] * 50
    with pytest.raises(ValueError, match="Taille de sous-groupe .* non supportee"):
        compute_xbar_r_chart(data, subgroup_size=15)
