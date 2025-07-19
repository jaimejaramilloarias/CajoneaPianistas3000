"""Simple GUI for montuno generation."""

from pathlib import Path
from tkinter import Tk, Text, Button, Label, StringVar, Radiobutton, ttk

import midi_utils

from modos import MODOS_DISPONIBLES


# Opciones de armonización disponibles
ARMONIZACIONES = ["Octavas", "Doble octava", "Décimas", "Treceavas"]

# ---------------------------------------------------------------------------
# Configuration of the available "claves".  Each entry defines the reference
# MIDI file and the rhythmic pattern to use.  Add new claves here in the
# future, following the same structure.
# ---------------------------------------------------------------------------
CLAVES = {
    "Clave 2-3": {
        "midi": "tradicional_2-3.mid",
        "primer_bloque": [3, 4, 4, 3],
        "patron_repetido": [5, 4, 4, 3],
    },
    "Clave 3-2": {
        "midi": "tradicional_3-2.mid",
        "primer_bloque": [3, 3, 5, 4],
        "patron_repetido": [4, 3, 5, 4],
    },
}


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

    midi_ref = Path(cfg["midi"])
    output = midi_ref.with_stem(midi_ref.stem + "_montuno")

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
        midi_var.set(cfg["midi"])

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
