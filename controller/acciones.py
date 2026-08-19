"""
Módulo de Inyección de Eventos al Sistema Operativo.
Traduce los gestos reconocidos en acciones reales del cursor usando pynput.

Acciones soportadas:
- Mover el cursor proporcionalmente a la posición de la mano.
- Clic izquierdo / derecho.
- Scroll vertical.
- Drag & Drop (mantener clic, arrastrar y soltar).

IMPORTANTE (Checklist): Este módulo NO accede a la base de datos directamente.
"""

import screeninfo
from pynput.mouse import Button, Controller as MouseController


class ControladorMouse:
    """
    Controla el mouse del sistema operativo a través de pynput.
    """

    def __init__(self):
        self.mouse = MouseController()
        self._arrastrando = False  # Estado de drag & drop

        # Obtener resolución de pantalla
        monitor = screeninfo.get_monitors()[0]
        self.ancho_pantalla = monitor.width
        self.alto_pantalla = monitor.height

    def mover_cursor(self, x_normalizado, y_normalizado):
        """
        Mueve el cursor a una posición basada en coordenadas normalizadas [0.0, 1.0].

        Parámetros:
        - x_normalizado: posición X de la mano normalizada (0.0 = izquierda, 1.0 = derecha).
        - y_normalizado: posición Y de la mano normalizada (0.0 = arriba, 1.0 = abajo).
        """
        # Convertir coordenadas normalizadas a píxeles de pantalla
        x_pixel = int(x_normalizado * self.ancho_pantalla)
        y_pixel = int(y_normalizado * self.alto_pantalla)

        # Limitar a los bordes de la pantalla
        x_pixel = max(0, min(x_pixel, self.ancho_pantalla - 1))
        y_pixel = max(0, min(y_pixel, self.alto_pantalla - 1))

        self.mouse.position = (x_pixel, y_pixel)

    def clic_izquierdo(self):
        """Simula un clic izquierdo."""
        self.mouse.click(Button.left, 1)

    def clic_derecho(self):
        """Simula un clic derecho."""
        self.mouse.click(Button.right, 1)

    def scroll(self, direccion_y):
        """
        Simula scroll vertical.

        Parámetros:
        - direccion_y: positivo = scroll arriba, negativo = scroll abajo.
        """
        self.mouse.scroll(0, direccion_y)

    def iniciar_arrastre(self):
        """Inicia un drag (mantiene presionado el botón izquierdo)."""
        if not self._arrastrando:
            self.mouse.press(Button.left)
            self._arrastrando = True

    def soltar_arrastre(self):
        """Suelta el drag (libera el botón izquierdo)."""
        if self._arrastrando:
            self.mouse.release(Button.left)
            self._arrastrando = False

    @property
    def esta_arrastrando(self):
        """Retorna True si está en medio de un drag & drop."""
        return self._arrastrando

    def obtener_posicion_actual(self):
        """Retorna la posición actual del cursor como tupla (x, y)."""
        return self.mouse.position
