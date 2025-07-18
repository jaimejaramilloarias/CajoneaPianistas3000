"""Definition of the available montuno generation modes."""

from pathlib import Path
from typing import List

from voicings import generar_voicings_enlazados_tradicional
from midi_utils import exportar_montuno, generar_grupos_corchea


# ==========================================================================
# Traditional mode
# ==========================================================================

def montuno_tradicional(progresion: List[str], midi_ref: Path, output: Path) -> None:
    """Generate a montuno in the traditional style."""
    voicings = generar_voicings_enlazados_tradicional(progresion)
    grupos_corchea = generar_grupos_corchea(len(voicings))
    exportar_montuno(midi_ref, voicings, grupos_corchea, output)


MODOS_DISPONIBLES = {
    "Tradicional": montuno_tradicional,
    # futuros modos se agregarán aquí
}
