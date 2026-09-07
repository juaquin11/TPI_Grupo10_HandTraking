import customtkinter as ctk

class WidgetFlotante(ctk.CTkToplevel):
    """
    Mini ventana (Picture-in-Picture) que flota sobre otras ventanas
    sin bordes y permite arrastrarse libremente.
    """
    def __init__(self, parent, callback_restaurar):
        super().__init__(parent)
        
        self.callback_restaurar = callback_restaurar
        
        # Configuración de la ventana
        self.title("HandTracking Mini")
        
        # Dimensiones y posición inicial (esquina inferior derecha aprox)
        w, h = 320, 240
        x = self.winfo_screenwidth() - w - 20
        y = self.winfo_screenheight() - h - 60
        self.geometry(f"{w}x{h}+{x}+{y}")
        
        # Sin bordes y siempre al frente
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        
        # Label para mostrar el video
        self.label_video = ctk.CTkLabel(self, text="Cargando...", fg_color="black")
        self.label_video.pack(fill="both", expand=True)
        
        # Binds para arrastrar la ventana
        self.label_video.bind("<ButtonPress-1>", self._on_drag_start)
        self.label_video.bind("<B1-Motion>", self._on_drag_motion)
        
        # Bind para restaurar con doble clic
        self.label_video.bind("<Double-Button-1>", self._on_double_click)
        
        # Variables internas para el drag
        self._drag_x = 0
        self._drag_y = 0

    def _on_drag_start(self, event):
        """Guarda la posición inicial al hacer clic para arrastrar."""
        self._drag_x = event.x
        self._drag_y = event.y

    def _on_drag_motion(self, event):
        """Mueve la ventana basándose en el movimiento del ratón."""
        x = self.winfo_x() - self._drag_x + event.x
        y = self.winfo_y() - self._drag_y + event.y
        self.geometry(f"+{x}+{y}")

    def _on_double_click(self, event):
        """Notifica al padre para restaurar la vista completa."""
        if self.callback_restaurar:
            self.callback_restaurar()
            
    def actualizar_imagen(self, ctk_imagen):
        """Actualiza el label con el nuevo frame."""
        self.label_video.configure(image=ctk_imagen, text="")
        self.label_video._imagen = ctk_imagen
