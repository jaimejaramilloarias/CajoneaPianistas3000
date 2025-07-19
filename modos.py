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

def montuno_tradicional(
    progresion_texto: str,
    midi_ref: Path,
    output: Path,
    armonizacion: str | None = None,
) -> None:
    """Generate a montuno in the traditional style.

    ``armonizacion`` especifica la forma de duplicar las notas generadas. Por
    ahora solo se aplica la opción "Octavas".
    """
    asignaciones, compases = procesar_progresion_en_grupos(
        progresion_texto, armonizacion
    )
    acordes = [a for a, _, _ in asignaciones]
    voicings = generar_voicings_enlazados_tradicional(acordes)
    exportar_montuno(
        midi_ref,
        voicings,
        asignaciones,
        compases,
        output,
        armonizacion=armonizacion,
    )


MODOS_DISPONIBLES = {
    "Tradicional": montuno_tradicional,
    # futuros modos se agregarán aquí
}
