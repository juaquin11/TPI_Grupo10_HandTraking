"""
Módulo de Captura de Video y Detección de Landmarks.
Utiliza OpenCV para capturar el flujo de la webcam y MediaPipe Tasks API (v1.0+)
para extraer las coordenadas articulares (landmarks) de la mano.

IMPORTANTE (Checklist): Este módulo NO accede a la base de datos directamente.
"""

import os
import cv2
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import (
    HandLandmarker,
    HandLandmarkerOptions,
    RunningMode,
)

# Ruta al modelo descargado
MODELO_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", "hand_landmarker.task")


class CapturaMano:
    """
    Captura video de la webcam y detecta los landmarks de la mano
    usando MediaPipe HandLandmarker (Tasks API v1.0+).
    """

    def __init__(self, id_camara=0, max_manos=1, confianza_deteccion=0.7, confianza_seguimiento=0.6):
        """
        Parámetros:
        - id_camara: índice de la webcam (0 = cámara por defecto).
        - max_manos: cantidad máxima de manos a detectar simultáneamente.
        - confianza_deteccion: umbral mínimo de confianza para detección.
        - confianza_seguimiento: umbral mínimo de confianza para seguimiento.
        """
        self.id_camara = id_camara
        self.captura = None
        self._frame_timestamp = 0

        # Configurar el HandLandmarker con la nueva Tasks API
        opciones = HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=MODELO_PATH),
            running_mode=RunningMode.VIDEO,
            num_hands=max_manos,
            min_hand_detection_confidence=confianza_deteccion,
            min_hand_presence_confidence=confianza_seguimiento,
            min_tracking_confidence=confianza_seguimiento,
        )
        self.detector = HandLandmarker.create_from_options(opciones)

    def iniciar_camara(self):
        """Abre la webcam para comenzar a capturar video."""
        self.captura = cv2.VideoCapture(self.id_camara)
        if not self.captura.isOpened():
            raise RuntimeError(f"No se pudo abrir la cámara con ID {self.id_camara}")

    def leer_frame(self):
        """
        Lee un frame de la webcam.
        Retorna: (exito: bool, frame: imagen BGR de OpenCV)
        """
        if self.captura is None:
            raise RuntimeError("La cámara no fue iniciada. Llamar a iniciar_camara() primero.")
        return self.captura.read()

    def detectar_landmarks(self, frame):
        """
        Procesa un frame BGR y extrae los landmarks de la mano.

        Parámetros:
        - frame: imagen BGR capturada por OpenCV.

        Retorna:
        - landmarks: lista de 21 tuplas (x, y, z) normalizados [0.0, 1.0],
          o None si no se detectó ninguna mano.
        - resultados: el objeto HandLandmarkerResult completo.
        """
        # Convertir a formato MediaPipe Image (RGB)
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)

        # Incrementar timestamp (MediaPipe VIDEO mode requiere timestamps crecientes)
        self._frame_timestamp += 33  # ~30 FPS (33ms por frame)
        resultados = self.detector.detect_for_video(mp_image, self._frame_timestamp)

        if resultados.hand_landmarks:
            mano = resultados.hand_landmarks[0]  # Tomar la primera mano
            landmarks = [(punto.x, punto.y, punto.z) for punto in mano]
            return landmarks, resultados

        return None, resultados

    def dibujar_landmarks(self, frame, landmarks_lista):
        """
        Dibuja los landmarks y conexiones de la mano sobre el frame (útil para debug).
        Usa dibujo manual ya que mp.solutions.drawing_utils no existe en v1.0+.
        """
        if landmarks_lista is None:
            return frame

        # Si recibimos un HandLandmarkerResult, extraemos la lista de landmarks
        if hasattr(landmarks_lista, 'hand_landmarks') and landmarks_lista.hand_landmarks:
            manos = landmarks_lista.hand_landmarks
        else:
            return frame

        alto, ancho, _ = frame.shape

        # Conexiones entre landmarks (esqueleto de la mano)
        conexiones = [
            (0, 1), (1, 2), (2, 3), (3, 4),      # Pulgar
            (0, 5), (5, 6), (6, 7), (7, 8),      # Índice
            (0, 9), (9, 10), (10, 11), (11, 12),  # Medio
            (0, 13), (13, 14), (14, 15), (15, 16), # Anular
            (0, 17), (17, 18), (18, 19), (19, 20), # Meñique
            (5, 9), (9, 13), (13, 17),             # Palma
        ]

        for mano in manos:
            # Dibujar conexiones (líneas)
            for inicio, fin in conexiones:
                x1 = int(mano[inicio].x * ancho)
                y1 = int(mano[inicio].y * alto)
                x2 = int(mano[fin].x * ancho)
                y2 = int(mano[fin].y * alto)
                cv2.line(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

            # Dibujar puntos (landmarks)
            for punto in mano:
                x = int(punto.x * ancho)
                y = int(punto.y * alto)
                cv2.circle(frame, (x, y), 5, (0, 0, 255), -1)

        return frame

    def liberar(self):
        """Libera los recursos de la cámara y MediaPipe."""
        if self.captura is not None:
            self.captura.release()
        self.detector.close()
        cv2.destroyAllWindows()
