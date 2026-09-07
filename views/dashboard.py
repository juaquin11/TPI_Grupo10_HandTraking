"""
Dashboard Principal del Sistema HandTracking.
Interfaz gráfica construida con CustomTkinter que permite al usuario:
- Iniciar/detener el tracking de mano.
- Ver la preview de la cámara con landmarks en vivo.
- Monitorear estado en tiempo real (FPS, latencia, gesto detectado).
- Calibrar zona activa, suavizado y zona muerta.
- Seleccionar cámara y modo zurdo/diestro.
- Guardar el perfil de calibración en la base de datos.

IMPORTANTE (Checklist):
- Este módulo NO accede a la base de datos directamente.
- Toda comunicación con la BD pasa por controller/ y datos/repositorio.
"""

import threading
import cv2
import queue
import concurrent.futures
import keyboard
from PIL import Image, ImageTk
import customtkinter as ctk

from controller.motor import MotorHandTracking
from datos.repositorio import (
    obtener_perfil_activo,
    guardar_perfil,
    guardar_mapeo_completo_gestos,
    restaurar_gestos_predeterminados,
)
from views.pip_window import WidgetFlotante


# Tema global de CustomTkinter
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class Dashboard(ctk.CTk):
    """
    Ventana principal del Dashboard de HandTracking.
    """

    def __init__(self):
        super().__init__()

        self.title("🖐️ HandTracking — Panel de Control")
        self.geometry("960x720")
        self.minsize(900, 680)
        self.protocol("WM_DELETE_WINDOW", self._al_cerrar)

        # Thread pool para operaciones de DB asíncronas
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

        # Motor y estado
        self.motor = None
        self.hilo_motor = None
        self.tracking_activo = False

        # Modo Widget Flotante (PiP)
        self.pip_window = None
        self.bind("<Unmap>", self._on_window_unmap)
        self.bind("<Map>", self._on_window_map)

        # Cargar perfil actual
        self.perfil = obtener_perfil_activo()

        # Registrar atajo global Ctrl+Alt+H
        keyboard.add_hotkey("ctrl+alt+h", self._alternar_pausa_global)

        # Construir la interfaz
        self._crear_interfaz()

        # Iniciar actualización periódica de la preview
        self._actualizar_preview()

    # =========================================================================
    # EVENTOS DE VENTANA (MINIMIZAR/RESTAURAR)
    # =========================================================================

    def _on_window_unmap(self, event):
        """Detecta cuando la ventana principal se minimiza para abrir el PiP."""
        if event.widget == self and self.state() == "iconic":
            # Solo abrir el PiP si el tracking está activo
            if self.pip_window is None and self.tracking_activo:
                self.pip_window = WidgetFlotante(self, self._restaurar_desde_pip)

    def _on_window_map(self, event):
        """Detecta cuando la ventana principal se restaura para cerrar el PiP."""
        if event.widget == self and self.state() in ("normal", "zoomed"):
            self._cerrar_pip()

    def _restaurar_desde_pip(self):
        """Restaura la ventana principal desde el widget PiP."""
        self._cerrar_pip()
        self.deiconify()

    def _cerrar_pip(self):
        """Cierra el widget PiP si existe."""
        if self.pip_window is not None:
            self.pip_window.destroy()
            self.pip_window = None

    # =========================================================================
    # CONSTRUCCIÓN DE LA INTERFAZ
    # =========================================================================

    def _crear_interfaz(self):
        """Construye todos los widgets del dashboard."""

        # --- Layout principal: 2 columnas ---
        self.grid_columnconfigure(0, weight=3)  # Preview (más ancho)
        self.grid_columnconfigure(1, weight=2)  # Panel lateral
        self.grid_rowconfigure(0, weight=1)

        # ===== COLUMNA IZQUIERDA: Preview + Estado =====
        col_izq = ctk.CTkFrame(self, corner_radius=10)
        col_izq.grid(row=0, column=0, padx=(10, 5), pady=10, sticky="nsew")
        col_izq.grid_rowconfigure(0, weight=1)
        col_izq.grid_columnconfigure(0, weight=1)

        # Preview de cámara
        self.label_preview = ctk.CTkLabel(col_izq, text="Cámara no iniciada",
                                          font=ctk.CTkFont(size=14))
        self.label_preview.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="nsew")

        # Panel de estado en vivo
        frame_estado = ctk.CTkFrame(col_izq, corner_radius=8)
        frame_estado.grid(row=1, column=0, padx=10, pady=(5, 10), sticky="ew")
        frame_estado.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)

        self.lbl_fps = ctk.CTkLabel(frame_estado, text="FPS: ---",
                                    font=ctk.CTkFont(size=12, weight="bold"))
        self.lbl_fps.grid(row=0, column=0, padx=5, pady=5)

        self.lbl_latencia = ctk.CTkLabel(frame_estado, text="Latencia: --- ms",
                                         font=ctk.CTkFont(size=12))
        self.lbl_latencia.grid(row=0, column=1, padx=5, pady=5)

        self.lbl_mano = ctk.CTkLabel(frame_estado, text="Mano: ❌",
                                     font=ctk.CTkFont(size=12))
        self.lbl_mano.grid(row=0, column=2, padx=5, pady=5)

        self.lbl_gesto = ctk.CTkLabel(frame_estado, text="Gesto: ---",
                                      font=ctk.CTkFont(size=12))
        self.lbl_gesto.grid(row=0, column=3, padx=5, pady=5)

        self.lbl_accion = ctk.CTkLabel(frame_estado, text="Acción: ---",
                                       font=ctk.CTkFont(size=12))
        self.lbl_accion.grid(row=0, column=4, padx=5, pady=5)

        # ===== COLUMNA DERECHA: Controles y Calibración =====
        col_der = ctk.CTkScrollableFrame(self, corner_radius=10, label_text="Panel de Control")
        col_der.grid(row=0, column=1, padx=(5, 10), pady=10, sticky="nsew")
        col_der.grid_columnconfigure(0, weight=1)

        # --- Sección: Controles Principales ---
        self._crear_seccion_controles(col_der)

        # --- Sección: Calibración ---
        self._crear_seccion_calibracion(col_der)

        # --- Sección: Configuración ---
        self._crear_seccion_configuracion(col_der)

        # --- Botones de Acción ---
        frame_botones = ctk.CTkFrame(col_der, fg_color="transparent")
        frame_botones.grid(row=10, column=0, padx=10, pady=(15, 10), sticky="ew")
        frame_botones.grid_columnconfigure((0, 1), weight=1)

        self.btn_guardar = ctk.CTkButton(
            frame_botones, text="💾 Guardar", height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#28a745", hover_color="#218838",
            command=self._guardar_perfil
        )
        self.btn_guardar.grid(row=0, column=0, padx=(0, 5), sticky="ew")

        self.btn_restablecer = ctk.CTkButton(
            frame_botones, text="🔄 Restablecer", height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#6c757d", hover_color="#5a6268",
            command=self._restablecer_valores
        )
        self.btn_restablecer.grid(row=0, column=1, padx=(5, 0), sticky="ew")

    def _crear_seccion_controles(self, parent):
        """Sección de Start/Stop, Cámara y Modo Zurdo."""
        lbl = ctk.CTkLabel(parent, text="▶ Control del Tracking",
                           font=ctk.CTkFont(size=15, weight="bold"))
        lbl.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")

        # Botón Start / Stop
        self.btn_start = ctk.CTkButton(
            parent, text="▶  Iniciar Tracking", height=45,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#0d6efd", hover_color="#0b5ed7",
            command=self._toggle_tracking
        )
        self.btn_start.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

        # Info atajo
        lbl_atajo = ctk.CTkLabel(parent, text="⌨️ Ctrl+Alt+H → Pausar/Reanudar",
                                 font=ctk.CTkFont(size=11),
                                 text_color="gray")
        lbl_atajo.grid(row=2, column=0, padx=10, pady=(0, 5), sticky="w")

        # Selector de cámara
        lbl_cam = ctk.CTkLabel(parent, text="📷 Cámara:",
                               font=ctk.CTkFont(size=13))
        lbl_cam.grid(row=3, column=0, padx=10, pady=(10, 0), sticky="w")

        camaras_disponibles = self._detectar_camaras()
        self.combo_camara = ctk.CTkComboBox(
            parent, values=camaras_disponibles,
            state="readonly"
        )
        self.combo_camara.set(f"Cámara {self.perfil.id_camara}")
        self.combo_camara.grid(row=4, column=0, padx=10, pady=5, sticky="ew")

        # Modo zurdo/diestro
        self.var_zurdo = ctk.BooleanVar(value=self.perfil.es_zurdo)
        self.switch_zurdo = ctk.CTkSwitch(
            parent, text="🤚 Modo Zurdo",
            variable=self.var_zurdo,
            font=ctk.CTkFont(size=13),
            command=self._aplicar_configuracion_al_motor
        )
        self.switch_zurdo.grid(row=5, column=0, padx=10, pady=10, sticky="w")

    def _crear_seccion_calibracion(self, parent):
        """Sección de Bounding Box, Suavizado y Zona Muerta."""
        sep = ctk.CTkFrame(parent, height=2, fg_color="gray30")
        sep.grid(row=6, column=0, padx=10, pady=5, sticky="ew")

        lbl = ctk.CTkLabel(parent, text="🎯 Calibración",
                           font=ctk.CTkFont(size=15, weight="bold"))
        lbl.grid(row=7, column=0, padx=10, pady=(10, 5), sticky="w")

        frame_cal = ctk.CTkFrame(parent, corner_radius=8)
        frame_cal.grid(row=8, column=0, padx=5, pady=5, sticky="ew")
        frame_cal.grid_columnconfigure(0, weight=1)

        # --- Zona Activa (Bounding Box) ---
        lbl_bb = ctk.CTkLabel(frame_cal, text="📐 Zona Activa (Bounding Box)",
                              font=ctk.CTkFont(size=13, weight="bold"))
        lbl_bb.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")

        # X Min
        self.lbl_xmin_val = ctk.CTkLabel(frame_cal, text=f"X Mín: {self.perfil.zona_activa_x_min:.2f}")
        self.lbl_xmin_val.grid(row=1, column=0, padx=10, sticky="w")
        self.slider_xmin = ctk.CTkSlider(
            frame_cal, from_=0.05, to=0.45,
            command=lambda v: (
                self.lbl_xmin_val.configure(text=f"X Mín: {v:.2f}"),
                self._aplicar_configuracion_al_motor()
            )
        )
        self.slider_xmin.set(self.perfil.zona_activa_x_min)
        self.slider_xmin.grid(row=2, column=0, padx=10, pady=(0, 5), sticky="ew")

        # X Max
        self.lbl_xmax_val = ctk.CTkLabel(frame_cal, text=f"X Máx: {self.perfil.zona_activa_x_max:.2f}")
        self.lbl_xmax_val.grid(row=3, column=0, padx=10, sticky="w")
        self.slider_xmax = ctk.CTkSlider(
            frame_cal, from_=0.55, to=0.95,
            command=lambda v: (
                self.lbl_xmax_val.configure(text=f"X Máx: {v:.2f}"),
                self._aplicar_configuracion_al_motor()
            )
        )
        self.slider_xmax.set(self.perfil.zona_activa_x_max)
        self.slider_xmax.grid(row=4, column=0, padx=10, pady=(0, 5), sticky="ew")

        # Y Min
        self.lbl_ymin_val = ctk.CTkLabel(frame_cal, text=f"Y Mín: {self.perfil.zona_activa_y_min:.2f}")
        self.lbl_ymin_val.grid(row=5, column=0, padx=10, sticky="w")
        self.slider_ymin = ctk.CTkSlider(
            frame_cal, from_=0.05, to=0.45,
            command=lambda v: (
                self.lbl_ymin_val.configure(text=f"Y Mín: {v:.2f}"),
                self._aplicar_configuracion_al_motor()
            )
        )
        self.slider_ymin.set(self.perfil.zona_activa_y_min)
        self.slider_ymin.grid(row=6, column=0, padx=10, pady=(0, 5), sticky="ew")

        # Y Max
        self.lbl_ymax_val = ctk.CTkLabel(frame_cal, text=f"Y Máx: {self.perfil.zona_activa_y_max:.2f}")
        self.lbl_ymax_val.grid(row=7, column=0, padx=10, sticky="w")
        self.slider_ymax = ctk.CTkSlider(
            frame_cal, from_=0.55, to=0.95,
            command=lambda v: (
                self.lbl_ymax_val.configure(text=f"Y Máx: {v:.2f}"),
                self._aplicar_configuracion_al_motor()
            )
        )
        self.slider_ymax.set(self.perfil.zona_activa_y_max)
        self.slider_ymax.grid(row=8, column=0, padx=10, pady=(0, 10), sticky="ew")

        # --- Suavizado (Alpha EMA) ---
        sep2 = ctk.CTkFrame(frame_cal, height=1, fg_color="gray40")
        sep2.grid(row=9, column=0, padx=10, pady=5, sticky="ew")

        lbl_suav = ctk.CTkLabel(frame_cal, text="🧹 Suavizado (Estabilidad ↔ Velocidad)",
                                font=ctk.CTkFont(size=13, weight="bold"))
        lbl_suav.grid(row=10, column=0, padx=10, pady=(5, 0), sticky="w")

        self.lbl_suav_val = ctk.CTkLabel(frame_cal, text=f"Alpha: {self.perfil.suavizado_factor:.2f}")
        self.lbl_suav_val.grid(row=11, column=0, padx=10, sticky="w")
        self.slider_suavizado = ctk.CTkSlider(
            frame_cal, from_=0.1, to=1.0,
            command=lambda v: (
                self.lbl_suav_val.configure(text=f"Alpha: {v:.2f}"),
                self._aplicar_configuracion_al_motor()
            )
        )
        self.slider_suavizado.set(self.perfil.suavizado_factor)
        self.slider_suavizado.grid(row=12, column=0, padx=10, pady=(0, 5), sticky="ew")

        # Etiquetas explicativas
        frame_etiq = ctk.CTkFrame(frame_cal, fg_color="transparent")
        frame_etiq.grid(row=13, column=0, padx=10, sticky="ew")
        frame_etiq.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkLabel(frame_etiq, text="← Más estable", text_color="gray",
                     font=ctk.CTkFont(size=10)).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(frame_etiq, text="Más rápido →", text_color="gray",
                     font=ctk.CTkFont(size=10)).grid(row=0, column=1, sticky="e")

        # --- Zona Muerta ---
        sep3 = ctk.CTkFrame(frame_cal, height=1, fg_color="gray40")
        sep3.grid(row=14, column=0, padx=10, pady=5, sticky="ew")

        lbl_zm = ctk.CTkLabel(frame_cal, text="🎯 Zona Muerta (Precisión)",
                              font=ctk.CTkFont(size=13, weight="bold"))
        lbl_zm.grid(row=15, column=0, padx=10, pady=(5, 0), sticky="w")

        self.lbl_zm_val = ctk.CTkLabel(frame_cal, text=f"Umbral: {self.perfil.zona_muerta_px} px")
        self.lbl_zm_val.grid(row=16, column=0, padx=10, sticky="w")
        self.slider_zona_muerta = ctk.CTkSlider(
            frame_cal, from_=0, to=10, number_of_steps=10,
            command=lambda v: (
                self.lbl_zm_val.configure(text=f"Umbral: {int(v)} px"),
                self._aplicar_configuracion_al_motor()
            )
        )
        self.slider_zona_muerta.set(self.perfil.zona_muerta_px)
        self.slider_zona_muerta.grid(row=17, column=0, padx=10, pady=(0, 10), sticky="ew")

    def _crear_seccion_configuracion(self, parent):
        """Sección del Editor de Gestos: tabla Gesto → Acción y umbral de pellizco."""
        sep = ctk.CTkFrame(parent, height=2, fg_color="gray30")
        sep.grid(row=9, column=0, padx=10, pady=5, sticky="ew")

        lbl = ctk.CTkLabel(parent, text="🖐️ Mapeo de Gestos",
                           font=ctk.CTkFont(size=15, weight="bold"))
        lbl.grid(row=10, column=0, padx=10, pady=(10, 5), sticky="w")

        frame_gestos = ctk.CTkFrame(parent, corner_radius=8)
        frame_gestos.grid(row=11, column=0, padx=5, pady=5, sticky="ew")
        frame_gestos.grid_columnconfigure(1, weight=1)

        # Acciones disponibles para asignar a cada gesto
        acciones_disponibles = [
            "MOVER_CURSOR", "CLIC_IZQUIERDO", "CLIC_DERECHO",
            "DRAG_AND_DROP", "SCROLL", "NINGUNA"
        ]

        # Lista ordenada de gestos estándar
        gestos_orden = [
            ("MANO_ABIERTA", "🖐️ Mano Abierta", "MOVER_CURSOR"),
            ("PELLIZCO_INDICE", "🤏 Pellizco Índice", "CLIC_IZQUIERDO"),
            ("PELLIZCO_MEDIO", "🤏 Pellizco Medio", "CLIC_DERECHO"),
            ("PELLIZCO_TRIPLE", "🤌 Pellizco Triple", "DRAG_AND_DROP"),
            ("DOS_DEDOS", "✌️ Dos Dedos", "SCROLL"),
        ]

        mapeo_existente = {g.nombre_gesto: g.accion_sistema for g in self.perfil.gestos}
        self.dropdowns_gestos = {}  # {nombre_gesto: CTkOptionMenu}

        for fila, (nombre_gesto, nombre_label, accion_def) in enumerate(gestos_orden):
            lbl_gesto = ctk.CTkLabel(frame_gestos, text=nombre_label,
                                     font=ctk.CTkFont(size=12))
            lbl_gesto.grid(row=fila, column=0, padx=(10, 5), pady=4, sticky="w")

            dropdown = ctk.CTkOptionMenu(
                frame_gestos, values=acciones_disponibles,
                font=ctk.CTkFont(size=11),
                width=160,
                command=lambda _: self._aplicar_configuracion_al_motor()
            )
            dropdown.set(mapeo_existente.get(nombre_gesto, accion_def))
            dropdown.grid(row=fila, column=1, padx=(5, 10), pady=4, sticky="ew")

            self.dropdowns_gestos[nombre_gesto] = dropdown

        cant_gestos = len(gestos_orden)

        # --- Umbral de Pellizco ---
        sep2 = ctk.CTkFrame(frame_gestos, height=1, fg_color="gray40")
        sep2.grid(row=cant_gestos, column=0, columnspan=2,
                  padx=10, pady=5, sticky="ew")

        lbl_umbral = ctk.CTkLabel(frame_gestos, text="🎯 Umbral de Pellizco",
                                  font=ctk.CTkFont(size=13, weight="bold"))
        lbl_umbral.grid(row=cant_gestos + 1, column=0, columnspan=2,
                        padx=10, pady=(5, 0), sticky="w")

        umbral_actual = getattr(self.perfil, 'umbral_pellizco', 0.06)
        self.lbl_umbral_val = ctk.CTkLabel(
            frame_gestos, text=f"Distancia: {umbral_actual:.2f}"
        )
        self.lbl_umbral_val.grid(row=cant_gestos + 2, column=0,
                                 columnspan=2, padx=10, sticky="w")

        self.slider_umbral = ctk.CTkSlider(
            frame_gestos, from_=0.02, to=0.12,
            command=lambda v: (
                self.lbl_umbral_val.configure(text=f"Distancia: {v:.2f}"),
                self._aplicar_configuracion_al_motor()
            )
        )
        self.slider_umbral.set(umbral_actual)
        self.slider_umbral.grid(row=cant_gestos + 3, column=0,
                                columnspan=2, padx=10, pady=(0, 3), sticky="ew")

        # Etiquetas explicativas
        frame_etiq_umb = ctk.CTkFrame(frame_gestos, fg_color="transparent")
        frame_etiq_umb.grid(row=cant_gestos + 4, column=0,
                            columnspan=2, padx=10, sticky="ew")
        frame_etiq_umb.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkLabel(frame_etiq_umb, text="← Más estricto", text_color="gray",
                     font=ctk.CTkFont(size=10)).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(frame_etiq_umb, text="Más tolerante →", text_color="gray",
                     font=ctk.CTkFont(size=10)).grid(row=0, column=1, sticky="e")

        # --- Botón Restaurar Gestos ---
        self.btn_restaurar_gestos = ctk.CTkButton(
            frame_gestos, text="🔄 Restaurar Gestos por Defecto", height=32,
            font=ctk.CTkFont(size=12),
            fg_color="#6c757d", hover_color="#5a6268",
            command=self._restaurar_gestos
        )
        self.btn_restaurar_gestos.grid(row=cant_gestos + 5, column=0,
                                       columnspan=2, padx=10, pady=(8, 10), sticky="ew")

        # Info
        lbl_info = ctk.CTkLabel(
            parent,
            text="ℹ️ Los cambios se aplican al guardar el perfil.",
            font=ctk.CTkFont(size=11),
            text_color="gray",
            justify="left"
        )
        lbl_info.grid(row=12, column=0, padx=10, pady=(5, 5), sticky="w")

    # =========================================================================
    # LÓGICA DE CONTROL
    # =========================================================================

    def _toggle_tracking(self):
        """Inicia o detiene el tracking."""
        if not self.tracking_activo:
            self._iniciar_tracking()
        else:
            self._detener_tracking()

    def _iniciar_tracking(self):
        """Crea el motor y lo lanza en un Thread."""
        self.motor = MotorHandTracking()

        # Aplicar configuración de la UI al motor antes de iniciar
        self._aplicar_configuracion_al_motor()

        self.hilo_motor = threading.Thread(target=self.motor.iniciar, daemon=True)
        self.hilo_motor.start()

        self.tracking_activo = True
        self.btn_start.configure(
            text="⏹  Detener Tracking",
            fg_color="#dc3545", hover_color="#c82333"
        )

        # Si ya estaba minimizada (raro, pero posible) abrir PiP
        if self.state() == "iconic" and self.pip_window is None:
            self.pip_window = WidgetFlotante(self, self._restaurar_desde_pip)

    def _detener_tracking(self):
        """Detiene el motor y el thread."""
        if self.motor:
            self.motor.ejecutando = False
            if self.hilo_motor and self.hilo_motor.is_alive():
                self.hilo_motor.join(timeout=2)
            self.motor = None

        self.tracking_activo = False
        self.label_preview.configure(image=None, text="Cámara no iniciada")
        self.btn_start.configure(
            text="▶  Iniciar Tracking",
            fg_color="#0d6efd", hover_color="#0b5ed7"
        )
        
        # Cerrar PiP si estaba abierto
        self._cerrar_pip()

        # Resetear estado
        self.lbl_fps.configure(text="FPS: ---")
        self.lbl_latencia.configure(text="Latencia: --- ms")
        self.lbl_mano.configure(text="Mano: ❌")
        self.lbl_gesto.configure(text="Gesto: ---")
        self.lbl_accion.configure(text="Acción: ---")

    def _alternar_pausa_global(self):
        """Callback del atajo global Ctrl+Alt+H."""
        if self.motor and self.tracking_activo:
            self.motor.alternar_pausa()

    def _aplicar_configuracion_al_motor(self):
        """Aplica los valores actuales de los sliders y gestos al motor en tiempo real."""
        if self.motor:
            self.motor.filtro.set_alpha(self.slider_suavizado.get())
            self.motor.zona_x_min = self.slider_xmin.get()
            self.motor.zona_x_max = self.slider_xmax.get()
            self.motor.zona_y_min = self.slider_ymin.get()
            self.motor.zona_y_max = self.slider_ymax.get()
            self.motor.controlador_mouse.set_zona_muerta(int(self.slider_zona_muerta.get()))
            self.motor.es_zurdo = self.var_zurdo.get()
            self.motor.umbral_pellizco = self.slider_umbral.get()

            # Mapeo de gestos en tiempo real
            nuevo_mapeo = {}
            for nombre_gesto, dropdown in self.dropdowns_gestos.items():
                accion = dropdown.get()
                if accion != "NINGUNA":
                    nuevo_mapeo[nombre_gesto] = accion
            self.motor.mapeo_gestos = nuevo_mapeo

    def _guardar_perfil(self):
        """Guarda la configuración actual asincronamente."""
        texto_camara = self.combo_camara.get()
        id_camara = int(texto_camara.split(" ")[-1]) if texto_camara else 0

        # Mapeo completo de gestos
        mapeo_dict = {nombre: dropdown.get() for nombre, dropdown in self.dropdowns_gestos.items()}
        
        # Guardado asíncrono
        def operacion_db():
            guardar_perfil(
                id_perfil=self.perfil.id,
                nombre=self.perfil.nombre,
                suavizado=self.slider_suavizado.get(),
                x_min=self.slider_xmin.get(),
                y_min=self.slider_ymin.get(),
                x_max=self.slider_xmax.get(),
                y_max=self.slider_ymax.get(),
                zona_muerta_px=int(self.slider_zona_muerta.get()),
                es_zurdo=self.var_zurdo.get(),
                id_camara=id_camara,
                umbral_pellizco=self.slider_umbral.get()
            )
            guardar_mapeo_completo_gestos(self.perfil.id, mapeo_dict)
            
            # Feedback visual (vuelve al Hilo Principal via .after())
            self.after(0, lambda: self.btn_guardar.configure(text="✅ Guardado!", fg_color="#218838"))
            self.after(2000, lambda: self.btn_guardar.configure(text="💾 Guardar", fg_color="#28a745"))

        self.btn_guardar.configure(text="⏳ Guardando...", fg_color="#ffc107")
        self.executor.submit(operacion_db)

        # Aplicar al motor inmediatamente
        self._aplicar_configuracion_al_motor()

    def _restablecer_valores(self):
        """Restablece todos los parámetros a sus valores predeterminados de fábrica."""
        # Valores por defecto
        val_xmin = 0.20
        val_xmax = 0.80
        val_ymin = 0.20
        val_ymax = 0.80
        val_alpha = 0.50
        val_zm = 3
        val_zurdo = False
        val_cam = 0
        val_umbral = 0.06

        # Actualizar sliders y etiquetas
        self.slider_xmin.set(val_xmin)
        self.lbl_xmin_val.configure(text=f"X Mín: {val_xmin:.2f}")

        self.slider_xmax.set(val_xmax)
        self.lbl_xmax_val.configure(text=f"X Máx: {val_xmax:.2f}")

        self.slider_ymin.set(val_ymin)
        self.lbl_ymin_val.configure(text=f"Y Mín: {val_ymin:.2f}")

        self.slider_ymax.set(val_ymax)
        self.lbl_ymax_val.configure(text=f"Y Máx: {val_ymax:.2f}")

        self.slider_suavizado.set(val_alpha)
        self.lbl_suav_val.configure(text=f"Alpha: {val_alpha:.2f}")

        self.slider_zona_muerta.set(val_zm)
        self.lbl_zm_val.configure(text=f"Umbral: {val_zm} px")

        self.slider_umbral.set(val_umbral)
        self.lbl_umbral_val.configure(text=f"Distancia: {val_umbral:.2f}")

        self.var_zurdo.set(val_zurdo)
        self.combo_camara.set(f"Cámara {val_cam}")

        # Guardar en base de datos asincronamente
        def operacion_db():
            guardar_perfil(
                id_perfil=self.perfil.id,
                nombre=self.perfil.nombre,
                suavizado=val_alpha,
                x_min=val_xmin,
                y_min=val_ymin,
                x_max=val_xmax,
                y_max=val_ymax,
                zona_muerta_px=val_zm,
                es_zurdo=val_zurdo,
                id_camara=val_cam,
                umbral_pellizco=val_umbral
            )
            # Feedback visual
            self.after(0, lambda: self.btn_restablecer.configure(text="✅ Restablecido!", fg_color="#5a6268"))
            self.after(2000, lambda: self.btn_restablecer.configure(text="🔄 Restablecer", fg_color="#6c757d"))

        self.btn_restablecer.configure(text="⏳ Restableciendo...", fg_color="#ffc107")
        self.executor.submit(operacion_db)

        # Aplicar al motor si está corriendo
        self._aplicar_configuracion_al_motor()

        # Restaurar gestos también
        self._restaurar_gestos(silencioso=True)

    def _restaurar_gestos(self, silencioso=False):
        """Restaura los gestos a los valores predeterminados de fábrica asincronamente."""
        gestos_default = {
            "MANO_ABIERTA": "MOVER_CURSOR",
            "PELLIZCO_INDICE": "CLIC_IZQUIERDO",
            "PELLIZCO_MEDIO": "CLIC_DERECHO",
            "PELLIZCO_TRIPLE": "DRAG_AND_DROP",
            "DOS_DEDOS": "SCROLL",
        }

        for nombre_gesto, accion in gestos_default.items():
            if nombre_gesto in self.dropdowns_gestos:
                self.dropdowns_gestos[nombre_gesto].set(accion)

        def operacion_db():
            guardar_mapeo_completo_gestos(self.perfil.id, gestos_default)
            if not silencioso:
                self.after(0, lambda: self.btn_restaurar_gestos.configure(text="✅ Restaurados!", fg_color="#5a6268"))
                self.after(2000, lambda: self.btn_restaurar_gestos.configure(text="🔄 Restaurar Gestos por Defecto", fg_color="#6c757d"))

        if not silencioso:
            self.btn_restaurar_gestos.configure(text="⏳ Restaurando...", fg_color="#ffc107")
            
        self.executor.submit(operacion_db)
        self._aplicar_configuracion_al_motor()

    # =========================================================================
    # ACTUALIZACIÓN DE PREVIEW Y ESTADO
    # =========================================================================

    def _actualizar_preview(self):
        """Actualiza la preview de cámara y el estado en vivo consumiendo la cola de eventos."""
        if self.motor and self.tracking_activo:
            try:
                estado = self.motor.cola_estado.get_nowait()
                frame = estado["frame"]
                
                # Convertir BGR (OpenCV) → RGB (Pillow) → ImageTk
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                imagen = Image.fromarray(frame_rgb)

                # Si hay ventana flotante (PiP), redimensionar para ella
                if self.pip_window is not None:
                    lbl_w = self.pip_window.winfo_width()
                    lbl_h = self.pip_window.winfo_height()
                else:
                    lbl_w = self.label_preview.winfo_width()
                    lbl_h = self.label_preview.winfo_height()

                if lbl_w > 1 and lbl_h > 1:
                    img_w, img_h = imagen.size
                    ratio = min(lbl_w / img_w, lbl_h / img_h)
                    nuevo_w = max(1, int(img_w * ratio))
                    nuevo_h = max(1, int(img_h * ratio))
                else:
                    nuevo_w, nuevo_h = (640, 480)

                ctk_foto = ctk.CTkImage(light_image=imagen, dark_image=imagen, size=(nuevo_w, nuevo_h))
                
                # Renderizar donde corresponda
                if self.pip_window is not None:
                    self.pip_window.actualizar_imagen(ctk_foto)
                else:
                    self.label_preview.configure(image=ctk_foto, text="")
                    self.label_preview._imagen = ctk_foto  # Mantener referencia

                # Actualizar indicadores de estado
                self.lbl_fps.configure(text=f"FPS: {estado['fps']:.1f}")
                self.lbl_latencia.configure(text=f"Latencia: {estado['latencia']:.0f} ms")

                if estado["mano_detectada"]:
                    self.lbl_mano.configure(text="Mano: ✅", text_color="#28a745")
                else:
                    self.lbl_mano.configure(text="Mano: ❌", text_color="#dc3545")

                self.lbl_gesto.configure(text=f"Gesto: {estado['gesto']}")
                self.lbl_accion.configure(text=f"Acción: {estado['accion']}")

            except queue.Empty:
                pass  # No hay frames nuevos
            except Exception as e:
                print(f"[UI] Error actualizando preview: {e}")

        # Programar siguiente actualización (~30fps)
        self.after(33, self._actualizar_preview)

    # =========================================================================
    # UTILIDADES
    # =========================================================================

    def _detectar_camaras(self, max_camaras=5):
        """Detecta cámaras disponibles probando índices de OpenCV."""
        camaras = []
        for i in range(max_camaras):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                camaras.append(f"Cámara {i}")
                cap.release()
        if not camaras:
            camaras = ["Cámara 0"]  # Fallback
        return camaras

    def _al_cerrar(self):
        """Limpieza al cerrar la ventana."""
        self._detener_tracking()
        self.executor.shutdown(wait=False)
        keyboard.unhook_all()
        self.destroy()
