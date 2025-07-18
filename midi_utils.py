"""Helpers for reading, manipulating and exporting MIDI files."""

from pathlib import Path
from typing import List, Tuple
import pretty_midi

# Baseline notes present in the reference MIDI to be replaced by generated voicings
NOTAS_BASE = [55, 57, 60, 64]  # G3, A3, C4, E4


# ==========================================================================
# MIDI reading utilities
# ==========================================================================

def leer_midi_referencia(midi_path: Path):
    """Load reference MIDI and return its notes and the PrettyMIDI object."""
    pm = pretty_midi.PrettyMIDI(str(midi_path))
    # use the first instrument only
    instrumento = pm.instruments[0]
    # ensure notes are ordered by start time
    notes = sorted(instrumento.notes, key=lambda n: n.start)
    for n in notes:
        nombre = pretty_midi.note_number_to_name(int(n.pitch))
        print(f"{n.pitch} ({nombre})")
    print(f"Total de notas: {len(notes)}")
    return notes, pm


def obtener_posiciones_referencia(notes) -> List[dict]:
    """Return pitch/start/end for the baseline notes present in the reference."""
    posiciones = []
    for n in notes:
        pitch = int(n.pitch)
        if pitch in [int(p) for p in NOTAS_BASE]:
            posiciones.append(
                {
                    "pitch": pitch,
                    "start": n.start,
                    "end": n.end,
                }
            )
            nombre = pretty_midi.note_number_to_name(pitch)
            print(f"Nota base {pitch} ({nombre}) inicio {n.start}")
    posiciones.sort(key=lambda x: (x["start"], x["pitch"]))
    print(f"Notas base encontradas: {len(posiciones)}")
    ejemplo = [(p['pitch'], p['start']) for p in posiciones[:10]]
    print(f"Ejemplo primeros 10: {ejemplo}")
    return posiciones


# ==========================================================================
# MIDI export utilities
# ==========================================================================

def aplicar_voicings_a_referencia(
    posiciones: List[dict],
    voicings: List[List[int]],
    asignaciones: List[Tuple[str, List[int]]],
    grid_seg: float,
) -> Tuple[List[pretty_midi.Note], int]:
    """Reemplaza las notas de referencia por los voicings generados.

    Devuelve la lista de nuevas notas y el último índice de corchea utilizado.
    """

    # Mapeo corchea → índice de voicing
    mapa: dict[int, int] = {}
    max_idx = -1
    for i, (_, idxs) in enumerate(asignaciones):
        for ix in idxs:
            mapa[ix] = i
            if ix > max_idx:
                max_idx = ix

    nuevas_notas: List[pretty_midi.Note] = []

    for pos in posiciones:
        corchea = int(round(pos["start"] / grid_seg))
        if corchea not in mapa:
            continue  # silencio
        voicing = sorted(voicings[mapa[corchea]])
        orden = NOTAS_BASE.index(pos["pitch"])  # posición dentro del voicing
        nueva_nota = pretty_midi.Note(
            velocity=100,
            pitch=voicing[orden],
            start=pos["start"],
            end=pos["end"],
        )
        nuevas_notas.append(nueva_nota)

    return nuevas_notas, max_idx


def _grid_and_bpm(pm: pretty_midi.PrettyMIDI) -> Tuple[int, float, float]:
    """Return total number of eighth notes, duration of an eighth and bpm."""
    total = pm.get_end_time()
    times, tempi = pm.get_tempo_changes()
    bpm = tempi[0] if len(tempi) > 0 else 120.0
    grid = 60.0 / bpm / 2  # seconds per eighth note
    cor = int(round(total / grid))
    return cor, grid, bpm


def exportar_montuno(
    midi_referencia_path: Path,
    voicings: List[List[int]],
    asignaciones: List[Tuple[str, List[int]]],
    output_path: Path,
) -> None:
    """Generate a new MIDI file with the given voicings.

    The resulting notes are trimmed so the output stops after the
    last eighth-note of the progression.
    """
    notes, pm = leer_midi_referencia(midi_referencia_path)
    posiciones = obtener_posiciones_referencia(notes)
    _, grid, bpm = _grid_and_bpm(pm)

    nuevas_notas, max_idx = aplicar_voicings_a_referencia(
        posiciones, voicings, asignaciones, grid
    )

    limite_cor = ((max_idx + 1 + 7) // 8) * 8 if max_idx >= 0 else 0
    limite = limite_cor * grid
    nuevas_notas = [n for n in nuevas_notas if n.start < limite]

    # Añade una nota de duración cero para asegurar la duración total
    if limite > 0:
        nuevas_notas.append(
            pretty_midi.Note(
                velocity=1,
                pitch=0,
                start=max(0.0, limite - grid),
                end=limite,
            )
        )

    pm_out = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    inst_out = pretty_midi.Instrument(
        program=pm.instruments[0].program,
        is_drum=pm.instruments[0].is_drum,
        name=pm.instruments[0].name,
    )
    inst_out.notes = nuevas_notas
    pm_out.instruments.append(inst_out)
    pm_out.write(str(output_path))


# ==========================================================================
# Traditional rhythmic grouping
# ==========================================================================

# ---------------------------------------------------------------------------
# Rhythmic pattern configuration
# ---------------------------------------------------------------------------
# ``PATRON_GRUPOS`` contiene la secuencia de longitudes de grupos de corcheas
# utilizada al distribuir los acordes.  Se repetirá indefinidamente si se
# necesitan más valores.
PATRON_GRUPOS: List[int] = [
    4, 3, 4, 3,
    6, 3, 4, 3,
    6, 3, 4, 3,
    6, 3, 4, 3,
]


def _siguiente_grupo(indice: int) -> int:
    """Devuelve el valor del patrón correspondiente al índice indicado."""
    return PATRON_GRUPOS[indice % len(PATRON_GRUPOS)]



def procesar_progresion_en_grupos(texto: str) -> List[Tuple[str, List[int]]]:
    """Asigna las corcheas del patrón a los acordes de ``texto``.

    Cada acorde recibe consecutivamente un grupo de ``PATRON_GRUPOS``.  Si un
    grupo no cabe completo en el compás actual (8 corcheas), se divide y la parte
    restante pasa al siguiente compás.  Devuelve una lista donde cada elemento es
    ``(acorde, [indices])`` siendo ``indices`` la lista de corcheas (0-indexadas)
    que corresponden al acorde.
    """

    # Extrae todos los acordes ignorando las barras "|".
    tokens = [t for t in texto.replace("|", " ").split() if t]

    resultado: List[Tuple[str, List[int]]] = []
    indice_patron = 0
    posicion = 0  # corchea actual

    for acorde in tokens:
        grupo = _siguiente_grupo(indice_patron)
        indice_patron += 1
        restante = grupo
        indices: List[int] = []

        while restante > 0:
            fin_compas = ((posicion // 8) + 1) * 8
            disponible = fin_compas - posicion
            usar = min(restante, disponible)
            indices.extend(range(posicion, posicion + usar))
            posicion += usar
            restante -= usar
            # Si se acabó el compás pero quedan corcheas por asignar, continuará
            # en el siguiente compás en la siguiente iteración del while.
        resultado.append((acorde, indices))

    # Depuración: imprime la asignación final
    for acorde, idxs in resultado:
        print(f"{acorde}: {idxs}")

    return resultado
