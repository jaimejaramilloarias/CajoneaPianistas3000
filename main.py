"""Simple GUI for montuno generation."""

from pathlib import Path
from tkinter import Tk, Text, Button, Label, StringVar, Radiobutton, ttk

import midi_utils

from modos import MODOS_DISPONIBLES


# Opciones de armonización disponibles.  También se pueden alternar dentro
# de la progresión escribiendo "(8)", "(15)", "(10)" o "(13)" antes del acorde.
ARMONIZACIONES = ["Octavas", "Doble octava", "Décimas", "Treceavas"]

# ---------------------------------------------------------------------------
# Configuration of the available "claves".  Each entry defines the reference
# MIDI file and the rhythmic pattern to use.  Add new claves here in the
# future, following the same structure.
# ---------------------------------------------------------------------------
CLAVES = {
    "Clave 2-3": {
        "midi_prefix": "tradicional_2-3",
        "primer_bloque": [3, 4, 4, 3],
        "patron_repetido": [5, 4, 4, 3],
    },
    "Clave 3-2": {
        "midi_prefix": "tradicional_3-2",
        "primer_bloque": [3, 3, 5, 4],
        "patron_repetido": [4, 3, 5, 4],
    },
}

# ---------------------------------------------------------------------------
# Keep track of the next reference MIDI to use for each clave and
# a global counter for the generated montunos.  This ensures that the
# reference changes on every generation and that output files have
# sequential names.
# ---------------------------------------------------------------------------
INDICES_MIDI = {clave: 0 for clave in CLAVES}
CONTADOR_MONTUNO = 1


def generar(
    status_var: StringVar,
    clave_var: StringVar,
    texto: Text,
    modo_combo: ttk.Combobox,
    armon_combo: ttk.Combobox,
) -> None:
    clave = clave_var.get()
    cfg = CLAVES.get(clave)
    if cfg is None:
        status_var.set(f"Clave no soportada: {clave}")
        return

    # Apply the rhythmic pattern for the selected clave
    midi_utils.PRIMER_BLOQUE = cfg["primer_bloque"]
    midi_utils.PATRON_REPETIDO = cfg["patron_repetido"]
    midi_utils.PATRON_GRUPOS = midi_utils.PRIMER_BLOQUE + midi_utils.PATRON_REPETIDO * 3

    global CONTADOR_MONTUNO
    midi_dir = Path("reference_midi_loops")
    pattern = f"{cfg['midi_prefix']}_*.mid"
    opciones = sorted(midi_dir.glob(pattern))
    if not opciones:
        status_var.set(f"No se encontraron archivos para {clave}")
        return

    # Use a different reference MIDI each time by cycling through the
    # available options for the selected clave.
    idx = INDICES_MIDI.get(clave, 0) % len(opciones)
    midi_ref = opciones[idx]
    INDICES_MIDI[clave] = idx + 1

    # Output file stored on the user's desktop with a sequential name
    desktop = Path.home() / "Desktop"
    desktop.mkdir(parents=True, exist_ok=True)
    output = desktop / f"montuno_tradicional_clave_{CONTADOR_MONTUNO}.mid"
    CONTADOR_MONTUNO += 1

    progresion_texto = texto.get("1.0", "end")
    progresion_texto = " ".join(progresion_texto.split())  # limpia espacios extra
    if not progresion_texto.strip():
        status_var.set("Ingresa una progresión de acordes")
        return

    modo_nombre = modo_combo.get()
    funcion = MODOS_DISPONIBLES.get(modo_nombre)
    if funcion is None:
        status_var.set(f"Modo no soportado: {modo_nombre}")
        return

    armonizacion = armon_combo.get()

    try:
        funcion(progresion_texto, midi_ref, output, armonizacion)
        status_var.set(f"MIDI generado: {output}")
    except Exception as e:
        status_var.set(f"Error: {e}")


def main():
    root = Tk()
    root.title("Generador de Montunos")

    clave_var = StringVar(value="Clave 2-3")
    midi_var = StringVar()
    status_var = StringVar()

    def actualizar_clave() -> None:
        """Update the reference MIDI label when the clave changes."""
        cfg = CLAVES[clave_var.get()]
        midi_var.set(f"reference_midi_loops/{cfg['midi_prefix']}_*.mid")

    Label(root, text="Progresión de acordes:").pack(anchor="w")
    texto = Text(root, width=40, height=4)
    texto.pack(fill="x", padx=5)

    Label(root, text="Clave:").pack(anchor="w", pady=(5, 0))
    for nombre in CLAVES:
        Radiobutton(
            root,
            text=nombre,
            variable=clave_var,
            value=nombre,
            command=actualizar_clave,
        ).pack(anchor="w")

    Label(root, text="MIDI de referencia:").pack(anchor="w", pady=(5, 0))
    Label(root, textvariable=midi_var).pack(anchor="w")

    actualizar_clave()

    Label(root, text="Modo:").pack(anchor="w", pady=(10, 0))
    modo_combo = ttk.Combobox(root, values=list(MODOS_DISPONIBLES.keys()))
    modo_combo.current(0)
    modo_combo.pack(fill="x", padx=5)

    Label(root, text="Armonización:").pack(anchor="w", pady=(10, 0))
    armon_combo = ttk.Combobox(root, values=ARMONIZACIONES)
    armon_combo.current(0)
    armon_combo.pack(fill="x", padx=5)

    Button(
        root,
        text="Generar",
        command=lambda: generar(status_var, clave_var, texto, modo_combo, armon_combo),
    ).pack(pady=10)
    Label(root, textvariable=status_var).pack(pady=(5, 0))

    root.mainloop()


if __name__ == "__main__":
    main()
