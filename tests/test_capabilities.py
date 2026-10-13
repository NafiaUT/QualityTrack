"""
tests/test_capabilities.py
--------------------------
Tests unitaires pour le calcul des indicateurs de capabilite (Cp, Cpk, Pp, Ppk).
"""

import pytest
import numpy as np
from core.capabilities import compute_capabilities, CapabilityResult


def test_perfectly_centered_process():
    """Un procede parfaitement centre doit avoir Cp == Cpk et Pp == Ppk."""
    # 20 mesures centrees sur 10.0, symetriques
    data = [
        9.9, 10.0, 10.1, 10.0, 10.0,
        9.9, 10.0, 10.1, 10.0, 10.0,
        9.9, 10.0, 10.1, 10.0, 10.0,
        9.9, 10.0, 10.1, 10.0, 10.0,
    ]
    res = compute_capabilities(data, lsl=9.5, usl=10.5, subgroup_size=5)

    assert isinstance(res, CapabilityResult)
    assert res.mean == pytest.approx(10.0, abs=1e-4)
    # Comme le procede est exactement au centre, Cp et Cpk doivent etre egaux
    assert res.cp == pytest.approx(res.cpk, abs=1e-3)
    assert res.pp == pytest.approx(res.ppk, abs=1e-3)
    assert res.is_capable is True


def test_off_center_process_reduces_cpk():
    """Quand le procede derive, Cpk doit etre strictement inferieur a Cp."""
    # 20 mesures decalées vers l'USL (cible = 10.0, LSL=9.0, USL=11.0)
    data = [10.6, 10.7, 10.6, 10.8, 10.7] * 4
    res = compute_capabilities(data, lsl=9.0, usl=11.0, subgroup_size=5)

    assert res.cpk < res.cp
    assert res.ppk < res.pp


def test_invalid_spec_limits_raises_error():
    """LSL >= USL doit lever une exception ValueError."""
    data = [10.0] * 10
    with pytest.raises(ValueError, match="LSL .* doit etre strictement inferieur a USL"):
        compute_capabilities(data, lsl=12.0, usl=10.0)


def test_insufficient_data_raises_error():
    """Moins de mesures que la taille minimale requise doit lever une erreur."""
    data = [10.0, 10.1, 10.2]
    with pytest.raises(ValueError):
        compute_capabilities(data, lsl=9.0, usl=11.0, subgroup_size=5)
