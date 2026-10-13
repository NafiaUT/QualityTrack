"""
core/nelson_rules.py
--------------------
Detection des causes assignables par les regles de Nelson.

Les regles de Nelson (1984) permettent de detecter des anomalies de procede
qui ne sont pas necessairement visibles par le seul depassement des limites
UCL/LCL. Elles analysent les *patterns* dans la sequence des points.

Source de reference :
  Nelson, L.S. (1984). "The Shewhart Control Chart - Tests for Special Causes".
  Journal of Quality Technology, 16(4), 237-239.

Regles implementees :
  R1 - Un point hors des limites +-3 sigma (cause assignable evidente)
  R2 - 9 points consecutifs du meme cote de la ligne centrale (derive ou decentrage)
  R3 - 6 points consecutifs en tendance monotone (hausse ou baisse continue)
  R4 - 14 points consecutifs alternant haut/bas (melange de deux populations)
"""

from dataclasses import dataclass, field
import numpy as np


@dataclass
class NelsonViolation:
    """Represente une violation detectee d'une regle de Nelson."""
    rule: int                   # Numero de la regle (1 a 4)
    indices: list[int]          # Indices des points concernes dans la serie
    description: str            # Description lisible de l'anomalie


@dataclass
class NelsonResult:
    """Resultat de l'analyse par les regles de Nelson."""
    violations: list[NelsonViolation] = field(default_factory=list)

    @property
    def has_violations(self) -> bool:
        return len(self.violations) > 0

    @property
    def violated_rules(self) -> list[int]:
        return sorted({v.rule for v in self.violations})

    def summary(self) -> str:
        if not self.has_violations:
            return "Aucune violation des regles de Nelson detectee. Procede sous controle."

        lines = [f"=== {len(self.violations)} violation(s) detectee(s) ==="]
        for v in self.violations:
            indices_str = str(v.indices[:5])
            if len(v.indices) > 5:
                indices_str = indices_str[:-1] + f", ... ({len(v.indices)} points)]"
            lines.append(f"  [Regle {v.rule}] {v.description}")
            lines.append(f"           Points concernes : {indices_str}")
        return "\n".join(lines)


