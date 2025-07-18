"""Simple GUI for montuno generation."""

from pathlib import Path
from tkinter import Tk, Text, Button, Label, StringVar, ttk, Radiobutton

from midi_utils import configurar_clave

from modos import MODOS_DISPONIBLES

# Opciones de armonización disponibles
ARMONIZACIONES = ["Octavas", "Doble octava", "Terceras", "Sextas"]

def generar(
    status_var: StringVar,
    midi_var: StringVar,
    texto: Text,
    modo_combo: ttk.Combobox,
    armon_combo: ttk.Combobox,
) -> None:
    ruta_midi = midi_var.get()

    progresion_texto = texto.get("1.0", "end")
    progresion_texto = " ".join(progresion_texto.split())  # limpia espacios extra
    if not progresion_texto.strip():
        status_var.set("Ingresa una progresión de acordes")
        return
    midi_ref = Path(ruta_midi)
    output = midi_ref.with_stem(midi_ref.stem + "_montuno")

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

    midi_var = StringVar()
    clave_var = StringVar(value="2-3")
    status_var = StringVar()

    Label(root, text="Progresión de acordes:").pack(anchor="w")
    texto = Text(root, width=40, height=4)
    texto.pack(fill="x", padx=5)

    def actualizar():
        ruta = configurar_clave(clave_var.get())
        midi_var.set(str(ruta))

    actualizar()

    Label(root, text="Clave:").pack(anchor="w", pady=(5, 0))
    Radiobutton(
        root,
        text="Clave 2-3",
        variable=clave_var,
        value="2-3",
        command=actualizar,
    ).pack(anchor="w")
    Radiobutton(
        root,
        text="Clave 3-2",
        variable=clave_var,
        value="3-2",
        command=actualizar,
    ).pack(anchor="w")
    Label(root, textvariable=midi_var).pack()

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
        command=lambda: generar(status_var, midi_var, texto, modo_combo, armon_combo),
    ).pack(pady=10)
    Label(root, textvariable=status_var).pack(pady=(5, 0))

    root.mainloop()


if __name__ == "__main__":
    main()
