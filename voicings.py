"""Utilities for generating piano voicings."""

from typing import List, Tuple

# ==========================================================================
# Dictionaries for chord suffixes and note names
# These are used to parse chord symbols and build chord voicings
# ===========================================================================

INTERVALOS_TRADICIONALES = {
    '6':      [0, 4, 7, 9],     # 1 3 5 6
    '7':      [0, 4, 7, 10],    # 1 3 5 b7
    '∆':      [0, 4, 7, 11],    # 1 3 5 7
    'm6':     [0, 3, 7, 9],     # 1 b3 5 6
    'm7':     [0, 3, 7, 10],    # 1 b3 5 b7
    'm∆':     [0, 3, 7, 11],    # 1 b3 5 7
    '+7':     [0, 4, 8, 10],    # 1 3 #5 b7
    '∆sus4':  [0, 5, 7, 11],    # 1 4 5 7
    '∆sus2':  [0, 2, 7, 11],    # 1 2 5 7
    '7sus4':  [0, 5, 7, 10],    # 1 4 5 b7
    '7sus2':  [0, 2, 7, 10],    # 1 2 5 b7
    'º7':     [0, 3, 6, 9],     # 1 b3 b5 bb7 (bb7 = 6ma mayor)
    'º∆':     [0, 3, 6, 11],    # 1 b3 b5 7
    'ø':      [0, 3, 6, 10],    # 1 b3 b5 b7
    '7(b5)':  [0, 4, 6, 10],    # 1 3 b5 b7
    '∆(b5)':  [0, 4, 6, 11],    # 1 3 b5 7
}

NOTAS = {
    'C':0,  'B#':0,
    'C#':1, 'Db':1,
    'D':2,
    'D#':3,'Eb':3,
    'E':4, 'Fb':4,
    'F':5, 'E#':5,
    'F#':6,'Gb':6,
    'G':7,
    'G#':8,'Ab':8,
    'A':9,
    'A#':10,'Bb':10,
    'B':11, 'Cb':11,
}

# ==========================================================================
# Chord parsing and linked voicing generation
# ==========================================================================

def parsear_nombre_acorde(nombre: str) -> Tuple[int, str]:
    """Parse a chord name into root MIDI pitch class and suffix."""
    import re

    m = re.match(r'^([A-G][b#]?)(m6|m7|m∆|m|6|7|∆sus4|∆sus2|∆|\+7|º7|º∆|ø|7sus4|7sus2|7\(b5\)|∆\(b5\))$', nombre)
    if not m:
        raise ValueError(f"Acorde no reconocido: {nombre}")
    root, suf = m.group(1), m.group(2)
    return NOTAS[root], suf


RANGO_MIN = 53  # F3
RANGO_MAX = 67  # G4


def _ajustar_octava(pitch: int) -> int:
    """Move ``pitch`` by octaves so it falls inside ``RANGO_MIN``-``RANGO_MAX``."""
    while pitch < RANGO_MIN:
        pitch += 12
    while pitch > RANGO_MAX:
        pitch -= 12
    return pitch


def generar_voicings_enlazados_tradicional(progresion: List[str]) -> List[List[int]]:
    """Generate four-note voicings applying simple voice leading.

    The notes of each chord are placed as close as possible to the previous
    voicing so that the jump in the bass voice is minimal.  All notes are kept
    within ``RANGO_MIN`` and ``RANGO_MAX`` and the resulting voicing is always
    sorted from low to high.
    """

    from itertools import permutations

    referencia = [55, 57, 60, 64]  # posiciones de las cuatro voces
    voicings: List[List[int]] = []
    bajo_anterior = referencia[0]

    def ajustar(pc: int, target: int) -> int:
        """Return ``pc`` adjusted in octaves near ``target`` within range."""
        pitch = target + ((pc - target) % 12)
        if abs(pitch - target) > abs(pitch - 12 - target):
            pitch -= 12
        while pitch < RANGO_MIN:
            pitch += 12
        while pitch > RANGO_MAX:
            pitch -= 12
        return pitch

    for nombre in progresion:
        root, suf = parsear_nombre_acorde(nombre)
        pcs = [(root + i) % 12 for i in INTERVALOS_TRADICIONALES[suf]]

        mejor: List[int] | None = None
        mejor_salto: int | None = None

        for perm in permutations(pcs):
            notas = [ajustar(pc, t) for pc, t in zip(perm, referencia)]
            notas.sort()
            salto = abs(notas[0] - bajo_anterior)
            if mejor is None or salto < mejor_salto:
                mejor = notas
                mejor_salto = salto

        assert mejor is not None
        voicings.append(mejor)
        bajo_anterior = mejor[0]

    return voicings

# Future voicing strategies for other modes can be added here
