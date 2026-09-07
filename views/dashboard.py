"""
Dashboard Principal del Sistema HandTracking.
Interfaz gráfica construida con CustomTkinter que permite al usuario:
- Iniciar/detener el tracking de mano.
- Ver la preview de la cámara con landmarks en vivo.
- Monitorear estado en tiempo real (FPS, latencia, gesto detectado).
- Calibrar mediante un asistente guiado.
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
from views.calibracion_wizard import AsistenteCalibracion


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

        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
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

        self.lbl_fps = ctk.CTkLabel(frame_estado, text="FPS: ---", font=ctk.CTkFont(size=12, weight="bold"))
        self.lbl_fps.grid(row=0, column=0, padx=5, pady=5)
        self.lbl_latencia = ctk.CTkLabel(frame_estado, text="Latencia: --- ms", font=ctk.CTkFont(size=12))
        self.lbl_latencia.grid(row=0, column=1, padx=5, pady=5)
        self.lbl_mano = ctk.CTkLabel(frame_estado, text="Mano: ❌", font=ctk.CTkFont(size=12))
        self.lbl_mano.grid(row=0, column=2, padx=5, pady=5)
        self.lbl_gesto = ctk.CTkLabel(frame_estado, text="Gesto: ---", font=ctk.CTkFont(size=12))
        self.lbl_gesto.grid(row=0, column=3, padx=5, pady=5)
        self.lbl_accion = ctk.CTkLabel(frame_estado, text="Acción: ---", font=ctk.CTkFont(size=12))
        self.lbl_accion.grid(row=0, column=4, padx=5, pady=5)

        # ===== COLUMNA DERECHA: Controles y Calibración =====
        col_der = ctk.CTkScrollableFrame(self, corner_radius=10, label_text="Panel de Control")
        col_der.grid(row=0, column=1, padx=(5, 10), pady=10, sticky="nsew")
        col_der.grid_columnconfigure(0, weight=1)

        self._crear_seccion_controles(col_der)
        self._crear_seccion_calibracion(col_der)
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
        lbl = ctk.CTkLabel(parent, text="▶ Control del Tracking", font=ctk.CTkFont(size=15, weight="bold"))
        lbl.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")

        self.btn_start = ctk.CTkButton(
            parent, text="▶  Iniciar Tracking", height=45,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#0d6efd", hover_color="#0b5ed7",
            command=self._toggle_tracking
        )
        self.btn_start.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

        lbl_atajo = ctk.CTkLabel(parent, text="⌨️ Ctrl+Alt+H → Pausar/Reanudar", font=ctk.CTkFont(size=11), text_color="gray")
        lbl_atajo.grid(row=2, column=0, padx=10, pady=(0, 5), sticky="w")

        lbl_cam = ctk.CTkLabel(parent, text="📷 Cámara:", font=ctk.CTkFont(size=13))
        lbl_cam.grid(row=3, column=0, padx=10, pady=(10, 0), sticky="w")

        camaras_disponibles = self._detectar_camaras()
        self.combo_camara = ctk.CTkComboBox(parent, values=camaras_disponibles, state="readonly")
        self.combo_camara.set(f"Cámara {self.perfil.id_camara}")
        self.combo_camara.grid(row=4, column=0, padx=10, pady=5, sticky="ew")

        self.var_zurdo = ctk.BooleanVar(value=self.perfil.es_zurdo)
        self.switch_zurdo = ctk.CTkSwitch(
            parent, text="🤚 Modo Zurdo", variable=self.var_zurdo,
            font=ctk.CTkFont(size=13), command=self._aplicar_configuracion_al_motor
        )
        self.switch_zurdo.grid(row=5, column=0, padx=10, pady=10, sticky="w")

    def _crear_seccion_calibracion(self, parent):
        """Sección de Calibración, ahora delegada al Asistente (Wizard)."""
        sep = ctk.CTkFrame(parent, height=2, fg_color="gray30")
        sep.grid(row=6, column=0, padx=10, pady=5, sticky="ew")

        lbl = ctk.CTkLabel(parent, text="🎯 Calibración", font=ctk.CTkFont(size=15, weight="bold"))
        lbl.grid(row=7, column=0, padx=10, pady=(10, 5), sticky="w")

        frame_cal = ctk.CTkFrame(parent, corner_radius=8)
        frame_cal.grid(row=8, column=0, padx=5, pady=5, sticky="ew")
        frame_cal.grid_columnconfigure(0, weight=1)
        
        lbl_info = ctk.CTkLabel(frame_cal, text="Ajusta el rango de movimiento y la sensibilidad\nde forma guiada y visual.", text_color="gray", font=ctk.CTkFont(size=11))
        lbl_info.grid(row=0, column=0, padx=10, pady=(10, 5))

        btn_wizard = ctk.CTkButton(
            frame_cal, text="🪄 Iniciar Calibración Guiada", height=35,
            font=ctk.CTkFont(weight="bold"),
            command=self._abrir_wizard
        )
        btn_wizard.grid(row=1, column=0, padx=10, pady=(5, 10), sticky="ew")

    def _abrir_wizard(self):
        """Abre el asistente paso a paso de calibración."""
        wizard = AsistenteCalibracion(self)
        
    def _crear_seccion_configuracion(self, parent):
        """Sección del Editor de Gestos y umbral de pellizco."""
        sep = ctk.CTkFrame(parent, height=2, fg_color="gray30")
        sep.grid(row=9, column=0, padx=10, pady=5, sticky="ew")

        lbl = ctk.CTkLabel(parent, text="🖐️ Mapeo de Gestos", font=ctk.CTkFont(size=15, weight="bold"))
        lbl.grid(row=10, column=0, padx=10, pady=(10, 5), sticky="w")

        frame_gestos = ctk.CTkFrame(parent, corner_radius=8)
        frame_gestos.grid(row=11, column=0, padx=5, pady=5, sticky="ew")
        frame_gestos.grid_columnconfigure(1, weight=1)

        acciones_disponibles = ["MOVER_CURSOR", "CLIC_IZQUIERDO", "CLIC_DERECHO", "DRAG_AND_DROP", "SCROLL", "NINGUNA"]
        gestos_orden = [
            ("MANO_ABIERTA", "🖐️ Mano Abierta", "MOVER_CURSOR"),
            ("PELLIZCO_INDICE", "🤏 Pellizco Índice", "CLIC_IZQUIERDO"),
            ("PELLIZCO_MEDIO", "🤏 Pellizco Medio", "CLIC_DERECHO"),
            ("PELLIZCO_TRIPLE", "🤌 Pellizco Triple", "DRAG_AND_DROP"),
            ("DOS_DEDOS", "✌️ Dos Dedos", "SCROLL"),
        ]

        mapeo_existente = {g.nombre_gesto: g.accion_sistema for g in self.perfil.gestos}
        self.dropdowns_gestos = {}

        for fila, (nombre_gesto, nombre_label, accion_def) in enumerate(gestos_orden):
            lbl_gesto = ctk.CTkLabel(frame_gestos, text=nombre_label, font=ctk.CTkFont(size=12))
            lbl_gesto.grid(row=fila, column=0, padx=(10, 5), pady=4, sticky="w")

            dropdown = ctk.CTkOptionMenu(
                frame_gestos, values=acciones_disponibles,
                font=ctk.CTkFont(size=11), width=160,
                command=lambda _: self._aplicar_configuracion_al_motor()
            )
            dropdown.set(mapeo_existente.get(nombre_gesto, accion_def))
            dropdown.grid(row=fila, column=1, padx=(5, 10), pady=4, sticky="ew")

            self.dropdowns_gestos[nombre_gesto] = dropdown

        cant_gestos = len(gestos_orden)

        sep2 = ctk.CTkFrame(frame_gestos, height=1, fg_color="gray40")
        sep2.grid(row=cant_gestos, column=0, columnspan=2, padx=10, pady=5, sticky="ew")

        lbl_umbral = ctk.CTkLabel(frame_gestos, text="🎯 Umbral de Pellizco", font=ctk.CTkFont(size=13, weight="bold"))
        lbl_umbral.grid(row=cant_gestos + 1, column=0, columnspan=2, padx=10, pady=(5, 0), sticky="w")

        umbral_actual = getattr(self.perfil, 'umbral_pellizco', 0.06)
        self.lbl_umbral_val = ctk.CTkLabel(frame_gestos, text=f"Distancia: {umbral_actual:.2f}")
        self.lbl_umbral_val.grid(row=cant_gestos + 2, column=0, columnspan=2, padx=10, sticky="w")

        self.slider_umbral = ctk.CTkSlider(
            frame_gestos, from_=0.02, to=0.12,
            command=lambda v: (
                self.lbl_umbral_val.configure(text=f"Distancia: {v:.2f}"),
                self._aplicar_configuracion_al_motor()
            )
        )
        self.slider_umbral.set(umbral_actual)
        self.slider_umbral.grid(row=cant_gestos + 3, column=0, columnspan=2, padx=10, pady=(0, 3), sticky="ew")

        frame_etiq_umb = ctk.CTkFrame(frame_gestos, fg_color="transparent")
        frame_etiq_umb.grid(row=cant_gestos + 4, column=0, columnspan=2, padx=10, sticky="ew")
        frame_etiq_umb.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkLabel(frame_etiq_umb, text="← Más estricto", text_color="gray", font=ctk.CTkFont(size=10)).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(frame_etiq_umb, text="Más tolerante →", text_color="gray", font=ctk.CTkFont(size=10)).grid(row=0, column=1, sticky="e")

        self.btn_restaurar_gestos = ctk.CTkButton(
            frame_gestos, text="🔄 Restaurar Gestos por Defecto", height=32,
            font=ctk.CTkFont(size=12), fg_color="#6c757d", hover_color="#5a6268",
            command=self._restaurar_gestos
        )
        self.btn_restaurar_gestos.grid(row=cant_gestos + 5, column=0, columnspan=2, padx=10, pady=(8, 10), sticky="ew")

        lbl_info = ctk.CTkLabel(parent, text="ℹ️ Los cambios se aplican al guardar el perfil.", font=ctk.CTkFont(size=11), text_color="gray", justify="left")
        lbl_info.grid(row=12, column=0, padx=10, pady=(5, 5), sticky="w")

    # =========================================================================
    # LÓGICA DE CONTROL
    # =========================================================================

    def _toggle_tracking(self):
        if not self.tracking_activo:
            self._iniciar_tracking()
        else:
            self._detener_tracking()

    def _iniciar_tracking(self):
        self.motor = MotorHandTracking()
        self._aplicar_configuracion_al_motor()
        self.hilo_motor = threading.Thread(target=self.motor.iniciar, daemon=True)
        self.hilo_motor.start()

        self.tracking_activo = True
        self.btn_start.configure(text="⏹  Detener Tracking", fg_color="#dc3545", hover_color="#c82333")

        if self.state() == "iconic" and self.pip_window is None:
            self.pip_window = WidgetFlotante(self, self._restaurar_desde_pip)

    def _detener_tracking(self):
        if self.motor:
            self.motor.ejecutando = False
            if self.hilo_motor and self.hilo_motor.is_alive():
                self.hilo_motor.join(timeout=2)
            self.motor = None

        self.tracking_activo = False
        self.label_preview.configure(image=None, text="Cámara no iniciada")
        self.btn_start.configure(text="▶  Iniciar Tracking", fg_color="#0d6efd", hover_color="#0b5ed7")
        
        self._cerrar_pip()

        self.lbl_fps.configure(text="FPS: ---")
        self.lbl_latencia.configure(text="Latencia: --- ms")
        self.lbl_mano.configure(text="Mano: ❌")
        self.lbl_gesto.configure(text="Gesto: ---")
        self.lbl_accion.configure(text="Acción: ---")

    def _alternar_pausa_global(self):
        if self.motor and self.tracking_activo:
            self.motor.alternar_pausa()

    def _aplicar_configuracion_al_motor(self):
        if self.motor:
            # Ahora toma los valores directo del perfil (modificado por el Wizard)
            self.motor.filtro.set_alpha(self.perfil.suavizado_factor)
            self.motor.zona_x_min = self.perfil.zona_activa_x_min
            self.motor.zona_x_max = self.perfil.zona_activa_x_max
            self.motor.zona_y_min = self.perfil.zona_activa_y_min
            self.motor.zona_y_max = self.perfil.zona_activa_y_max
            self.motor.controlador_mouse.set_zona_muerta(self.perfil.zona_muerta_px)
            
            # Variables de la UI
            self.motor.es_zurdo = self.var_zurdo.get()
            self.motor.umbral_pellizco = self.slider_umbral.get()

            nuevo_mapeo = {}
            for nombre_gesto, dropdown in self.dropdowns_gestos.items():
                accion = dropdown.get()
                if accion != "NINGUNA":
                    nuevo_mapeo[nombre_gesto] = accion
            self.motor.mapeo_gestos = nuevo_mapeo

    def _guardar_perfil(self):
        texto_camara = self.combo_camara.get()
        id_camara = int(texto_camara.split(" ")[-1]) if texto_camara else 0

        mapeo_dict = {nombre: dropdown.get() for nombre, dropdown in self.dropdowns_gestos.items()}
        
        def operacion_db():
            guardar_perfil(
                id_perfil=self.perfil.id,
                nombre=self.perfil.nombre,
                suavizado=self.perfil.suavizado_factor,
                x_min=self.perfil.zona_activa_x_min,
                y_min=self.perfil.zona_activa_y_min,
                x_max=self.perfil.zona_activa_x_max,
                y_max=self.perfil.zona_activa_y_max,
                zona_muerta_px=self.perfil.zona_muerta_px,
                es_zurdo=self.var_zurdo.get(),
                id_camara=id_camara,
                umbral_pellizco=self.slider_umbral.get()
            )
            guardar_mapeo_completo_gestos(self.perfil.id, mapeo_dict)
            
            self.after(0, lambda: self.btn_guardar.configure(text="✅ Guardado!", fg_color="#218838"))
            self.after(2000, lambda: self.btn_guardar.configure(text="💾 Guardar", fg_color="#28a745"))

        self.btn_guardar.configure(text="⏳ Guardando...", fg_color="#ffc107")
        self.executor.submit(operacion_db)
        self._aplicar_configuracion_al_motor()

    def _restablecer_valores(self):
        # Actualizar valores del perfil
        self.perfil.zona_activa_x_min = 0.20
        self.perfil.zona_activa_x_max = 0.80
        self.perfil.zona_activa_y_min = 0.20
        self.perfil.zona_activa_y_max = 0.80
        self.perfil.suavizado_factor = 0.50
        self.perfil.zona_muerta_px = 3
        
        # UI update (solo los que quedaron en la UI)
        self.var_zurdo.set(False)
        self.combo_camara.set(f"Cámara 0")
        self.slider_umbral.set(0.06)
        self.lbl_umbral_val.configure(text=f"Distancia: 0.06")

        def operacion_db():
            guardar_perfil(
                id_perfil=self.perfil.id,
                nombre=self.perfil.nombre,
                suavizado=0.50,
                x_min=0.20,
                y_min=0.20,
                x_max=0.80,
                y_max=0.80,
                zona_muerta_px=3,
                es_zurdo=False,
                id_camara=0,
                umbral_pellizco=0.06
            )
            self.after(0, lambda: self.btn_restablecer.configure(text="✅ Restablecido!", fg_color="#5a6268"))
            self.after(2000, lambda: self.btn_restablecer.configure(text="🔄 Restablecer", fg_color="#6c757d"))

        self.btn_restablecer.configure(text="⏳ Restableciendo...", fg_color="#ffc107")
        self.executor.submit(operacion_db)

        self._aplicar_configuracion_al_motor()
        self._restaurar_gestos(silencioso=True)

    def _restaurar_gestos(self, silencioso=False):
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
        if self.motor and self.tracking_activo:
            try:
                estado = self.motor.cola_estado.get_nowait()
                frame = estado["frame"]
                
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                imagen = Image.fromarray(frame_rgb)

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
                
                if self.pip_window is not None:
                    self.pip_window.actualizar_imagen(ctk_foto)
                else:
                    self.label_preview.configure(image=ctk_foto, text="")
                    self.label_preview._imagen = ctk_foto

                self.lbl_fps.configure(text=f"FPS: {estado['fps']:.1f}")
                self.lbl_latencia.configure(text=f"Latencia: {estado['latencia']:.0f} ms")
                if estado["mano_detectada"]:
                    self.lbl_mano.configure(text="Mano: ✅", text_color="#28a745")
                else:
                    self.lbl_mano.configure(text="Mano: ❌", text_color="#dc3545")

                self.lbl_gesto.configure(text=f"Gesto: {estado['gesto']}")
                self.lbl_accion.configure(text=f"Acción: {estado['accion']}")

            except queue.Empty:
                pass
            except Exception as e:
                print(f"[UI] Error actualizando preview: {e}")

        self.after(33, self._actualizar_preview)

    def _detectar_camaras(self, max_camaras=5):
        camaras = []
        for i in range(max_camaras):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                camaras.append(f"Cámara {i}")
                cap.release()
        if not camaras:
            camaras = ["Cámara 0"]
        return camaras

    def _al_cerrar(self):
        self._detener_tracking()
        self.executor.shutdown(wait=False)
        keyboard.unhook_all()
        self.destroy()
