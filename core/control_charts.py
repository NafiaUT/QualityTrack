"""
core/control_charts.py
----------------------
Calcul des cartes de controle de Shewhart (X-bar / R).

Une carte de controle permet de determiner si un procede est "sous controle
statistique", c'est-a-dire si sa variabilite est uniquement due a des causes
aleatoires naturelles (causes communes), ou si une anomalie est presente
(cause assignable : derive, saut de moyenne, usure d'outil...).

Principe :
  - On organise les mesures en sous-groupes chronologiques.
  - On calcule la moyenne (X-bar) et l'etendue (R = max - min) de chaque sous-groupe.
  - On trace les limites de controle (UCL/LCL) a +/- 3 sigma de la ligne centrale.
  - Tout point hors limites est un signal d'anomalie a investiguer.
"""

import numpy as np
from dataclasses import dataclass, field


# --- Constantes de Shewhart (ASTM STP-15D / ISO 7870) ---
# Ces constantes dependent uniquement de la taille n du sous-groupe.
# Elles permettent de calculer les limites de controle a partir de R_bar.
#
# A2 : coefficient pour les limites de la carte X-bar  (UCL/LCL = X_bar_bar +/- A2 * R_bar)
# D3 : coefficient pour la limite basse de la carte R  (LCL_R = D3 * R_bar, = 0 pour n < 7)
# D4 : coefficient pour la limite haute de la carte R  (UCL_R = D4 * R_bar)

_SHEWHART_CONSTANTS = {
#   n :  (A2,    D3,    D4)
    2:   (1.880, 0.000, 3.267),
    3:   (1.023, 0.000, 2.575),
    4:   (0.729, 0.000, 2.282),
    5:   (0.577, 0.000, 2.115),
    6:   (0.483, 0.000, 2.004),
    7:   (0.419, 0.076, 1.924),
    8:   (0.373, 0.136, 1.864),
    9:   (0.337, 0.184, 1.816),
    10:  (0.308, 0.223, 1.777),
}


@dataclass
class XBarRChartResult:
    """
    Resultat complet d'une analyse par carte de controle X-bar / R.

    Contient les donnees pour tracer les deux cartes et la liste
    des points hors-limites (signaux d'anomalie).
    """

    # --- Donnees par sous-groupe ---
    subgroup_means: np.ndarray      # Moyenne de chaque sous-groupe (pour la carte X-bar)
    subgroup_ranges: np.ndarray     # Etendue de chaque sous-groupe (pour la carte R)

    # --- Lignes centrales ---
    x_bar_bar: float                # Moyenne globale (ligne centrale carte X-bar)
    r_bar: float                    # Etendue moyenne (ligne centrale carte R)

    # --- Limites carte X-bar ---
    ucl_xbar: float                 # Limite superieure de controle
    lcl_xbar: float                 # Limite inferieure de controle

    # --- Limites carte R ---
    ucl_r: float                    # Limite superieure de controle
    lcl_r: float                    # Limite inferieure de controle (souvent 0)

    # --- Signaux d'anomalie ---
    out_of_control_xbar: list[int] = field(default_factory=list)  # Indices hors limites X-bar
    out_of_control_r: list[int] = field(default_factory=list)     # Indices hors limites R

    subgroup_size: int = 0
    n_subgroups: int = 0

    @property
    def is_in_control(self) -> bool:
        """Retourne True si aucun point n'est hors limites sur les deux cartes."""
        return len(self.out_of_control_xbar) == 0 and len(self.out_of_control_r) == 0

    def summary(self) -> str:
        status = "SOUS CONTROLE" if self.is_in_control else "HORS CONTROLE"
        lines = [
            "--- Carte de Controle X-bar / R ---",
            f"Sous-groupes : {self.n_subgroups} x {self.subgroup_size} mesures",
            f"X-bar-bar = {self.x_bar_bar:.4f} | R-bar = {self.r_bar:.4f}",
            f"",
            f"Carte X-bar : LCL = {self.lcl_xbar:.4f} | UCL = {self.ucl_xbar:.4f}",
            f"Carte R     : LCL = {self.lcl_r:.4f} | UCL = {self.ucl_r:.4f}",
            f"",
            f"Points hors limites X-bar : {self.out_of_control_xbar or 'Aucun'}",
            f"Points hors limites R     : {self.out_of_control_r or 'Aucun'}",
            f"",
            f"Statut : {status}",
        ]
        return "\n".join(lines)


