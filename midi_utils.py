"""Helpers for reading, manipulating and exporting MIDI files."""

from pathlib import Path
from typing import List, Tuple
import pretty_midi
from voicings import parsear_nombre_acorde, INTERVALOS_TRADICIONALES

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
    """Return pitch, start, end and velocity for baseline notes in the reference."""
    posiciones = []
    for n in notes:
        pitch = int(n.pitch)
        if pitch in [int(p) for p in NOTAS_BASE]:
            posiciones.append(
                {
                    "pitch": pitch,
                    "start": n.start,
                    "end": n.end,
                    "velocity": n.velocity,
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
                    "velocity": pos["velocity"],
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
                    "velocity": nota["velocity"],
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
        # Preserve the velocity of the reference note so dynamics match
        nueva_nota = pretty_midi.Note(
            velocity=pos["velocity"],
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


def _arm_octavas(notas: List[pretty_midi.Note]) -> List[pretty_midi.Note]:
    """Duplicate each note one octave above."""

    resultado: List[pretty_midi.Note] = []
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


def _arm_doble_octava(notas: List[pretty_midi.Note]) -> List[pretty_midi.Note]:
    """Create notes an octave below and above, without keeping the original."""

    resultado: List[pretty_midi.Note] = []
    for n in notas:
        if n.pitch > 0:
            # Copy the velocity from the original note
            resultado.append(
                pretty_midi.Note(
                    velocity=n.velocity,
                    pitch=n.pitch - 12,
                    start=n.start,
                    end=n.end,
                )
            )
            resultado.append(
                pretty_midi.Note(
                    velocity=n.velocity,
                    pitch=n.pitch + 12,
                    start=n.start,
                    end=n.end,
                )
            )
    return resultado


def _arm_por_parejas(
    posiciones: List[dict],
    voicings: List[List[int]],
    asignaciones: List[Tuple[str, List[int]]],
    grid_seg: float,
    salto: int,
    *,
    debug: bool = False,
) -> List[pretty_midi.Note]:
    """Generate notes in parallel motion (thirds or sixths).

    Each chord ``voicing`` is walked sequentially using the eighth-note
    positions assigned to it.  ``salto`` determines the pairing pattern:
    ``1`` produces thirds and ``2`` produces sixths.  The rhythmic
    information (start, end and velocity) is taken from the reference
    ``posiciones`` list.
    """

    # Map each eighth index to the corresponding voicing/chord
    mapa: dict[int, int] = {}
    for i, (_, idxs) in enumerate(asignaciones):
        for ix in idxs:
            mapa[ix] = i

    # Counter so each chord advances through its voicing in parallel
    contadores: dict[int, int] = {}

    resultado: List[pretty_midi.Note] = []
    for pos in posiciones:
        corchea = int(round(pos["start"] / grid_seg))
        if corchea not in mapa:
            if debug:
                print(f"Corchea {corchea}: silencio")
            continue

        idx_voicing = mapa[corchea]
        paso = contadores.get(idx_voicing, 0)
        contadores[idx_voicing] = paso + 1

        voicing = sorted(voicings[idx_voicing])

        if salto == 1:  # terceras
            principal = voicing[paso % 4]
            agregada = voicing[(paso + 1) % 4] + 12
        else:  # sextas
            principal = voicing[(paso + 1) % 4]
            agregada = voicing[paso % 4] + 12

        # Ensure the upper note never sits in the same octave as the
        # principal voice.  This avoids "collapsed" intervals when the
        # voicing spans less than an octave.
        while agregada <= principal:
            agregada += 12

        for pitch in (principal, agregada):
            resultado.append(
                pretty_midi.Note(
                    velocity=pos["velocity"],
                    pitch=pitch,
                    start=pos["start"],
                    end=pos["end"],
                )
            )

        if debug:
            print(
                f"Corchea {corchea}: paso {paso} -> {principal} / {agregada}"
            )

    return resultado


def _arm_terceras_intervalos(
    posiciones: List[dict],
    voicings: List[List[int]],
    asignaciones: List[Tuple[str, List[int]]],
    grid_seg: float,
    *,
    debug: bool = False,
) -> List[pretty_midi.Note]:
    """Harmonize in parallel thirds following fixed functional pairs.

    Before processing the MIDI positions each chord is analysed so every
    pitch can be labelled as fundamental, third, fifth, sixth or seventh.
    The added note is then obtained with the exact interval mandated by the
    specification:

    * F → 3 (+12)
    * 3 → 5 (+12)
    * 5 → 7 (+12) or M7 (+12) on sixth chords
    * 6 or diminished 7 → F (+24)
    * 7 → 9 (+12)

    Velocity and timing from the reference are preserved verbatim.
    """

    # ------------------------------------------------------------------
    # Build a map from eighth index to voicing index and gather information
    # about each chord so that every pitch can be classified by function.
    # ``info`` stores the root pitch class, the four intervals of the chord
    # and flags indicating whether it is a sixth chord or a diminished
    # seventh.
    # ------------------------------------------------------------------
    mapa: dict[int, int] = {}
    for i, (_, idxs) in enumerate(asignaciones):
        for ix in idxs:
            mapa[ix] = i

    info: list[dict] = []
    for nombre, _ in asignaciones:
        root_pc, suf = parsear_nombre_acorde(nombre)
        ints = INTERVALOS_TRADICIONALES[suf]
        is_sixth = suf.endswith("6") and "7" not in suf
        is_dim7 = suf == "º7"
        info.append(
            {
                "root_pc": root_pc,
                "intervals": ints,
                "is_sixth": is_sixth,
                "is_dim7": is_dim7,
            }
        )

    contadores: dict[int, int] = {}
    resultado: List[pretty_midi.Note] = []

    for pos in posiciones:
        corchea = int(round(pos["start"] / grid_seg))
        if corchea not in mapa:
            if debug:
                print(f"Corchea {corchea}: silencio")
            continue

        idx = mapa[corchea]
        paso = contadores.get(idx, 0)
        contadores[idx] = paso + 1

        datos = info[idx]
        voicing = sorted(voicings[idx])
        base = voicing[paso % 4]
        root_pc = datos["root_pc"]
        ints = datos["intervals"]
        is_sixth = datos["is_sixth"]
        is_dim7 = datos["is_dim7"]

        # --------------------------------------------------------------
        # Identify the function of ``base`` comparing its pitch class
        # against the intervals of the current chord.
        # --------------------------------------------------------------
        pc = base % 12
        func = None
        if pc == (root_pc + ints[0]) % 12:
            func = "F"
            target = root_pc + ints[1]
        elif pc == (root_pc + ints[1]) % 12:
            func = "3"
            target = root_pc + ints[2]
        elif pc == (root_pc + ints[2]) % 12:
            func = "5"
            target = root_pc + (11 if is_sixth else ints[3])
        elif pc == (root_pc + ints[3]) % 12:
            if is_sixth or is_dim7:
                func = "6"
                target = root_pc  # fundamental
            else:
                func = "7"
                target = root_pc + 2
        else:
            # Should not happen with valid voicings
            target = base

        # --------------------------------------------------------------
        # Compute the upper note ensuring it sits above the principal.
        # Octave or double octave shifts are applied as required.
        # --------------------------------------------------------------
        agregada = target
        if func == "6":
            agregada += 24
        else:
            agregada += 12
            while agregada <= base:
                agregada += 12

        if debug:
            print(
                f"Corchea {corchea}: paso {paso} {asignaciones[idx][0]} "
                f"{pretty_midi.note_number_to_name(base)} ({func}) -> "
                f"{pretty_midi.note_number_to_name(agregada)}"
            )

        for pitch in (base, agregada):
            resultado.append(
                pretty_midi.Note(
                    velocity=pos["velocity"],
                    pitch=pitch,
                    start=pos["start"],
                    end=pos["end"],
                )
            )

    return resultado


def _arm_noop(notas: List[pretty_midi.Note]) -> List[pretty_midi.Note]:
    """Placeholder for future harmonization types."""

    return notas


# Armonizaciones simples que no dependen del contexto del voicing
_ARMONIZADORES = {
    "octavas": _arm_octavas,
    "doble octava": _arm_doble_octava,
}


def aplicar_armonizacion(notas: List[pretty_midi.Note], opcion: str) -> List[pretty_midi.Note]:
    """Apply the selected harmonization option using ``_ARMONIZADORES``."""

    funcion = _ARMONIZADORES.get(opcion.lower())
    if funcion is None:
        return notas
    return funcion(notas)


def _grid_and_bpm(pm: pretty_midi.PrettyMIDI) -> Tuple[int, float, float]:
    """Return total number of eighth notes, duration of an eighth and bpm."""
    total = pm.get_end_time()
    times, tempi = pm.get_tempo_changes()
    bpm = tempi[0] if len(tempi) > 0 else 120.0
    grid = 60.0 / bpm / 2  # seconds per eighth note
    cor = int(round(total / grid))
    return cor, grid, bpm


def _recortar_notas_a_limite(
    notas: List[pretty_midi.Note], limite: float
) -> List[pretty_midi.Note]:
    """Recorta las notas para que no se extiendan más allá de ``limite``.

    Cualquier nota que termine después del instante indicado se acorta para
    que su atributo ``end`` coincida exactamente con ``limite``.  Las notas
    cuyo ``start`` es posterior al límite se descartan.
    """

    recortadas: List[pretty_midi.Note] = []
    for n in notas:
        if n.start >= limite:
            continue
        if n.end > limite:
            n.end = limite
        recortadas.append(n)
    return recortadas


def _cortar_notas_superpuestas(notas: List[pretty_midi.Note]) -> List[pretty_midi.Note]:
    """Shorten notes to avoid overlaps at the same pitch.

    If two consecutive notes share the same ``pitch`` and the first note
    extends beyond the start of the second, the first note is truncated so
    that it ends exactly when the following one begins.  This prevents MIDI
    artefacts caused by overlapping identical pitches.
    """

    agrupadas: dict[int, List[pretty_midi.Note]] = {}
    for n in sorted(notas, key=lambda x: (x.pitch, x.start)):
        lista = agrupadas.setdefault(n.pitch, [])
        if lista and lista[-1].end > n.start:
            lista[-1].end = n.start
        lista.append(n)

    resultado = [n for lst in agrupadas.values() for n in lst]
    resultado.sort(key=lambda x: (x.start, x.pitch))
    return resultado


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

    limite = total_dest_cor * grid

    arm = (armonizacion or "").lower()
    if arm == "terceras":
        nuevas_notas = _arm_terceras_intervalos(
            posiciones, voicings, asignaciones, grid, debug=debug
        )
    elif arm == "sextas":
        nuevas_notas = _arm_por_parejas(
            posiciones, voicings, asignaciones, grid, 2, debug=debug
        )
    else:
        nuevas_notas, _ = aplicar_voicings_a_referencia(
            posiciones, voicings, asignaciones, grid, debug=debug
        )

    # Avoid overlapping notes at the same pitch which can cause MIDI
    # artefacts by trimming preceding notes when necessary.
    nuevas_notas = _cortar_notas_superpuestas(nuevas_notas)

    # ------------------------------------------------------------------
    # Ajuste final de duracion: todas las notas se recortan para que
    # terminen, como maximo, en la ultima corchea programada.
    # ------------------------------------------------------------------
    nuevas_notas = _recortar_notas_a_limite(nuevas_notas, limite)

    # Se añade una nota de duracion cero al final para fijar la longitud
    if limite > 0:
        nuevas_notas.append(
            pretty_midi.Note(
                velocity=1,
                pitch=0,
                start=max(0.0, limite - grid),
                end=limite,
            )
        )

    if arm and arm not in ("terceras", "sextas"):
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
# ``PRIMER_BLOQUE`` y ``PATRON_REPETIDO`` definen el esquema de agrupación de
# corcheas utilizado por el modo tradicional.  El primer bloque se utiliza tal
# cual una única vez y a partir de entonces se repite ``PATRON_REPETIDO`` de
# forma indefinida.  Para cambiar el patrón basta con modificar estas dos
# listas.
PRIMER_BLOQUE: List[int] = [3, 4, 4, 3]
PATRON_REPETIDO: List[int] = [5, 4, 4, 3]

# ``PATRON_GRUPOS`` se mantiene solo como referencia para visualizar los
# primeros valores calculados con la configuración actual.
PATRON_GRUPOS: List[int] = PRIMER_BLOQUE + PATRON_REPETIDO * 3


def _siguiente_grupo(indice: int) -> int:
    """Devuelve la longitud del grupo de corcheas según ``indice``.

    Los cuatro primeros valores provienen de ``PRIMER_BLOQUE`` y, a partir de
    ahí, se repite ``PATRON_REPETIDO`` tantas veces como sea necesario.
    """
    if indice < len(PRIMER_BLOQUE):
        return PRIMER_BLOQUE[indice]
    indice -= len(PRIMER_BLOQUE)
    return PATRON_REPETIDO[indice % len(PATRON_REPETIDO)]



def procesar_progresion_en_grupos(texto: str) -> Tuple[List[Tuple[str, List[int]]], int]:
    """Asignar corcheas a los acordes usando ``_siguiente_grupo``.

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
