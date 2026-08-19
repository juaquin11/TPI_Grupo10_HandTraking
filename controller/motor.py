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

        # Estado interno
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

    def _ejecutar_accion(self, gesto, landmarks):
        """
        Ejecuta la acción correspondiente al gesto detectado.
        Usa el centro de la palma como referencia de posición ultra estable.
        """
        ahora = time.time()
        accion = self.mapeo_gestos.get(gesto)

        # 1. Calcular posición del cursor a partir del Centro de la Palma (ultra estable)
        x_palma, y_palma = calcular_centro_palma(landmarks)
        x_suavizado, y_suavizado = self.filtro.aplicar((x_palma, y_palma))
        x_pantalla, y_pantalla = self._normalizar_a_zona_activa(x_suavizado, y_suavizado)

        # Mover siempre el cursor con la posición de la palma (salvo que no haya acción asignada)
        if accion != "SCROLL":
            self.controlador_mouse.mover_cursor(x_pantalla, y_pantalla)
            self.posicion_scroll_anterior = None

        # 2. Ejecutar la acción según el gesto
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

                # Si el gesto anterior era PELLIZCO y ahora no, soltar el drag
                if self.gesto_anterior == "PELLIZCO" and gesto != "PELLIZCO":
                    self.controlador_mouse.soltar_arrastre()

                self.gesto_anterior = gesto

                # Determinar la acción que se muestra en pantalla
                if gesto == "UN_DEDO_INDICE" and self.tiempo_inicio_un_dedo is not None:
                    tiempo_en_gesto = time.time() - self.tiempo_inicio_un_dedo
                    accion_display = "SCROLL" if tiempo_en_gesto >= self.umbral_tiempo_scroll else "Decidiendo..."
                else:
                    accion_display = self.mapeo_gestos.get(gesto, "---")

                # Dibujar info en el frame para debug
                if mostrar_preview:
                    cv2.putText(frame, f"Gesto: {gesto}", (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                    cv2.putText(frame, f"Accion: {accion_display}", (10, 70),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

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
