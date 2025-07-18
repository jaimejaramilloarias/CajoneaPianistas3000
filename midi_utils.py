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
    grupos_corchea: List[int],
    grid_seg: float,
) -> List[pretty_midi.Note]:
    """Replace the reference notes with the generated voicings."""
    nuevas_notas: List[pretty_midi.Note] = []
    idx_voicing = 0
    grupo_limite = grupos_corchea[0]

    for pos in posiciones:
        # determine which eighth note this belongs to
        corchea = int(round(pos["start"] / grid_seg)) + 1
        while corchea > grupo_limite and idx_voicing + 1 < len(voicings):
            idx_voicing += 1
            if idx_voicing < len(grupos_corchea):
                grupo_limite += grupos_corchea[idx_voicing]
        voicing = sorted(voicings[idx_voicing])
        orden = NOTAS_BASE.index(pos["pitch"])  # position within voicing
        nueva_nota = pretty_midi.Note(
            velocity=100,
            pitch=voicing[orden],
            start=pos["start"],
            end=pos["end"],
        )
        nuevas_notas.append(nueva_nota)
    return nuevas_notas


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
    grupos_corchea: List[int],
    output_path: Path,
) -> None:
    """Generate a new MIDI file with the given voicings.

    The resulting notes are trimmed so the output stops after the
    last eighth-note of the progression.
    """
    notes, pm = leer_midi_referencia(midi_referencia_path)
    posiciones = obtener_posiciones_referencia(notes)
    _, grid, bpm = _grid_and_bpm(pm)
    nuevas_notas = aplicar_voicings_a_referencia(posiciones, voicings, grupos_corchea, grid)

    limite = sum(grupos_corchea) * grid
    nuevas_notas = [n for n in nuevas_notas if n.start < limite]

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
# ``PATRON_INICIAL`` se utiliza para los cuatro primeros grupos de corcheas.
# A partir de ahí se repite indefinidamente ``PATRON_REPETICION``.  Modificar
# estas listas permite ajustar fácilmente el feel rítmico sin cambiar el resto
# del código.
PATRON_INICIAL: List[int] = [3, 2, 4, 2]
PATRON_REPETICION: List[int] = [5, 2, 4, 2]


def _iterar_patron_grupos():
    """Yield eighth-note group lengths following the defined pattern."""
    for g in PATRON_INICIAL:
        yield g
    while True:
        for g in PATRON_REPETICION:
            yield g


def generar_grupos_corchea(cantidad: int) -> List[int]:
    """Return ``cantidad`` eighth-note groups following the rhythmic pattern."""
    gen = _iterar_patron_grupos()
    return [next(gen) for _ in range(cantidad)]


def procesar_progresion_en_grupos(texto: str) -> Tuple[List[str], List[int]]:
    """Return chords and their lengths in eighth notes following the pattern.

    ``texto`` may contain bars separated by the ``|`` character.  Within each
    bar there can be either one chord or two chords separated by whitespace.  A
    single chord spans **two** consecutive groups from the rhythmic pattern,
    while two chords share one group each, in the order they appear.
    """

    texto = " ".join(texto.strip().split())
    segmentos = [s.strip() for s in texto.split("|") if s.strip()]

    acordes: List[str] = []
    duraciones: List[int] = []
    grupos_por_acorde: List[List[int]] = []
    gen = _iterar_patron_grupos()

    for seg in segmentos:
        ch = [c for c in seg.split() if c]
        if len(ch) == 1:
            # One chord -> consume two groups of the rhythmic pattern
            g1 = next(gen)
            g2 = next(gen)
            acordes.append(ch[0])
            duraciones.append(g1 + g2)
            grupos_por_acorde.append([g1, g2])
        elif len(ch) == 2:
            # Two chords -> one group each, sequentially
            g1 = next(gen)
            g2 = next(gen)
            acordes.append(ch[0])
            duraciones.append(g1)
            grupos_por_acorde.append([g1])
            acordes.append(ch[1])
            duraciones.append(g2)
            grupos_por_acorde.append([g2])
        else:
            raise ValueError("Se permiten uno o dos acordes entre barras")

    # Muestra en consola el resultado para facilitar la depuración
    for a, grupos in zip(acordes, grupos_por_acorde):
        resumen = ",".join(str(g) for g in grupos)
        total = sum(grupos)
        print(f"{a}: {resumen} (total {total} corcheas)")

    return acordes, duraciones
