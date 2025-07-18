import pretty_midi
from pathlib import Path

# ===================== Diccionarios de acordes y notas ======================

INTERVALOS_TRADICIONALES = {
    '6':      [0, 4, 7, 9],     # 1 3 5 6
    '7':      [0, 4, 7, 10],    # 1 3 5 b7
    '∆':      [0, 4, 7, 11],    # 1 3 5 7
    'm6':     [0, 3, 7, 9],     # 1 b3 5 6
    'm7':     [0, 3, 7, 10],    # 1 b3 5 b7
    'm∆':     [0, 3, 7, 11],    # 1 b3 5 7
    '+7':     [0, 4, 8, 10],    # 1 3 #5 b7
    '∆sus4':  [0, 5, 7, 11],    # 1 4 5 7
    '∆sus2':  [0, 2, 7, 11],    # 1 2 5 7
    '7sus4':  [0, 5, 7, 10],    # 1 4 5 b7
    '7sus2':  [0, 2, 7, 10],    # 1 2 5 b7
    'º7':     [0, 3, 6, 9],     # 1 b3 b5 bb7 (bb7 = 6ma mayor)
    'º∆':     [0, 3, 6, 11],    # 1 b3 b5 7
    'ø':      [0, 3, 6, 10],    # 1 b3 b5 b7
    '7(b5)':  [0, 4, 6, 10],    # 1 3 b5 b7
    '∆(b5)':  [0, 4, 6, 11],    # 1 3 b5 7
}

NOTAS = {
    'C':0,  'B#':0,
    'C#':1, 'Db':1,
    'D':2,
    'D#':3,'Eb':3,
    'E':4, 'Fb':4,
    'F':5, 'E#':5,
    'F#':6,'Gb':6,
    'G':7,
    'G#':8,'Ab':8,
    'A':9,
    'A#':10,'Bb':10,
    'B':11, 'Cb':11,
}

# ===================== Parser de acordes y generador de voicings ======================

def parsear_nombre_acorde(nombre):
    import re
    m = re.match(r'^([A-G][b#]?)(m6|m7|m∆|m|6|7|∆sus4|∆sus2|∆|\+7|º7|º∆|ø|7sus4|7sus2|7\(b5\)|∆\(b5\))$', nombre)
    if not m:
        raise ValueError(f"Acorde no reconocido: {nombre}")
    root, suf = m.group(1), m.group(2)
    return NOTAS[root], suf

def generar_voicings_enlazados_tradicional(progresion):
    """
    progresion: lista de nombres de acordes (ej: ['C7', 'F∆', 'G7sus4'])
    Devuelve: lista de voicings, cada uno lista de 4 notas MIDI, enlazados por la nota grave
    """
    voicings = []
    bajo_anterior = 43  # G2

    for idx, nombre in enumerate(progresion):
        root, suf = parsear_nombre_acorde(nombre)
        intervalos = INTERVALOS_TRADICIONALES[suf]
        notas_base = [root + i for i in intervalos]
        candidatos = []
        for o in range(1, 5):  # octavas razonables para graves
            acorde = [n + 12*o for n in notas_base]
            for idx_bajo, n in enumerate(acorde):
                distancia = abs(n - bajo_anterior)
                candidatos.append((distancia, n, acorde, idx_bajo))
        candidatos_comunes = [c for c in candidatos if c[1] == bajo_anterior]
        if candidatos_comunes:
            mejor = min(candidatos_comunes, key=lambda x: x[0])
        else:
            mejor = min(candidatos, key=lambda x: x[0])
        nuevo_bajo = mejor[1]
        acorde = mejor[2]
        idx_bajo = mejor[3]
        resto = acorde[:idx_bajo] + acorde[idx_bajo+1:]
        resto.sort()
        voicing = [nuevo_bajo] + resto
        voicings.append(voicing)
        bajo_anterior = nuevo_bajo
    return voicings

# ===================== Manejo de archivo MIDI referencia ======================

NOTAS_BASE = [43, 45, 48, 52]  # G2, A2, C3, E3

def leer_midi_referencia(midi_path):
    pm = pretty_midi.PrettyMIDI(str(midi_path))
    # Solo primer instrumento por ahora
    instrumento = pm.instruments[0]
    return instrumento.notes, pm

