"""Helpers for reading, manipulating and exporting MIDI files."""

from pathlib import Path
from typing import List, Tuple
import random
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


def generar_ventanas(
    posiciones: List[dict],
    grid_seg: float,
    total_corcheas: int,
    tam: int = 16,
) -> List[List[dict]]:
    """Extrae todas las ventanas posibles de ``tam`` corcheas.

    Las posiciones se agrupan por corchea para poder copiar bloques
    consecutivos fácilmente.  Cada ventana contiene copias de las
    posiciones con sus tiempos relativos al inicio de dicha ventana.
    """

    pos_por_corchea: List[List[dict]] = [[] for _ in range(total_corcheas)]
    for pos in posiciones:
        idx = int(round(pos["start"] / grid_seg))
        if 0 <= idx < total_corcheas:
            pos_por_corchea[idx].append(pos)

    ventanas: List[List[dict]] = []
    for inicio in range(0, total_corcheas - tam + 1):
        ventana: List[dict] = []
        for i in range(inicio, inicio + tam):
            for pos in pos_por_corchea[i]:
                ventana.append(
                    {
                        "pitch": pos["pitch"],
                        "start": pos["start"] - inicio * grid_seg,
                        "end": pos["end"] - inicio * grid_seg,
                    }
                )
        ventana.sort(key=lambda x: (x["start"], x["pitch"]))
        ventanas.append(ventana)

    return ventanas


def construir_posiciones_desde_ventanas(
    ventanas: List[List[dict]],
    total_corcheas: int,
    grid_seg: float,
    *,
    debug: bool = False,
    selector=random.choice,
) -> List[dict]:
    """Genera posiciones copiando ventanas aleatorias por bloques de 16 corcheas.

    La lista resultante contendra notas solamente dentro del rango de ``total_corcheas``.
    Cada bloque de 16 corcheas se rellena a partir de una ventana elegida al
    azar.  Si una corchea concreta de la ventana no contiene notas, dicha
    corchea quedara en silencio en el bloque resultante.
    """

    # Pre calcula para cada ventana las notas asociadas a cada corchea relativa
    ventanas_por_idx: List[List[List[dict]]] = []
    for ventana in ventanas:
        grupos = [[] for _ in range(16)]
        for pos in ventana:
            idx = int(round(pos["start"] / grid_seg))
            if 0 <= idx < 16:
                grupos[idx].append(
                    {
                        "pitch": pos["pitch"],
                        "start": pos["start"] - idx * grid_seg,
                        "end": pos["end"] - idx * grid_seg,
                    }
                )
        ventanas_por_idx.append(grupos)

    posiciones: List[dict] = []
    bloques = (total_corcheas + 15) // 16

    for bloque in range(bloques):
        ventana_idx = selector(range(len(ventanas_por_idx)))
        grupos = ventanas_por_idx[ventana_idx]
        if debug:
            inicio_cor = bloque * 16
            fin_cor = min(inicio_cor + 15, total_corcheas - 1)
            idxs = list(range(inicio_cor, fin_cor + 1))
            print(f"Bloque {bloque}: ventana {ventana_idx}, corcheas {idxs}")

        for local_idx in range(16):
            abs_idx = bloque * 16 + local_idx
            if abs_idx >= total_corcheas:
                break
            notas = grupos[local_idx]
            for nota in notas:
                posiciones.append(
                    {
                        "pitch": nota["pitch"],
                        "start": abs_idx * grid_seg + nota["start"],
                        "end": abs_idx * grid_seg + nota["end"],
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
    *,
    usar_ventanas: bool = True,
    debug_ventanas: bool = False,
) -> None:
    """Generate a new MIDI file with the given voicings.

    The resulting notes are trimmed so the output stops after the
    last eighth-note of the progression.
    """
    notes, pm = leer_midi_referencia(midi_referencia_path)
    posiciones_base = obtener_posiciones_referencia(notes)
    total_cor, grid, bpm = _grid_and_bpm(pm)

    if debug_ventanas:
        print("Asignacion de acordes a corcheas:")
        for acorde, idxs in asignaciones:
            print(f"  {acorde}: {idxs}")

    max_idx_asig = max((i for _, idxs in asignaciones for i in idxs), default=-1)
    total_salida = max_idx_asig + 1

    if usar_ventanas:
        ventanas = generar_ventanas(posiciones_base, grid, total_cor)
        posiciones = construir_posiciones_desde_ventanas(
            ventanas, total_salida, grid, debug=debug_ventanas
        )
    else:
        posiciones = posiciones_base

    nuevas_notas, max_idx = aplicar_voicings_a_referencia(
        posiciones, voicings, asignaciones, grid, debug=debug_ventanas
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
    """Asignar corcheas a los acordes usando ``PATRON_GRUPOS``.

    El texto de la progresión se divide por barras ``|`` en segmentos.  Cada
    segmento puede contener uno o dos acordes.  Si sólo hay un acorde, se le
    asignan dos grupos consecutivos del patrón sumados.  Si hay dos acordes,
    cada uno toma un grupo.  Los índices de corchea son absolutos y se asignan de
    manera continua sin respetar límites de compás.
    """

    segmentos = [s.strip() for s in texto.split("|") if s.strip()]

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

    return resultado
