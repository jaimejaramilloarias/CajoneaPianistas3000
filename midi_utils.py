"""Helpers for reading, manipulating and exporting MIDI files."""

from pathlib import Path
from typing import List, Tuple
import pretty_midi

# Baseline notes present in the reference MIDI to be replaced by generated voicings
NOTAS_BASE = [43, 45, 48, 52]  # G2, A2, C3, E3


# ==========================================================================
# MIDI reading utilities
# ==========================================================================

def leer_midi_referencia(midi_path: Path):
    """Load reference MIDI and return its notes and the PrettyMIDI object."""
    pm = pretty_midi.PrettyMIDI(str(midi_path))
    # use the first instrument only
    instrumento = pm.instruments[0]
    return instrumento.notes, pm


def obtener_posiciones_referencia(notes) -> List[dict]:
    """Return pitch/start/end for the baseline notes present in the reference."""
    posiciones = []
    for n in notes:
        if n.pitch in NOTAS_BASE:
            posiciones.append(
                {
                    "pitch": n.pitch,
                    "start": n.start,
                    "end": n.end,
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
        voicing = voicings[idx_voicing]
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
    """Generate a new MIDI file with the given voicings."""
    notes, pm = leer_midi_referencia(midi_referencia_path)
    posiciones = obtener_posiciones_referencia(notes)
    _, grid, bpm = _grid_and_bpm(pm)
    nuevas_notas = aplicar_voicings_a_referencia(posiciones, voicings, grupos_corchea, grid)

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

def generar_grupos_corchea(num_acordes: int) -> List[int]:
    grupos = [3, 2, 4, 2]
    while len(grupos) < num_acordes:
        grupos += [5, 2, 4, 2]
    return grupos[:num_acordes]
