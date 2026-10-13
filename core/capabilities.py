"""
core/capabilities.py
--------------------
Calcul des indicateurs de capabilite d'un procede (SPC).

Les indicateurs de capabilite mesurent l'aptitude d'un procede a produire
des pieces conformes aux tolerances definies (LSL = Lower Spec Limit,
USL = Upper Spec Limit).

Regle d'interpretation :
  - Valeur < 1.00 : Procede non capable (trop de rebuts previsibles)
  - 1.00 <= Valeur < 1.33 : Procede limite (surveillance requise)
  - Valeur >= 1.33 : Procede capable (objectif standard industrie)
  - Valeur >= 1.67 : Procede tres capable (objectif Six Sigma)
"""

import numpy as np
from dataclasses import dataclass


@dataclass
class CapabilityResult:
    """Resultat complet d'une analyse de capabilite."""
    cp: float
    cpk: float
    pp: float
    ppk: float
    mean: float
    std_lt: float       # Ecart-type long terme (global)
    std_st: float       # Ecart-type court terme (intra-echantillons)
    lsl: float
    usl: float
    n: int              # Nombre total de mesures

    @property
    def is_capable(self) -> bool:
        """Retourne True si le procede est capable (Cpk >= 1.33)."""
        return bool(self.cpk >= 1.33)

    def summary(self) -> str:
        """Retourne un resume textuel de la capabilite."""
        status = "CAPABLE" if self.is_capable else "NON CAPABLE"
        return (
            f"--- Analyse de Capabilite ---\n"
            f"N = {self.n} mesures | Moyenne = {self.mean:.4f}\n"
            f"LSL = {self.lsl} | USL = {self.usl}\n"
            f"Sigma court terme = {self.std_st:.4f} | Sigma long terme = {self.std_lt:.4f}\n"
            f"Cp  = {self.cp:.3f}  |  Cpk  = {self.cpk:.3f}\n"
            f"Pp  = {self.pp:.3f}  |  Ppk  = {self.ppk:.3f}\n"
            f"Statut : {status}"
        )


def compute_capabilities(
    measurements: list[float] | np.ndarray,
    lsl: float,
    usl: float,
    subgroup_size: int = 5,
) -> CapabilityResult:
    """
    Calcule les indicateurs de capabilite Cp, Cpk, Pp, Ppk.
    """
    data = np.asarray(measurements, dtype=float)
    n = len(data)

    if n < subgroup_size:
        raise ValueError(
            f"Nombre de mesures insuffisant : {n} < taille sous-groupe {subgroup_size}"
        )
    if lsl >= usl:
        raise ValueError(f"LSL ({lsl}) doit etre strictement inferieur a USL ({usl})")

    # --- Statistiques de base ---
    mean = float(np.mean(data))

    # --- Sigma long terme (Pp, Ppk) ---
    std_lt = float(np.std(data, ddof=1))

    # --- Sigma court terme (Cp, Cpk) ---
    std_st = float(_estimate_short_term_sigma(data, subgroup_size))

    # --- Calcul des indicateurs ---
    tolerance = usl - lsl

    # Cp / Pp : capabilite potentielle
    cp = tolerance / (6 * std_st)
    pp = tolerance / (6 * std_lt)

    # Cpk / Ppk : capabilite reelle
    cpk = min(
        (usl - mean) / (3 * std_st),
        (mean - lsl) / (3 * std_st),
    )
    ppk = min(
        (usl - mean) / (3 * std_lt),
        (mean - lsl) / (3 * std_lt),
    )

    return CapabilityResult(
        cp=float(round(cp, 4)),
        cpk=float(round(cpk, 4)),
        pp=float(round(pp, 4)),
        ppk=float(round(ppk, 4)),
        mean=float(round(mean, 6)),
        std_lt=float(round(std_lt, 6)),
        std_st=float(round(std_st, 6)),
        lsl=float(lsl),
        usl=float(usl),
        n=int(n),
    )


# --- Constantes d2 (ASTM / AIAG) ---
_D2_CONSTANTS = {
    2: 1.128,
    3: 1.693,
    4: 2.059,
    5: 2.326,
    6: 2.534,
    7: 2.704,
    8: 2.847,
    9: 2.970,
    10: 3.078,
}


def _estimate_short_term_sigma(data: np.ndarray, subgroup_size: int) -> float:
    """
    Estime le sigma court terme via la methode R_bar / d2.
    """
    if subgroup_size not in _D2_CONSTANTS:
        raise ValueError(
            f"Taille de sous-groupe {subgroup_size} non supportee. "
            f"Valeurs acceptees : {list(_D2_CONSTANTS.keys())}"
        )

    d2 = _D2_CONSTANTS[subgroup_size]

    n_subgroups = len(data) // subgroup_size
    if n_subgroups < 2:
        raise ValueError(
            f"Pas assez de sous-groupes complets. "
            f"Besoin d'au moins {2 * subgroup_size} mesures pour subgroup_size={subgroup_size}."
        )

    subgroups = data[: n_subgroups * subgroup_size].reshape(n_subgroups, subgroup_size)
    ranges = np.ptp(subgroups, axis=1)
    r_bar = float(np.mean(ranges))

    return r_bar / d2