def check_nelson_rules(
    values: list[float] | np.ndarray,
    center_line: float,
    ucl: float,
    lcl: float,
) -> NelsonResult:
    """
    Applique les 4 regles de Nelson sur une serie de valeurs de carte de controle.

    Parametres
    ----------
    values      : serie chronologique des valeurs (moyennes de sous-groupes X-bar,
                  ou etendues R, ou mesures individuelles)
    center_line : ligne centrale (X-bar-bar pour carte X-bar, R-bar pour carte R)
    ucl         : limite superieure de controle (+3 sigma)
    lcl         : limite inferieure de controle (-3 sigma)

    Retourne
    --------
    NelsonResult : liste de toutes les violations trouvees.
    """
    pts = np.asarray(values, dtype=float)
    n = len(pts)
    violations: list[NelsonViolation] = []

    # ------------------------------------------------------------------ #
    # REGLE 1 : Un point hors des limites +/- 3 sigma
    # ------------------------------------------------------------------ #
    # C'est la regle de base des cartes de controle de Shewhart.
    # Probabilite d'une fausse alarme : ~0.27% (1 point sur ~370).
    ooc_indices = [i for i in range(n) if pts[i] > ucl or pts[i] < lcl]
    for idx in ooc_indices:
        direction = "superieure" if pts[idx] > ucl else "inferieure"
        violations.append(NelsonViolation(
            rule=1,
            indices=[idx],
            description=f"Point hors limite {direction} (+-3 sigma) au point {idx}",
        ))

    # ------------------------------------------------------------------ #
    # REGLE 2 : 9 points consecutifs du meme cote de la ligne centrale
    # ------------------------------------------------------------------ #
    # Signal d'un decentrage du procede ou d'une derive lente.
    # Probabilite de fausse alarme : (1/2)^9 = ~0.2%
    RUN_LENGTH_R2 = 9
    sides = np.sign(pts - center_line)  # +1 si au-dessus, -1 si en-dessous

    for i in range(n - RUN_LENGTH_R2 + 1):
        window = sides[i : i + RUN_LENGTH_R2]
        # On ignore les points exactement sur la ligne centrale (signe = 0)
        nonzero = window[window != 0]
        if len(nonzero) == RUN_LENGTH_R2 and len(set(nonzero)) == 1:
            side_str = "au-dessus" if nonzero[0] > 0 else "en-dessous"
            violations.append(NelsonViolation(
                rule=2,
                indices=list(range(i, i + RUN_LENGTH_R2)),
                description=(
                    f"{RUN_LENGTH_R2} points consecutifs {side_str} "
                    f"de la ligne centrale (decentrage ou derive)"
                ),
            ))

    # ------------------------------------------------------------------ #
    # REGLE 3 : 6 points consecutifs en tendance monotone
    # ------------------------------------------------------------------ #
    # Signal d'une derive progressive : usure d'outil, derive de capteur,
    # degradation progressive d'un parametre procede.
    RUN_LENGTH_R3 = 6
    diffs = np.diff(pts)  # differences entre points consecutifs

    for i in range(n - RUN_LENGTH_R3):
        window_diffs = diffs[i : i + RUN_LENGTH_R3 - 1]
        if np.all(window_diffs > 0):
            violations.append(NelsonViolation(
                rule=3,
                indices=list(range(i, i + RUN_LENGTH_R3)),
                description=(
                    f"{RUN_LENGTH_R3} points consecutifs en hausse monotone "
                    f"(derive progressive ascendante)"
                ),
            ))
        elif np.all(window_diffs < 0):
            violations.append(NelsonViolation(
                rule=3,
                indices=list(range(i, i + RUN_LENGTH_R3)),
                description=(
                    f"{RUN_LENGTH_R3} points consecutifs en baisse monotone "
                    f"(derive progressive descendante)"
                ),
            ))

    # ------------------------------------------------------------------ #
    # REGLE 4 : 14 points consecutifs alternant haut/bas
    # ------------------------------------------------------------------ #
    # Signal d'un melange de deux populations distinctes dans les donnees :
    # 2 operateurs, 2 machines, 2 fournisseurs, echantillonnage biaise.
    RUN_LENGTH_R4 = 14
    for i in range(n - RUN_LENGTH_R4 + 1):
        window_diffs = diffs[i : i + RUN_LENGTH_R4 - 1]
        # Alternance = les signes des differences changent a chaque pas
        signs = np.sign(window_diffs)
        is_alternating = np.all(signs[:-1] * signs[1:] < 0)
        if is_alternating and len(signs) == RUN_LENGTH_R4 - 1:
            violations.append(NelsonViolation(
                rule=4,
                indices=list(range(i, i + RUN_LENGTH_R4)),
                description=(
                    f"{RUN_LENGTH_R4} points consecutifs en alternance haut/bas "
                    f"(melange de deux populations distinctes)"
                ),
            ))

    # Deduplication : on conserve la premiere occurrence de chaque regle
    # pour eviter de noyer le rapport avec des violations qui se chevauchent.
    violations = _deduplicate(violations)

    return NelsonResult(violations=violations)


def _deduplicate(violations: list[NelsonViolation]) -> list[NelsonViolation]:
    """
    Supprime les violations redondantes qui se chevauchent sur les memes indices.
    Pour chaque regle, on ne conserve que les sequences non chevauchantes.
    """
    seen: dict[int, set[int]] = {}
    deduplicated = []
    for v in violations:
        used = seen.get(v.rule, set())
        # On accepte la violation si ses indices ne chevauchent pas une violation precedente
        if not set(v.indices) & used:
            deduplicated.append(v)
            seen.setdefault(v.rule, set()).update(v.indices)
    return deduplicated
