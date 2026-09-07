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
import queue

from controller.captura import CapturaMano
from controller.suavizado import FiltroEMA
from controller.gestos import reconocer_gesto, calcular_centro_palma, INDICE_PUNTA
from controller.acciones import ControladorMouse
from datos.repositorio import obtener_perfil_activo
from controller.fsm_drag import DragStateMachine, DRAG_PUNO_DETECTADO, DRAG_DRAGGING


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

        # Umbral de pellizco configurable (sensibilidad de los clics)
        self.umbral_pellizco = self.perfil.umbral_pellizco

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
        self.fsm_drag = DragStateMachine(frames_necesarios=4, tolerancia_frames=6)

        # --- Cola de Eventos para la UI ---
        self.cola_estado = queue.Queue(maxsize=1)

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
        estado_previo = self.fsm_drag.estado
        accion_drag = self.fsm_drag.actualizar(accion == "DRAG_AND_DROP")

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
           self.fsm_drag.estado in (DRAG_PUNO_DETECTADO, DRAG_DRAGGING):
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

    def _enviar_estado_ui(self, frame, fps, latencia, mano_detectada, gesto_actual, accion_actual):
        estado = {
            "frame": frame,
            "fps": fps,
            "latencia": latencia,
            "mano_detectada": mano_detectada,
            "gesto": gesto_actual,
            "accion": accion_actual
        }
        if self.cola_estado.full():
            try:
                self.cola_estado.get_nowait()
            except queue.Empty:
                pass
        self.cola_estado.put(estado)

    def iniciar(self):
        """
        Inicia el bucle principal del tracking de mano.
        Diseñado para correr en un Thread separado.
        La UI lee self.cola_estado para mostrar la preview.
        """
        self.ejecutando = True
        self.captura.iniciar_camara()
        print("[Motor] HandTracking iniciado.")

        tiempo_anterior = time.time()
        contador_frames = 0
        fps_actual = 0.0
        latencia_ms = 0.0

        while self.ejecutando:
            try:
                # Si está pausado, no procesar pero seguir capturando
                if self.pausado:
                    exito, frame = self.captura.leer_frame()
                    if not exito:
                        raise RuntimeError("Error al leer frame en pausa")
                    
                    frame = cv2.flip(frame, 1)
                    cv2.putText(frame, "PAUSADO", (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                    self._enviar_estado_ui(frame, fps_actual, latencia_ms, False, "---", "PAUSADO")
                    time.sleep(0.033)  # ~30fps mínimo
                    continue

                inicio_frame = time.time()

                exito, frame = self.captura.leer_frame()
                if not exito:
                    raise RuntimeError("Error al leer frame activo")

                # Voltear horizontalmente para efecto espejo
                frame = cv2.flip(frame, 1)

                # Detectar landmarks
                landmarks, resultados = self.captura.detectar_landmarks(frame)

                mano_detectada = False
                gesto_actual = "---"
                accion_actual = "---"

                if landmarks:
                    mano_detectada = True
                    gesto = reconocer_gesto(landmarks, umbral_pellizco=self.umbral_pellizco)
                    gesto_actual = gesto

                    # Ejecutar acción correspondiente
                    self._ejecutar_accion(gesto, landmarks)

                    self.gesto_anterior = gesto

                    # Determinar la acción que se muestra
                    accion_display = self.mapeo_gestos.get(gesto, "---")
                    if self.fsm_drag.estado == DRAG_PUNO_DETECTADO:
                        accion_display = f"Confirmando... ({self.fsm_drag.frames_confirmacion}/{self.fsm_drag.frames_necesarios})"
                    elif self.fsm_drag.estado == DRAG_DRAGGING:
                        accion_display = "ARRASTRANDO"
                    accion_actual = accion_display

                    # Dibujar info en el frame
                    cv2.putText(frame, f"Gesto: {gesto}", (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    cv2.putText(frame, f"Accion: {accion_display}", (10, 60),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

                else:
                    # Tolerancia de drag ante pérdida de mano
                    if self.fsm_drag.estado == DRAG_DRAGGING:
                        accion_drag = self.fsm_drag.actualizar(False)
                        if accion_drag == "SOLTAR_DRAG":
                            self.controlador_mouse.soltar_arrastre()

                # Dibujar zona activa (Bounding Box)
                h, w_img, _ = frame.shape
                x1, y1 = int(self.zona_x_min * w_img), int(self.zona_y_min * h)
                x2, y2 = int(self.zona_x_max * w_img), int(self.zona_y_max * h)
                cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 150, 0), 2)
                cv2.putText(frame, "Zona Activa", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 150, 0), 1)

                # Dibujar landmarks en el frame
                frame = self.captura.dibujar_landmarks(frame, resultados)

                # Calcular FPS y latencia
                fin_frame = time.time()
                latencia_ms = (fin_frame - inicio_frame) * 1000
                contador_frames += 1
                if fin_frame - tiempo_anterior >= 1.0:
                    fps_actual = contador_frames / (fin_frame - tiempo_anterior)
                    contador_frames = 0
                    tiempo_anterior = fin_frame

                self._enviar_estado_ui(frame, fps_actual, latencia_ms, mano_detectada, gesto_actual, accion_actual)

            except Exception as e:
                print(f"[Motor] Error en cámara o procesamiento: {e}. Intentando reconectar...")
                time.sleep(1.0)
                try:
                    self.captura.liberar()
                    self.captura.iniciar_camara()
                except:
                    pass

        self.detener()

    def detener(self):
        """Detiene el tracking y libera recursos."""
        self.ejecutando = False
        self.controlador_mouse.soltar_arrastre()
        self.fsm_drag.resetear()
        self.captura.liberar()
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
        self.umbral_pellizco = self.perfil.umbral_pellizco

        self.mapeo_gestos.clear()
        for gesto_config in self.perfil.gestos:
            if gesto_config.habilitado:
                self.mapeo_gestos[gesto_config.nombre_gesto] = gesto_config.accion_sistema
        print("[Motor] Perfil recargado desde la base de datos.")
