"""
Máquina de Estados Finita (FSM) para el manejo del Drag & Drop.
Aísla la lógica compleja de transiciones y confirmaciones por frames.
"""

DRAG_IDLE = "IDLE"
DRAG_PUNO_DETECTADO = "PUNO_DETECTADO"
DRAG_DRAGGING = "DRAGGING"
DRAG_RELEASE = "RELEASE"


class DragStateMachine:
    def __init__(self, frames_necesarios=4, tolerancia_frames=6):
        self.estado = DRAG_IDLE
        self.frames_confirmacion = 0
        self.frames_necesarios = frames_necesarios
        self.frames_sin_puno = 0
        self.tolerancia_frames = tolerancia_frames

    def actualizar(self, es_drag):
        """
        Actualiza el estado según si el gesto actual mapea a Drag & Drop.
        Retorna la acción a ejecutar ("INICIAR_DRAG", "MANTENER_DRAG", "SOLTAR_DRAG", o None).
        """
        if self.estado == DRAG_IDLE:
            if es_drag:
                self.estado = DRAG_PUNO_DETECTADO
                self.frames_confirmacion = 1
            return None

        elif self.estado == DRAG_PUNO_DETECTADO:
            if es_drag:
                self.frames_confirmacion += 1
                if self.frames_confirmacion >= self.frames_necesarios:
                    self.estado = DRAG_DRAGGING
                    self.frames_sin_puno = 0
                    return "INICIAR_DRAG"
            else:
                self.estado = DRAG_IDLE
                self.frames_confirmacion = 0
            return None

        elif self.estado == DRAG_DRAGGING:
            if es_drag:
                self.frames_sin_puno = 0
                return "MANTENER_DRAG"
            else:
                self.frames_sin_puno += 1
                if self.frames_sin_puno >= self.tolerancia_frames:
                    self.estado = DRAG_RELEASE
                    return "SOLTAR_DRAG"
                else:
                    return "MANTENER_DRAG"

        elif self.estado == DRAG_RELEASE:
            self.estado = DRAG_IDLE
            self.frames_confirmacion = 0
            self.frames_sin_puno = 0
            return None

        return None

    def resetear(self):
        """Fuerza a la máquina a volver al estado inicial."""
        self.estado = DRAG_IDLE
        self.frames_confirmacion = 0
        self.frames_sin_puno = 0
