"""
Motor Principal del Pipeline de HandTracking.
Orquesta todos los módulos de la capa de negocio:
    Captura (webcam) → Suavizado (EMA) → Reconocimiento de Gestos → Acción del SO

Este módulo es el "cerebro" que app.py llamará para iniciar/detener el tracking.

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
# Estados:
#   IDLE             → No se está arrastrando. Estado por defecto.
#   PUNO_DETECTADO   → Se detectó un puño, pero aún no se confirma.
#                      Se requieren N frames consecutivos para confirmar.
#   DRAGGING         → Arrastre confirmado. El clic izquierdo está presionado.
#   RELEASE          → Se soltó el puño. Se libera el clic y vuelve a IDLE.
#
# Transiciones:
#   IDLE            --[puño detectado]--> PUNO_DETECTADO
#   PUNO_DETECTADO  --[puño N frames]--> DRAGGING
#   PUNO_DETECTADO  --[no puño]--------> IDLE  (falsa alarma)
#   DRAGGING        --[no puño]--------> RELEASE (con tolerancia a frames perdidos)
#   DRAGGING        --[pérdida mano]---> mantener DRAGGING por M frames de gracia
#   RELEASE         --[inmediato]------> IDLE
# =============================================================================

DRAG_IDLE = "IDLE"
DRAG_PUNO_DETECTADO = "PUNO_DETECTADO"
DRAG_DRAGGING = "DRAGGING"
DRAG_RELEASE = "RELEASE"


class MotorHandTracking:
    """
    Motor principal que conecta captura → suavizado → gestos → acciones.
    """

    def __init__(self):
        # Cargar configuración desde la capa de datos
        self.perfil = obtener_perfil_activo()

        # Componentes del pipeline
        self.captura = CapturaMano()
        self.filtro = FiltroEMA(alpha=self.perfil.suavizado_factor)
        self.controlador_mouse = ControladorMouse()

        # Estado interno general
        self.ejecutando = False
        self.gesto_anterior = "NINGUNO"
        self.posicion_scroll_anterior = None

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
        self.drag_frames_necesarios = 4       # Frames de puño para confirmar (≈133ms a 30fps)
        self.drag_frames_sin_puno = 0
        self.drag_tolerancia_frames = 6       # Frames de tolerancia antes de soltar (≈200ms)

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
            if abs(delta) > 0.01:  # Umbral mínimo de movimiento
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
                # Pellizco triple detectado → empezar a contar frames de confirmación
                self.drag_estado = DRAG_PUNO_DETECTADO
                self.drag_frames_confirmacion = 1
            return None

        elif self.drag_estado == DRAG_PUNO_DETECTADO:
            if es_pellizco_triple:
                self.drag_frames_confirmacion += 1
                if self.drag_frames_confirmacion >= self.drag_frames_necesarios:
                    # Confirmado: N frames consecutivos → iniciar drag
                    self.drag_estado = DRAG_DRAGGING
                    self.drag_frames_sin_puno = 0
                    return "INICIAR_DRAG"
            else:
                # Falsa alarma: no se mantuvo → volver a IDLE
                self.drag_estado = DRAG_IDLE
                self.drag_frames_confirmacion = 0
            return None

        elif self.drag_estado == DRAG_DRAGGING:
            if es_pellizco_triple:
                # Sigue arrastrando normalmente
                self.drag_frames_sin_puno = 0
                return "MANTENER_DRAG"
            else:
                # No hay puño: incrementar contador de tolerancia
                self.drag_frames_sin_puno += 1
                if self.drag_frames_sin_puno >= self.drag_tolerancia_frames:
                    # Superó la tolerancia → soltar el drag
                    self.drag_estado = DRAG_RELEASE
                    return "SOLTAR_DRAG"
                else:
                    # Dentro de la tolerancia → mantener drag (frame malo / glitch)
                    return "MANTENER_DRAG"

        elif self.drag_estado == DRAG_RELEASE:
            # Transición inmediata de RELEASE → IDLE
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

        # Mover siempre el cursor (salvo durante scroll)
        if accion != "SCROLL":
            self.controlador_mouse.mover_cursor(x_pantalla, y_pantalla)
            self.posicion_scroll_anterior = None

        # 2. Actualizar FSM del Drag & Drop
        estado_previo = self.drag_estado
        accion_drag = self._actualizar_fsm_drag(gesto)

        if accion_drag == "INICIAR_DRAG":
            self.controlador_mouse.iniciar_arrastre()
            return  # No ejecutar otra acción este frame
        elif accion_drag == "MANTENER_DRAG":
            return  # Solo mover cursor, el drag ya está activo
        elif accion_drag == "SOLTAR_DRAG":
            self.controlador_mouse.soltar_arrastre()
            return

        # Si estamos confirmando o arrastrando (o lo estábamos ANTES de este frame),
        # no ejecutar clicks ni scroll. Esto evita que un pellizco parcial
        # dispare un clic cuando el usuario está intentando hacer PELLIZCO_TRIPLE
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

    def iniciar(self, mostrar_preview=True):
        """
        Inicia el bucle principal del tracking de mano.

        Parámetros:
        - mostrar_preview: si True, muestra una ventana con la cámara y los landmarks.
        """
        self.ejecutando = True
        self.captura.iniciar_camara()

        print("[Motor] HandTracking iniciado. Presionar 'Q' para detener.")

        while self.ejecutando:
            exito, frame = self.captura.leer_frame()
            if not exito:
                break

            # Voltear horizontalmente para efecto espejo
            frame = cv2.flip(frame, 1)

            # Detectar landmarks
            landmarks, resultados = self.captura.detectar_landmarks(frame)

            if landmarks:
                # Reconocer gesto
                gesto = reconocer_gesto(landmarks)

                # Ejecutar acción correspondiente
                self._ejecutar_accion(gesto, landmarks)

                self.gesto_anterior = gesto

                # Determinar la acción que se muestra en pantalla (debug)
                accion_display = self.mapeo_gestos.get(gesto, "---")
                if self.drag_estado == DRAG_PUNO_DETECTADO:
                    accion_display = f"Confirmando... ({self.drag_frames_confirmacion}/{self.drag_frames_necesarios})"
                elif self.drag_estado == DRAG_DRAGGING:
                    accion_display = "ARRASTRANDO"

                # Dibujar info en el frame para debug
                if mostrar_preview:
                    cv2.putText(frame, f"Gesto: {gesto}", (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                    cv2.putText(frame, f"Accion: {accion_display}", (10, 70),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
                    cv2.putText(frame, f"Drag FSM: {self.drag_estado}", (10, 110),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 2)

            else:
                # No se detectó mano: si estamos arrastrando, contar frames de tolerancia
                if self.drag_estado == DRAG_DRAGGING:
                    self.drag_frames_sin_puno += 1
                    if self.drag_frames_sin_puno >= self.drag_tolerancia_frames:
                        self.controlador_mouse.soltar_arrastre()
                        self.drag_estado = DRAG_IDLE
                        self.drag_frames_sin_puno = 0

            # Dibujar landmarks en la preview
            if mostrar_preview:
                frame = self.captura.dibujar_landmarks(frame, resultados)
                cv2.imshow("HandTracking", frame)

                # Salir con la tecla 'Q'
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

        self.detener()

    def detener(self):
        """Detiene el tracking y libera recursos."""
        self.ejecutando = False
        self.controlador_mouse.soltar_arrastre()
        self.drag_estado = DRAG_IDLE
        self.captura.liberar()
        print("[Motor] HandTracking detenido.")

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

        self.mapeo_gestos.clear()
        for gesto_config in self.perfil.gestos:
            if gesto_config.habilitado:
                self.mapeo_gestos[gesto_config.nombre_gesto] = gesto_config.accion_sistema
        print("[Motor] Perfil recargado desde la base de datos.")
