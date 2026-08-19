"""
Módulo de Reconocimiento e Interpretación de Gestos.
Analiza los landmarks de la mano y determina qué gesto
está realizando el usuario.

Esquema de gestos v2 (basado en centro de palma + pellizcos):
- El cursor SIEMPRE se mueve con el centro de la palma (estable al flexionar dedos).
- PELLIZCO_INDICE (pulgar + índice juntos) → CLIC_IZQUIERDO
- PELLIZCO_MEDIO (pulgar + medio juntos) → CLIC_DERECHO
- DOS_DEDOS (índice + medio levantados) → SCROLL
- PELLIZCO_SOSTENIDO (pellizco índice + mover) → DRAG_AND_DROP

IMPORTANTE (Checklist): Este módulo NO accede a la base de datos directamente.
"""

# Índices de los landmarks de MediaPipe Hands (21 puntos por mano)
# Referencia: https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker
MUNECA = 0
PULGAR_CMC = 1
PULGAR_MCP = 2
PULGAR_IP = 3
PULGAR_PUNTA = 4
INDICE_MCP = 5
INDICE_PIP = 6
INDICE_DIP = 7
INDICE_PUNTA = 8
MEDIO_MCP = 9
MEDIO_PIP = 10
MEDIO_DIP = 11
MEDIO_PUNTA = 12
ANULAR_MCP = 13
ANULAR_PIP = 14
ANULAR_DIP = 15
ANULAR_PUNTA = 16
MENIQUE_MCP = 17
MENIQUE_PIP = 18
MENIQUE_DIP = 19
MENIQUE_PUNTA = 20

# Landmarks que forman el centro de la palma (para tracking estable del cursor)
LANDMARKS_PALMA = [MUNECA, INDICE_MCP, MEDIO_MCP, ANULAR_MCP, MENIQUE_MCP]


def calcular_centro_palma(landmarks):
    """
    Calcula el centro de la palma como promedio de 5 landmarks estables:
    muñeca (#0), base índice (#5), base medio (#9), base anular (#13), base meñique (#17).

    Este punto apenas se mueve cuando los dedos se flexionan, ideal para
    trackear el cursor de forma estable.

    Retorna:
    - tupla (x, y) normalizada.
    """
    x_centro = sum(landmarks[i][0] for i in LANDMARKS_PALMA) / len(LANDMARKS_PALMA)
    y_centro = sum(landmarks[i][1] for i in LANDMARKS_PALMA) / len(LANDMARKS_PALMA)
    return (x_centro, y_centro)


def _dedo_levantado(landmarks, punta, pip):
    """
    Determina si un dedo está levantado (extendido).
    Un dedo se considera levantado si la punta está por ENCIMA
    de la articulación PIP (en coordenadas normalizadas, Y menor = más arriba).
    """
    return landmarks[punta][1] < landmarks[pip][1]


def _pulgar_levantado(landmarks):
    """
    Determina si el pulgar está extendido.
    Se compara en el eje X ya que el pulgar se mueve lateralmente.
    """
    return abs(landmarks[PULGAR_PUNTA][0] - landmarks[MUNECA][0]) > \
           abs(landmarks[PULGAR_IP][0] - landmarks[MUNECA][0])


def _distancia_entre_puntos(punto_a, punto_b):
    """Calcula la distancia euclidiana 2D entre dos landmarks."""
    return ((punto_a[0] - punto_b[0]) ** 2 + (punto_a[1] - punto_b[1]) ** 2) ** 0.5


def obtener_estado_dedos(landmarks):
    """
    Retorna un diccionario con el estado (levantado o no) de cada dedo.

    Retorna:
    - dict con claves: 'pulgar', 'indice', 'medio', 'anular', 'menique'
      y valores booleanos (True = levantado).
    """
    return {
        "pulgar": _pulgar_levantado(landmarks),
        "indice": _dedo_levantado(landmarks, INDICE_PUNTA, INDICE_PIP),
        "medio": _dedo_levantado(landmarks, MEDIO_PUNTA, MEDIO_PIP),
        "anular": _dedo_levantado(landmarks, ANULAR_PUNTA, ANULAR_PIP),
        "menique": _dedo_levantado(landmarks, MENIQUE_PUNTA, MENIQUE_PIP),
    }


