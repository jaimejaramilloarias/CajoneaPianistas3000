"""Utilities for generating piano voicings."""

from typing import List, Tuple

# ---------------------------------------------------------------------------
# Pitch range limits for the generated voicings.  Notes are adjusted so that
# they remain within this interval when building the linked voicings.
# These limits should only affect the base voicings; harmonisation later on
# (octaves, double octaves, tenths or sixths) may exceed ``RANGO_MAX``.
# ---------------------------------------------------------------------------
RANGO_MIN = 53  # F3
RANGO_MAX = 67  # G4

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
    '7(b9)':  [0, 4, 7, 10, 13],  # 1 3 5 b7 b9
    '+7(b9)': [0, 4, 8, 10, 13],  # 1 3 #5 b7 b9
    '7(b5)b9': [0, 4, 6, 10, 13],  # 1 3 b5 b7 b9
    '7sus4(b9)': [0, 5, 7, 10, 13],  # 1 4 5 b7 b9
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

    m = re.match(
        r'^([A-G][b#]?)(m6|m7|m∆|m|6|7|∆sus4|∆sus2|∆|\+7|º7|º∆|ø|7sus4|7sus2|7\(b5\)|7\(b9\)|\+7\(b9\)|7\(b5\)b9|7sus4\(b9\)|∆\(b5\))$',
        nombre,
    )
    if not m:
        raise ValueError(f"Acorde no reconocido: {nombre}")
    root, suf = m.group(1), m.group(2)
    return NOTAS[root], suf


def _ajustar_octava(pitch: int) -> int:
    """Confine ``pitch`` within ``RANGO_MIN`` .. ``RANGO_MAX`` by octaves."""

    while pitch < RANGO_MIN:
        pitch += 12
    while pitch > RANGO_MAX:
        pitch -= 12
    return pitch


def generar_voicings_enlazados_tradicional(progresion: List[str]) -> List[List[int]]:
    """Generate linked four‑note voicings in the traditional style.

    The bass voice is **never** the root (interval ``0``) nor the third
    (interval ``x``) of the chord.  Only the intervals ``y`` or ``z`` can be
    placed in the lowest voice.  The chosen bass is the option (``y`` or ``z``)
    closest to the previous bass note.  The rest of the chord tones are stacked
    above in ascending order.
    """

    import pretty_midi

    referencia = [55, 57, 60, 64]  # default positions for the four voices
    voicings: List[List[int]] = []
    bajo_anterior = referencia[0]

    def ajustar(pc: int, target: int) -> int:
        """Return ``pc`` adjusted near ``target`` without range limits."""
        pitch = target + ((pc - target) % 12)
        if abs(pitch - target) > abs(pitch - 12 - target):
            pitch -= 12
        return pitch

    for nombre in progresion:
        root, suf = parsear_nombre_acorde(nombre)
        ints = INTERVALOS_TRADICIONALES[suf]
        pcs = [(root + i) % 12 for i in ints]

        # ------------------------------------------------------------------
        # Elegir el bajo solamente entre las notas correspondientes a ``y``
        # o ``z``.  La fundamental y la tercera nunca se usan en la voz baja.
        # ------------------------------------------------------------------
        pc_y, pc_z = pcs[2], pcs[3]
        bajo_y = ajustar(pc_y, bajo_anterior)
        bajo_z = ajustar(pc_z, bajo_anterior)
        if abs(bajo_y - bajo_anterior) <= abs(bajo_z - bajo_anterior):
            bajo = _ajustar_octava(bajo_y)
            bajo_intervalo = "y"
            restantes_pcs = [pcs[0], pcs[1], pc_z]
        else:
            bajo = _ajustar_octava(bajo_z)
            bajo_intervalo = "z"
            restantes_pcs = [pcs[0], pcs[1], pc_y]

        notas_restantes: List[int] = []
        for pc, ref in zip(restantes_pcs, referencia[1:]):
            pitch = ajustar(pc, ref)
            # Asegura que todas las notas queden por encima del bajo
            while pitch <= bajo:
                pitch += 12
            pitch = _ajustar_octava(pitch)
            while pitch <= bajo:
                pitch += 12
            notas_restantes.append(pitch)

        voicing = sorted([bajo] + notas_restantes)
        voicings.append(voicing)
        nombres = [pretty_midi.note_number_to_name(n) for n in voicing]
        print(
            f"{nombre}: {nombres} - bajo {pretty_midi.note_number_to_name(bajo)}"
            f" ({bajo_intervalo})"
        )
        bajo_anterior = bajo

    return voicings

# Future voicing strategies for other modes can be added here
