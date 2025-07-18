"""Definition of the available montuno generation modes."""

from pathlib import Path


from voicings import generar_voicings_enlazados_tradicional
from midi_utils import (
    exportar_montuno,
    procesar_progresion_en_grupos,
)


# ==========================================================================
# Traditional mode
# ==========================================================================

def montuno_tradicional(progresion_texto: str, midi_ref: Path, output: Path) -> None:
    """Generate a montuno in the traditional style."""
    acordes, grupos_corchea = procesar_progresion_en_grupos(progresion_texto)
    voicings = generar_voicings_enlazados_tradicional(acordes)
    exportar_montuno(midi_ref, voicings, grupos_corchea, output)


MODOS_DISPONIBLES = {
    "Tradicional": montuno_tradicional,
    # futuros modos se agregarán aquí
}