def reconocer_gesto(landmarks, umbral_pellizco=0.06):
    """
    Analiza los landmarks de la mano y retorna el nombre del gesto detectado.
    Versión 2: usa pellizcos para clicks (más estable con tracking de palma).

    Parámetros:
    - landmarks: lista de 21 tuplas (x, y, z) normalizadas.
    - umbral_pellizco: distancia máxima entre pulgar y dedo para
      considerar un pellizco.

    Retorna:
    - str: "PELLIZCO_INDICE", "PELLIZCO_MEDIO", "DOS_DEDOS", o "MANO_ABIERTA".
    """
    dedos = obtener_estado_dedos(landmarks)

    # 1. PELLIZCO_TRIPLE: pulgar + índice + medio juntos → DRAG_AND_DROP
    dist_pulgar_indice = _distancia_entre_puntos(
        landmarks[PULGAR_PUNTA], landmarks[INDICE_PUNTA]
    )
    dist_pulgar_medio = _distancia_entre_puntos(
        landmarks[PULGAR_PUNTA], landmarks[MEDIO_PUNTA]
    )

    if dist_pulgar_indice < umbral_pellizco and dist_pulgar_medio < umbral_pellizco:
        return "PELLIZCO_TRIPLE"

    # 2. PELLIZCO_INDICE: pulgar + índice juntos → CLIC_IZQUIERDO
    if dist_pulgar_indice < umbral_pellizco:
        return "PELLIZCO_INDICE"

    # 3. PELLIZCO_MEDIO: pulgar + medio juntos → CLIC_DERECHO
    if dist_pulgar_medio < umbral_pellizco:
        return "PELLIZCO_MEDIO"

    # 4. DOS_DEDOS: índice Y medio levantados → SCROLL
    if dedos["indice"] and dedos["medio"] and not dedos["anular"] and not dedos["menique"]:
        return "DOS_DEDOS"

    # 5. MANO_ABIERTA: cualquier otra configuración → solo mover cursor
    return "MANO_ABIERTA"


# =============================================================================
# CÓDIGO ANTERIOR (v1) - Gestos basados en flexión de dedos
# Se conserva como referencia. Para restaurarlo, renombrar la función
# reconocer_gesto_v1 a reconocer_gesto y comentar la versión v2 de arriba.
# =============================================================================

# def reconocer_gesto_v1(landmarks, umbral_pellizco=0.05):
#     """
#     Versión anterior de reconocimiento de gestos.
#     Esquema v1:
#     - DOS_DEDOS (índice + medio levantados) → MOVER_CURSOR
#     - CLIC_INDICE (flexionar índice, medio levantado) → CLIC_IZQUIERDO
#     - UN_DEDO_INDICE (solo índice levantado) → SCROLL / CLIC_DERECHO (por tiempo)
#     - PELLIZCO (pulgar + índice juntos) → DRAG_AND_DROP
#     """
#     dedos = obtener_estado_dedos(landmarks)
#
#     distancia_pellizco = _distancia_entre_puntos(
#         landmarks[PULGAR_PUNTA], landmarks[INDICE_PUNTA]
#     )
#     if distancia_pellizco < umbral_pellizco:
#         return "PELLIZCO"
#
#     if dedos["indice"] and dedos["medio"] and not dedos["anular"] and not dedos["menique"]:
#         return "DOS_DEDOS"
#
#     if not dedos["indice"] and dedos["medio"] and not dedos["anular"] and not dedos["menique"]:
#         return "CLIC_INDICE"
#
#     if dedos["indice"] and not dedos["medio"] and not dedos["anular"] and not dedos["menique"]:
#         return "UN_DEDO_INDICE"
#
#     return "NINGUNO"
