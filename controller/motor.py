"""
Motor Principal del Pipeline de HandTracking.
Orquesta todos los módulos de la capa de negocio:
    Captura (webcam) → Suavizado (EMA) → Reconocimiento de Gestos → Acción del SO

Este módulo es el "cerebro" que la UI (views/dashboard.py) llamará para
iniciar/detener el tracking en un Thread separado.

IMPORTANTE (Checklist):
- Este módulo accede a la capa de datos ÚNICAMENTE a través de funciones
  del repositorio (datos.repositorio), nunca directamente a la base de datos.
- Este módulo NO contiene elementos de interfaz gráfica (botones, HTML, etc.).
"""

import time
import cv2

from controller.captura import CapturaMano
from controller.suavizado import FiltroEMA
from controller.gestos import reconocer_gesto, calcular_centro_palma, INDICE_PUNTA
from controller.acciones import ControladorMouse
from datos.repositorio import obtener_perfil_activo


# =============================================================================
# Máquina de Estados Finita (FSM) para Drag & Drop
# =============================================================================
DRAG_IDLE = "IDLE"
DRAG_PUNO_DETECTADO = "PUNO_DETECTADO"
DRAG_DRAGGING = "DRAGGING"
DRAG_RELEASE = "RELEASE"


class MotorHandTracking:
    """
    Motor principal que conecta captura → suavizado → gestos → acciones.
    Diseñado para correr en un Thread separado mientras la UI corre en el hilo principal.
    """

    def __init__(self):
        # Cargar configuración desde la capa de datos
        self.perfil = obtener_perfil_activo()

        # Componentes del pipeline
        self.captura = CapturaMano(id_camara=self.perfil.id_camara)
        self.filtro = FiltroEMA(alpha=self.perfil.suavizado_factor)
        self.controlador_mouse = ControladorMouse()
        self.controlador_mouse.set_zona_muerta(self.perfil.zona_muerta_px)

        # Estado interno general
        self.ejecutando = False
        self.pausado = False  # Para atajo global Ctrl+Alt+H
        self.gesto_anterior = "NINGUNO"
        self.posicion_scroll_anterior = None

        # Modo zurdo: invierte el eje X
        self.es_zurdo = self.perfil.es_zurdo

        # Mapeo de gestos a acciones (cargado desde la BD)
        self.mapeo_gestos = {}
        for gesto_config in self.perfil.gestos:
            if gesto_config.habilitado:
                self.mapeo_gestos[gesto_config.nombre_gesto] = gesto_config.accion_sistema

        # Zona activa (bounding box) desde el perfil
        self.zona_x_min = self.perfil.zona_activa_x_min
        self.zona_y_min = self.perfil.zona_activa_y_min
        self.zona_x_max = self.perfil.zona_activa_x_max
        self.zona_y_max = self.perfil.zona_activa_y_max

        # Cooldown para clics (evitar múltiples clics por cada frame)
        self.ultimo_clic_tiempo = 0
        self.cooldown_clic = 0.4  # segundos mínimos entre clics

        # --- FSM Drag & Drop ---
        self.drag_estado = DRAG_IDLE
        self.drag_frames_confirmacion = 0
        self.drag_frames_necesarios = 4
        self.drag_frames_sin_puno = 0
        self.drag_tolerancia_frames = 6

        # --- Estado en vivo (leído por la UI) ---
        self.fps_actual = 0.0
        self.latencia_ms = 0.0
        self.mano_detectada = False
        self.gesto_actual = "---"
        self.accion_actual = "---"
        self.ultimo_frame = None  # Frame procesado con landmarks (para la UI)

    def _normalizar_a_zona_activa(self, x, y):
        """
        Convierte las coordenadas de la mano (dentro de la zona activa definida)
        a coordenadas normalizadas [0.0, 1.0] para toda la pantalla.
        """
        x_norm = (x - self.zona_x_min) / (self.zona_x_max - self.zona_x_min)
        y_norm = (y - self.zona_y_min) / (self.zona_y_max - self.zona_y_min)

        x_norm = max(0.0, min(1.0, x_norm))
        y_norm = max(0.0, min(1.0, y_norm))

        return x_norm, y_norm

    def _ejecutar_scroll(self, landmarks):
        """Ejecuta la acción de scroll vertical basada en el movimiento de la mano."""
        y_actual = landmarks[INDICE_PUNTA][1]
        if self.posicion_scroll_anterior is not None:
            delta = self.posicion_scroll_anterior - y_actual
            if abs(delta) > 0.01:
                direccion = 1 if delta > 0 else -1
                self.controlador_mouse.scroll(direccion)
        self.posicion_scroll_anterior = y_actual

    def _actualizar_fsm_drag(self, gesto):
        """
        Actualiza la Máquina de Estados Finita (FSM) del Drag & Drop.

        Transiciones basadas en si el gesto actual es PELLIZCO_TRIPLE o no.
        Incluye confirmación por frames y tolerancia a pérdida breve.

        Retorna:
        - str con la acción a ejecutar: "INICIAR_DRAG", "MANTENER_DRAG",
          "SOLTAR_DRAG", o None si no hay acción de drag.
        """
        es_pellizco_triple = (gesto == "PELLIZCO_TRIPLE")

        if self.drag_estado == DRAG_IDLE:
            if es_pellizco_triple:
                self.drag_estado = DRAG_PUNO_DETECTADO
                self.drag_frames_confirmacion = 1
            return None

        elif self.drag_estado == DRAG_PUNO_DETECTADO:
            if es_pellizco_triple:
                self.drag_frames_confirmacion += 1
                if self.drag_frames_confirmacion >= self.drag_frames_necesarios:
                    self.drag_estado = DRAG_DRAGGING
                    self.drag_frames_sin_puno = 0
                    return "INICIAR_DRAG"
            else:
                self.drag_estado = DRAG_IDLE
                self.drag_frames_confirmacion = 0
            return None

        elif self.drag_estado == DRAG_DRAGGING:
            if es_pellizco_triple:
                self.drag_frames_sin_puno = 0
                return "MANTENER_DRAG"
            else:
                self.drag_frames_sin_puno += 1
                if self.drag_frames_sin_puno >= self.drag_tolerancia_frames:
                    self.drag_estado = DRAG_RELEASE
                    return "SOLTAR_DRAG"
                else:
                    return "MANTENER_DRAG"

        elif self.drag_estado == DRAG_RELEASE:
            self.drag_estado = DRAG_IDLE
            self.drag_frames_confirmacion = 0
            self.drag_frames_sin_puno = 0
            return None

        return None

    def _ejecutar_accion(self, gesto, landmarks):
        """
        Ejecuta la acción correspondiente al gesto detectado.
        Usa el centro de la palma como referencia de posición ultra estable.
        La lógica de Drag & Drop está gestionada por la FSM.
        """
        ahora = time.time()
        accion = self.mapeo_gestos.get(gesto)

        # 1. Calcular posición del cursor a partir del Centro de la Palma
        x_palma, y_palma = calcular_centro_palma(landmarks)
        x_suavizado, y_suavizado = self.filtro.aplicar((x_palma, y_palma))
        x_pantalla, y_pantalla = self._normalizar_a_zona_activa(x_suavizado, y_suavizado)

        # Modo zurdo: invertir eje X
        if self.es_zurdo:
            x_pantalla = 1.0 - x_pantalla

        # Mover siempre el cursor (salvo durante scroll)
        if accion != "SCROLL":
            self.controlador_mouse.mover_cursor(x_pantalla, y_pantalla)
            self.posicion_scroll_anterior = None

        # 2. Actualizar FSM del Drag & Drop
        estado_previo = self.drag_estado
        accion_drag = self._actualizar_fsm_drag(gesto)

        if accion_drag == "INICIAR_DRAG":
            self.controlador_mouse.iniciar_arrastre()
            return
        elif accion_drag == "MANTENER_DRAG":
            return
        elif accion_drag == "SOLTAR_DRAG":
            self.controlador_mouse.soltar_arrastre()
            return

        # Si estamos confirmando o arrastrando, suprimir clicks parciales
        if estado_previo in (DRAG_PUNO_DETECTADO, DRAG_DRAGGING) or \
           self.drag_estado in (DRAG_PUNO_DETECTADO, DRAG_DRAGGING):
            return

        # 3. Ejecutar acciones normales (solo si NO estamos en drag)
        if accion == "CLIC_IZQUIERDO":
            if ahora - self.ultimo_clic_tiempo > self.cooldown_clic:
                self.controlador_mouse.clic_izquierdo()
                self.ultimo_clic_tiempo = ahora

        elif accion == "CLIC_DERECHO":
            if ahora - self.ultimo_clic_tiempo > self.cooldown_clic:
                self.controlador_mouse.clic_derecho()
                self.ultimo_clic_tiempo = ahora

        elif accion == "SCROLL":
            self._ejecutar_scroll(landmarks)

        elif accion == "DRAG_AND_DROP":
            if not self.controlador_mouse.esta_arrastrando:
                self.controlador_mouse.iniciar_arrastre()
        else:
            if self.controlador_mouse.esta_arrastrando and accion != "DRAG_AND_DROP":
                self.controlador_mouse.soltar_arrastre()

    def iniciar(self):
        """
        Inicia el bucle principal del tracking de mano.
        Diseñado para correr en un Thread separado.
        La UI lee self.ultimo_frame para mostrar la preview.
        """
        self.ejecutando = True
        self.captura.iniciar_camara()
        print("[Motor] HandTracking iniciado.")

        tiempo_anterior = time.time()
        contador_frames = 0

        while self.ejecutando:
            # Si está pausado, no procesar pero seguir capturando
            if self.pausado:
                exito, frame = self.captura.leer_frame()
                if not exito:
                    break
                frame = cv2.flip(frame, 1)
                cv2.putText(frame, "PAUSADO", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                self.ultimo_frame = frame
                self.mano_detectada = False
                self.gesto_actual = "---"
                self.accion_actual = "PAUSADO"
                time.sleep(0.033)  # ~30fps mínimo
                continue

            inicio_frame = time.time()

            exito, frame = self.captura.leer_frame()
            if not exito:
                break

            # Voltear horizontalmente para efecto espejo
            frame = cv2.flip(frame, 1)

            # Detectar landmarks
            landmarks, resultados = self.captura.detectar_landmarks(frame)

            if landmarks:
                self.mano_detectada = True
                gesto = reconocer_gesto(landmarks)
                self.gesto_actual = gesto

                # Ejecutar acción correspondiente
                self._ejecutar_accion(gesto, landmarks)

                self.gesto_anterior = gesto

                # Determinar la acción que se muestra
                accion_display = self.mapeo_gestos.get(gesto, "---")
                if self.drag_estado == DRAG_PUNO_DETECTADO:
                    accion_display = f"Confirmando... ({self.drag_frames_confirmacion}/{self.drag_frames_necesarios})"
                elif self.drag_estado == DRAG_DRAGGING:
                    accion_display = "ARRASTRANDO"
                self.accion_actual = accion_display

                # Dibujar info en el frame
                cv2.putText(frame, f"Gesto: {gesto}", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                cv2.putText(frame, f"Accion: {accion_display}", (10, 60),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

            else:
                self.mano_detectada = False
                self.gesto_actual = "---"
                self.accion_actual = "---"

                # Tolerancia de drag ante pérdida de mano
                if self.drag_estado == DRAG_DRAGGING:
                    self.drag_frames_sin_puno += 1
                    if self.drag_frames_sin_puno >= self.drag_tolerancia_frames:
                        self.controlador_mouse.soltar_arrastre()
                        self.drag_estado = DRAG_IDLE
                        self.drag_frames_sin_puno = 0

            # Dibujar landmarks en el frame
            frame = self.captura.dibujar_landmarks(frame, resultados)
            self.ultimo_frame = frame

            # Calcular FPS y latencia
            fin_frame = time.time()
            self.latencia_ms = (fin_frame - inicio_frame) * 1000
            contador_frames += 1
            if fin_frame - tiempo_anterior >= 1.0:
                self.fps_actual = contador_frames / (fin_frame - tiempo_anterior)
                contador_frames = 0
                tiempo_anterior = fin_frame

        self.detener()

    def detener(self):
        """Detiene el tracking y libera recursos."""
        self.ejecutando = False
        self.controlador_mouse.soltar_arrastre()
        self.drag_estado = DRAG_IDLE
        self.captura.liberar()
        self.mano_detectada = False
        self.gesto_actual = "---"
        self.accion_actual = "---"
        self.fps_actual = 0.0
        self.ultimo_frame = None
        print("[Motor] HandTracking detenido.")

    def alternar_pausa(self):
        """Alterna entre pausado y activo. Para usar con el atajo global."""
        self.pausado = not self.pausado
        estado = "pausado" if self.pausado else "activo"
        print(f"[Motor] Tracking {estado}.")

    def recargar_perfil(self):
        """
        Recarga la configuración desde la base de datos.
        Útil cuando el usuario cambia parámetros desde el Dashboard.
        """
        self.perfil = obtener_perfil_activo()
        self.filtro.set_alpha(self.perfil.suavizado_factor)
        self.zona_x_min = self.perfil.zona_activa_x_min
        self.zona_y_min = self.perfil.zona_activa_y_min
        self.zona_x_max = self.perfil.zona_activa_x_max
        self.zona_y_max = self.perfil.zona_activa_y_max
        self.controlador_mouse.set_zona_muerta(self.perfil.zona_muerta_px)
        self.es_zurdo = self.perfil.es_zurdo

        self.mapeo_gestos.clear()
        for gesto_config in self.perfil.gestos:
            if gesto_config.habilitado:
                self.mapeo_gestos[gesto_config.nombre_gesto] = gesto_config.accion_sistema
        print("[Motor] Perfil recargado desde la base de datos.")
