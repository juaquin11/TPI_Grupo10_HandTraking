import customtkinter as ctk

class AsistenteCalibracion(ctk.CTkToplevel):
    """
    Wizard paso a paso para calibrar el HandTracking.
    Modifica directamente el perfil del dashboard y aplica cambios en tiempo real.
    """
    def __init__(self, dashboard):
        super().__init__(dashboard)
        
        self.dashboard = dashboard
        self.perfil = dashboard.perfil
        
        self.title("🪄 Asistente de Calibración")
        self.geometry("500x400")
        self.resizable(False, False)
        
        # Siempre al frente y bloquear principal
        self.attributes("-topmost", True)
        self.grab_set()
        
        self.paso_actual = 1
        self.total_pasos = 3
        
        # Contenedor principal
        self.frame_contenido = ctk.CTkFrame(self, corner_radius=10)
        self.frame_contenido.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Botones de navegación
        self.frame_botones = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_botones.pack(fill="x", padx=20, pady=(0, 20))
        
        self.btn_anterior = ctk.CTkButton(self.frame_botones, text="← Anterior", command=self._paso_anterior)
        self.btn_anterior.pack(side="left")
        
        self.btn_siguiente = ctk.CTkButton(self.frame_botones, text="Siguiente →", command=self._paso_siguiente)
        self.btn_siguiente.pack(side="right")
        
        self.frames_pasos = {}
        self._construir_pasos()
        self._mostrar_paso(1)

    def _aplicar(self):
        self.dashboard._aplicar_configuracion_al_motor()

    def _construir_pasos(self):
        # --- Paso 1: Zona Activa (Bounding Box) ---
        f1 = ctk.CTkFrame(self.frame_contenido, fg_color="transparent")
        self.frames_pasos[1] = f1
        
        ctk.CTkLabel(f1, text="Paso 1: Área de Movimiento", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(0, 10))
        ctk.CTkLabel(f1, text="Observa el rectángulo naranja en la cámara.\nAjusta su tamaño para que cubra tu rango cómodo de movimiento.\n(Más pequeño = Cursor más rápido y sensible).", justify="center").pack(pady=(0, 20))
        
        def update_x(val, is_max):
            if is_max: self.perfil.zona_activa_x_max = val
            else: self.perfil.zona_activa_x_min = val
            self._aplicar()
            
        def update_y(val, is_max):
            if is_max: self.perfil.zona_activa_y_max = val
            else: self.perfil.zona_activa_y_min = val
            self._aplicar()

        slider_x_min = ctk.CTkSlider(f1, from_=0.05, to=0.45, command=lambda v: update_x(v, False))
        slider_x_min.set(self.perfil.zona_activa_x_min)
        ctk.CTkLabel(f1, text="Margen Izquierdo").pack()
        slider_x_min.pack(fill="x", padx=30, pady=(0, 10))
        
        slider_x_max = ctk.CTkSlider(f1, from_=0.55, to=0.95, command=lambda v: update_x(v, True))
        slider_x_max.set(self.perfil.zona_activa_x_max)
        ctk.CTkLabel(f1, text="Margen Derecho").pack()
        slider_x_max.pack(fill="x", padx=30, pady=(0, 10))

        slider_y_min = ctk.CTkSlider(f1, from_=0.05, to=0.45, command=lambda v: update_y(v, False))
        slider_y_min.set(self.perfil.zona_activa_y_min)
        ctk.CTkLabel(f1, text="Margen Superior").pack()
        slider_y_min.pack(fill="x", padx=30, pady=(0, 10))
        
        slider_y_max = ctk.CTkSlider(f1, from_=0.55, to=0.95, command=lambda v: update_y(v, True))
        slider_y_max.set(self.perfil.zona_activa_y_max)
        ctk.CTkLabel(f1, text="Margen Inferior").pack()
        slider_y_max.pack(fill="x", padx=30, pady=(0, 10))


        # --- Paso 2: Suavizado ---
        f2 = ctk.CTkFrame(self.frame_contenido, fg_color="transparent")
        self.frames_pasos[2] = f2
        
        ctk.CTkLabel(f2, text="Paso 2: Fluidez de Movimiento", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(0, 10))
        ctk.CTkLabel(f2, text="¿Sientes que el cursor tiembla demasiado?\nAjusta este valor. Hacia la izquierda estabiliza el pulso,\nhacia la derecha da respuesta más inmediata.", justify="center").pack(pady=(0, 30))
        
        def update_suav(val):
            self.perfil.suavizado_factor = val
            self._aplicar()
            
        slider_suav = ctk.CTkSlider(f2, from_=0.05, to=1.0, command=update_suav)
        slider_suav.set(self.perfil.suavizado_factor)
        slider_suav.pack(fill="x", padx=40, pady=10)
        
        etiq_suav = ctk.CTkFrame(f2, fg_color="transparent")
        etiq_suav.pack(fill="x", padx=40)
        ctk.CTkLabel(etiq_suav, text="← Más Estable").pack(side="left")
        ctk.CTkLabel(etiq_suav, text="Más Rápido →").pack(side="right")


        # --- Paso 3: Zona Muerta ---
        f3 = ctk.CTkFrame(self.frame_contenido, fg_color="transparent")
        self.frames_pasos[3] = f3
        
        ctk.CTkLabel(f3, text="Paso 3: Precisión de Clics", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(0, 10))
        ctk.CTkLabel(f3, text="La Zona Muerta ignora los micro-movimientos involuntarios\nque suceden al cerrar la mano para hacer un clic.", justify="center").pack(pady=(0, 30))
        
        def update_zm(val):
            self.perfil.zona_muerta_px = int(val)
            self.lbl_zm_val.configure(text=f"{int(val)} píxeles")
            self._aplicar()
            
        slider_zm = ctk.CTkSlider(f3, from_=0, to=10, number_of_steps=10, command=update_zm)
        slider_zm.set(self.perfil.zona_muerta_px)
        slider_zm.pack(fill="x", padx=40, pady=10)
        
        self.lbl_zm_val = ctk.CTkLabel(f3, text=f"{self.perfil.zona_muerta_px} píxeles", font=ctk.CTkFont(weight="bold"))
        self.lbl_zm_val.pack()

    def _mostrar_paso(self, paso):
        for f in self.frames_pasos.values():
            f.pack_forget()
        
        self.frames_pasos[paso].pack(fill="both", expand=True)
        self.paso_actual = paso
        
        if paso == 1:
            self.btn_anterior.configure(state="disabled")
        else:
            self.btn_anterior.configure(state="normal")
            
        if paso == self.total_pasos:
            self.btn_siguiente.configure(text="Finalizar y Guardar ✅", fg_color="#28a745", hover_color="#218838")
        else:
            self.btn_siguiente.configure(text="Siguiente →", fg_color=["#3a7ebf", "#1f538d"], hover_color=["#325882", "#14375e"])

    def _paso_siguiente(self):
        if self.paso_actual < self.total_pasos:
            self._mostrar_paso(self.paso_actual + 1)
        else:
            self.dashboard._guardar_perfil()
            self.destroy()

    def _paso_anterior(self):
        if self.paso_actual > 1:
            self._mostrar_paso(self.paso_actual - 1)
