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



# ---------------------------------------------------------------------------
# The previous implementation copied random 16-eighth windows from the
# reference MIDI.  This logic has been removed to always use the full
# reference sequentially.
# ---------------------------------------------------------------------------

def construir_posiciones_secuenciales(
    posiciones_base: List[dict],
    total_cor_dest: int,
    total_cor_ref: int,
    grid_seg: float,
) -> List[dict]:
    """Build note positions repeating the reference sequentially."""

    grupos_ref: List[List[dict]] = [[] for _ in range(total_cor_ref)]
    for pos in posiciones_base:
        idx = int(round(pos["start"] / grid_seg))
        if 0 <= idx < total_cor_ref:
            grupos_ref[idx].append(
                {
                    "pitch": pos["pitch"],
                    "start": pos["start"] - idx * grid_seg,
                    "end": pos["end"] - idx * grid_seg,
                }
            )

    posiciones: List[dict] = []
    for dest_idx in range(total_cor_dest):
        ref_idx = dest_idx % total_cor_ref
        for nota in grupos_ref[ref_idx]:
            posiciones.append(
                {
                    "pitch": nota["pitch"],
                    "start": dest_idx * grid_seg + nota["start"],
                    "end": dest_idx * grid_seg + nota["end"],
                }
            )

    posiciones.sort(key=lambda x: (x["start"], x["pitch"]))
    return posiciones


# ==========================================================================
# MIDI export utilities
# ==========================================================================

def aplicar_voicings_a_referencia(
    posiciones: List[dict],
    voicings: List[List[int]],
    asignaciones: List[Tuple[str, List[int]]],
    grid_seg: float,
    *,
    debug: bool = False,
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
            if debug:
                print(f"Corchea {corchea}: silencio")
            continue  # silencio
        voicing = sorted(voicings[mapa[corchea]])
        orden = NOTAS_BASE.index(pos["pitch"])  # posición dentro del voicing
        nueva_nota = pretty_midi.Note(
            velocity=100,
            pitch=voicing[orden],
            start=pos["start"],
            end=pos["end"],
        )
        if debug:
            print(
                f"Corchea {corchea}: nota base {pos['pitch']} -> {nueva_nota.pitch}"
            )
        nuevas_notas.append(nueva_nota)

    return nuevas_notas, max_idx


def aplicar_armonizacion(notas: List[pretty_midi.Note], opcion: str) -> List[pretty_midi.Note]:
    """Apply the selected harmonization option to the list of notes."""

    resultado: List[pretty_midi.Note] = []
    if opcion.lower() == "octavas":
        # Duplicate each note one octave above
        for n in notas:
            resultado.append(n)
            if n.pitch > 0:
                resultado.append(
                    pretty_midi.Note(
                        velocity=n.velocity,
                        pitch=n.pitch + 12,
                        start=n.start,
                        end=n.end,
                    )
                )
        return resultado
    elif opcion.lower() == "doble octava":
        # TODO: implementar lógica para duplicar dos octavas por encima
        pass
    elif opcion.lower() == "terceras":
        # TODO: implementar duplicación a la tercera
        pass
    elif opcion.lower() == "sextas":
        # TODO: implementar duplicación a la sexta
        pass

    return notas


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
    num_compases: int,
    output_path: Path,
    armonizacion: str | None = None,
    *,
    debug: bool = False,
) -> None:
    """Generate a new MIDI file with the given voicings.

    The resulting notes are trimmed so the output stops after the last
    eighth-note of the progression.  ``armonizacion`` indica si las notas se
    deben duplicar (por ejemplo, en octavas).
    """
    notes, pm = leer_midi_referencia(midi_referencia_path)
    posiciones_base = obtener_posiciones_referencia(notes)
    total_cor_ref, grid, bpm = _grid_and_bpm(pm)

    if debug:
        print("Asignacion de acordes a corcheas:")
        for acorde, idxs in asignaciones:
            print(f"  {acorde}: {idxs}")

    total_dest_cor = num_compases * 8
    posiciones = construir_posiciones_secuenciales(
        posiciones_base, total_dest_cor, total_cor_ref, grid
    )

    nuevas_notas, _ = aplicar_voicings_a_referencia(
        posiciones, voicings, asignaciones, grid, debug=debug
    )

    limite_cor = total_dest_cor
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

    # --------------------------------------------------------------
    # Apply harmonization (e.g. duplicate notes an octave above)
    # --------------------------------------------------------------
    if armonizacion:
        nuevas_notas = aplicar_armonizacion(nuevas_notas, armonizacion)

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



def procesar_progresion_en_grupos(texto: str) -> Tuple[List[Tuple[str, List[int]]], int]:
    """Asignar corcheas a los acordes usando ``PATRON_GRUPOS``.

    El texto de la progresión se divide por barras ``|`` en segmentos.  Cada
    segmento puede contener uno o dos acordes.  Si sólo hay un acorde, se le
    asignan dos grupos consecutivos del patrón sumados.  Si hay dos acordes,
    cada uno toma un grupo.  Los índices de corchea son absolutos y se asignan de
    manera continua sin respetar límites de compás.

    Devuelve la lista de asignaciones y el número de compases escritos.
    """

    segmentos = [s.strip() for s in texto.split("|") if s.strip()]
    num_compases = len(segmentos)

    resultado: List[Tuple[str, List[int]]] = []
    indice_patron = 0
    posicion = 0  # corchea actual

    for seg in segmentos:
        acordes = [a for a in seg.split() if a]
        if len(acordes) == 1:
            g1 = _siguiente_grupo(indice_patron)
            g2 = _siguiente_grupo(indice_patron + 1)
            dur = g1 + g2
            indices = list(range(posicion, posicion + dur))
            resultado.append((acordes[0], indices))
            posicion += dur
            indice_patron += 2
        elif len(acordes) == 2:
            g1 = _siguiente_grupo(indice_patron)
            indices1 = list(range(posicion, posicion + g1))
            posicion += g1
            indice_patron += 1

            g2 = _siguiente_grupo(indice_patron)
            indices2 = list(range(posicion, posicion + g2))
            posicion += g2
            indice_patron += 1

            resultado.append((acordes[0], indices1))
            resultado.append((acordes[1], indices2))
        else:
            raise ValueError(
                "Cada segmento debe contener uno o dos acordes: " f"{seg}"
            )

    for acorde, idxs in resultado:
        print(f"{acorde}: {idxs}")

    return resultado, num_compases