def obtener_posiciones_referencia(notes):
    # Registra todas las posiciones y duraciones de las 4 notas base
    posiciones = []
    for n in notes:
        if n.pitch in NOTAS_BASE:
            posiciones.append({
                'pitch': n.pitch,
                'start': n.start,
                'end': n.end
            })
    # Ordena por inicio temporal y luego por pitch (grave a agudo)
    posiciones.sort(key=lambda x: (x['start'], x['pitch']))
    return posiciones

# ===================== Conversión a nuevo MIDI ======================

def aplicar_voicings_a_referencia(posiciones, voicings, grupos_corchea, grid_seg):
    """
    posiciones: lista de dicts con pitch, start, end de las notas base en la ref.
    voicings: lista de listas, cada una con 4 notas MIDI
    grupos_corchea: lista con la cantidad de corcheas por grupo (ej: [3,2,4,2,5,2,4,2...])
    grid_seg: duración de una corchea en segundos (float)
    """
    nuevas_notas = []
    idx_voicing = 0
    corchea_actual = 1
    grupo_limite = grupos_corchea[0]

    for pos in posiciones:
        # Calcula a qué corchea pertenece esta nota
        corchea = int(round(pos['start'] / grid_seg)) + 1
        while corchea > grupo_limite and idx_voicing + 1 < len(voicings):
            # Pasamos al siguiente grupo/voicing
            idx_voicing += 1
            corchea_actual = grupo_limite + 1
            if idx_voicing < len(grupos_corchea):
                grupo_limite += grupos_corchea[idx_voicing]
        # Selecciona el voicing actual
        voicing = voicings[idx_voicing]
        # Reemplaza la nota base por la correspondiente en el voicing (orden grave→agudo)
        orden = NOTAS_BASE.index(pos['pitch'])
        nueva_nota = pretty_midi.Note(
            velocity = 100,
            pitch = voicing[orden],
            start = pos['start'],
            end = pos['end']
        )
        nuevas_notas.append(nueva_nota)
    return nuevas_notas

def _grid_and_bpm(pm):
    """
    Devuelve:
      - Número total de corcheas (int)
      - Duración de una corchea en segundos (float)
      - bpm (float)
    """
    total = pm.get_end_time()
    times, tempi = pm.get_tempo_changes()
    bpm = tempi[0] if len(tempi) > 0 else 120.0
    grid = 60.0 / bpm / 2    # duración de la corchea en segundos
    cor = int(round(total / grid))  # número de corcheas totales
    return cor, grid, bpm

def exportar_montuno_tradicional(
        midi_referencia_path,
        voicings,
        grupos_corchea,
        output_path
    ):
    notes, pm = leer_midi_referencia(midi_referencia_path)
    posiciones = obtener_posiciones_referencia(notes)
    # Determina grid (duración de corchea) usando el tempo
    cor, grid, bpm = _grid_and_bpm(pm)
    nuevas_notas = aplicar_voicings_a_referencia(posiciones, voicings, grupos_corchea, grid)
    # Genera nuevo MIDI
    pm_out = pretty_midi.PrettyMIDI(initial_tempo = bpm)
    inst_out = pretty_midi.Instrument(program = pm.instruments[0].program,
                                      is_drum  = pm.instruments[0].is_drum,
                                      name     = pm.instruments[0].name)
    inst_out.notes = nuevas_notas
    pm_out.instruments.append(inst_out)
    pm_out.write(str(output_path))
    print(f"Archivo MIDI exportado en: {output_path}")

# =============== Generador de grupos de corcheas según la lógica tradicional ==============

def generar_grupos_corchea(num_acordes):
    grupos = [3, 2, 4, 2]  # primer "compás"
    while len(grupos) < num_acordes:
        grupos += [5, 2, 4, 2]
    return grupos[:num_acordes]

# ============================= USO DE EJEMPLO ================================

if __name__ == "__main__":
    # Cambia la ruta aquí a donde tengas el archivo midi de referencia:
    midi_ref = Path("tradicional_2-3.mid")
    # Cambia la progresión a tu gusto:
    progresion = ['C7', 'F∆', 'G7sus4', 'C6', 'Dm7', 'G7', 'C∆', 'F7']
    voicings = generar_voicings_enlazados_tradicional(progresion)
    grupos_corchea = generar_grupos_corchea(len(voicings))
    exportar_montuno_tradicional(
        midi_ref,
        voicings,
        grupos_corchea,
        Path("montuno_tradicional_output.mid")
    )