def compute_xbar_r_chart(
    measurements: list[float] | np.ndarray,
    subgroup_size: int = 5,
) -> XBarRChartResult:
    """
    Calcule les cartes de controle X-bar et R a partir de mesures individuelles.

    Parametres
    ----------
    measurements  : mesures individuelles en ordre chronologique
    subgroup_size : nombre de mesures par sous-groupe (typiquement 4 ou 5)

    Retourne
    --------
    XBarRChartResult : toutes les donnees necessaires pour tracer les deux cartes.

    Formules
    --------
    X-bar (moyenne du sous-groupe i) = sum(xi) / n
    R (etendue du sous-groupe i)     = max(xi) - min(xi)

    Ligne centrale X-bar : X_bar_bar = mean(X-bars)
    Ligne centrale R     : R_bar     = mean(R)

    UCL X-bar = X_bar_bar + A2 * R_bar
    LCL X-bar = X_bar_bar - A2 * R_bar
    UCL R     = D4 * R_bar
    LCL R     = D3 * R_bar  (= 0 pour n < 7)
    """
    data = np.asarray(measurements, dtype=float)

    if subgroup_size not in _SHEWHART_CONSTANTS:
        raise ValueError(
            f"Taille de sous-groupe {subgroup_size} non supportee. "
            f"Valeurs acceptees : {list(_SHEWHART_CONSTANTS.keys())}"
        )

    a2, d3, d4 = _SHEWHART_CONSTANTS[subgroup_size]
    n_subgroups = len(data) // subgroup_size

    if n_subgroups < 3:
        raise ValueError(
            f"Pas assez de donnees : besoin d'au moins 3 sous-groupes complets "
            f"({3 * subgroup_size} mesures minimum pour subgroup_size={subgroup_size})."
        )

    # Decoupage en sous-groupes (mesures residuelles ignorees)
    subgroups = data[: n_subgroups * subgroup_size].reshape(n_subgroups, subgroup_size)

    # Statistiques par sous-groupe
    subgroup_means = np.mean(subgroups, axis=1)
    subgroup_ranges = np.ptp(subgroups, axis=1)   # max - min

    # Lignes centrales
    x_bar_bar = float(np.mean(subgroup_means))
    r_bar = float(np.mean(subgroup_ranges))

    # Limites de controle
    ucl_xbar = x_bar_bar + a2 * r_bar
    lcl_xbar = x_bar_bar - a2 * r_bar
    ucl_r = d4 * r_bar
    lcl_r = d3 * r_bar

    # Detection des points hors limites
    out_xbar = [
        i for i, xbar in enumerate(subgroup_means)
        if xbar > ucl_xbar or xbar < lcl_xbar
    ]
    out_r = [
        i for i, r in enumerate(subgroup_ranges)
        if r > ucl_r or r < lcl_r
    ]

    return XBarRChartResult(
        subgroup_means=subgroup_means,
        subgroup_ranges=subgroup_ranges,
        x_bar_bar=round(x_bar_bar, 6),
        r_bar=round(r_bar, 6),
        ucl_xbar=round(ucl_xbar, 6),
        lcl_xbar=round(lcl_xbar, 6),
        ucl_r=round(ucl_r, 6),
        lcl_r=round(lcl_r, 6),
        out_of_control_xbar=out_xbar,
        out_of_control_r=out_r,
        subgroup_size=subgroup_size,
        n_subgroups=n_subgroups,
    )
