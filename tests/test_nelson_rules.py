"""
tests/test_nelson_rules.py
--------------------------
Tests unitaires pour la detection des regles de Nelson.
"""

import pytest
import numpy as np
from core.nelson_rules import check_nelson_rules, NelsonResult


CL = 10.0
UCL = 13.0
LCL = 7.0


def test_rule_1_out_of_limits():
    """R1: detection d un point au-dela de UCL ou sous LCL."""
    data = [10.0, 10.2, 14.5, 9.8, 10.1]
    res = check_nelson_rules(data, center_line=CL, ucl=UCL, lcl=LCL)

    assert res.has_violations is True
    assert 1 in res.violated_rules
    # Le point d indice 2 (valeur 14.5) doit etre identifie
    assert any(2 in v.indices for v in res.violations if v.rule == 1)


def test_rule_2_nine_points_same_side():
    """R2: 9 points consecutifs du meme cote de la ligne centrale."""
    # 9 points au-dessus de CL (10.0), mais sans depasser UCL (13.0)
    data = [10.5, 10.8, 11.0, 10.2, 10.7, 11.1, 10.4, 10.9, 10.6, 9.5]
    res = check_nelson_rules(data, center_line=CL, ucl=UCL, lcl=LCL)

    assert 2 in res.violated_rules


def test_rule_3_six_points_trending():
    """R3: 6 points consecutifs en tendance continue."""
    # 6 points croissants
    data = [9.0, 9.5, 9.9, 10.4, 10.8, 11.2, 10.0]
    res = check_nelson_rules(data, center_line=CL, ucl=UCL, lcl=LCL)

    assert 3 in res.violated_rules


def test_rule_4_fourteen_points_alternating():
    """R4: 14 points consecutifs alternant haut/bas."""
    # Alternance haut / bas autour de la ligne centrale
    data = [10.5 if i % 2 == 0 else 9.5 for i in range(16)]
    res = check_nelson_rules(data, center_line=CL, ucl=UCL, lcl=LCL)

    assert 4 in res.violated_rules


def test_stable_process_no_violations():
    """Un procede parfait ne doit lever aucune violation."""
    # Oscillations moderees symetriques sans sequences particulieres
    data = [10.1, 9.9, 10.2, 9.8, 10.1, 9.9, 10.0, 10.1]
    res = check_nelson_rules(data, center_line=CL, ucl=UCL, lcl=LCL)

    assert res.has_violations is False
    assert len(res.violations) == 0
