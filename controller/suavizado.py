"""
Módulo de Suavizado de Movimiento.
Aplica filtros matemáticos a las coordenadas detectadas para reducir
el temblor natural de la mano antes de interpretarlas como gestos.

Diseño extensible: se define una clase base (FiltroSuavizado) para que
en el futuro se pueda intercambiar el algoritmo (ej. Kalman) sin modificar
el resto de la aplicación.

IMPORTANTE (Checklist): Este módulo NO accede a la base de datos directamente.
"""

from abc import ABC, abstractmethod


class FiltroSuavizado(ABC):
    """
    Clase base abstracta para filtros de suavizado.
    Cualquier filtro nuevo (EMA, Kalman, etc.) debe heredar de esta clase
    e implementar el método 'aplicar'.
    """

    @abstractmethod
    def aplicar(self, valor_actual):
        """
        Recibe el valor actual (x, y) y retorna el valor suavizado.
        """
        pass

    @abstractmethod
    def reiniciar(self):
        """Resetea el estado interno del filtro."""
        pass


class FiltroEMA(FiltroSuavizado):
    """
    Filtro de Media Móvil Exponencial (Exponential Moving Average).

    Fórmula: suavizado = alpha * valor_actual + (1 - alpha) * valor_anterior

    - alpha cercano a 1.0 → menos suavizado, respuesta más rápida (más temblor).
    - alpha cercano a 0.0 → más suavizado, respuesta más lenta (menos temblor pero más lag).

    Un valor entre 0.3 y 0.5 suele ser un buen balance.
    """

    def __init__(self, alpha=0.4):
        """
        Parámetros:
        - alpha: factor de suavizado entre 0.0 y 1.0.
        """
        if not 0.0 < alpha <= 1.0:
            raise ValueError("El valor de alpha debe estar entre 0.0 (exclusivo) y 1.0 (inclusivo).")
        self.alpha = alpha
        self.valor_anterior = None

    def aplicar(self, valor_actual):
        """
        Aplica el filtro EMA a un par de coordenadas (x, y).

        Parámetros:
        - valor_actual: tupla (x, y) con las coordenadas del frame actual.

        Retorna:
        - tupla (x_suavizado, y_suavizado).
        """
        if self.valor_anterior is None:
            # Primer frame: no hay referencia anterior, se toma el valor tal cual
            self.valor_anterior = valor_actual
            return valor_actual

        x_actual, y_actual = valor_actual
        x_anterior, y_anterior = self.valor_anterior

        x_suavizado = self.alpha * x_actual + (1 - self.alpha) * x_anterior
        y_suavizado = self.alpha * y_actual + (1 - self.alpha) * y_anterior

        self.valor_anterior = (x_suavizado, y_suavizado)
        return (x_suavizado, y_suavizado)

    def reiniciar(self):
        """Resetea el filtro para comenzar desde cero."""
        self.valor_anterior = None

    def set_alpha(self, nuevo_alpha):
        """
        Permite cambiar el factor de suavizado en tiempo real
        (ej. desde el Dashboard de configuración).
        """
        if not 0.0 < nuevo_alpha <= 1.0:
            raise ValueError("El valor de alpha debe estar entre 0.0 (exclusivo) y 1.0 (inclusivo).")
        self.alpha = nuevo_alpha
