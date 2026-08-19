"""
Punto de entrada principal de la aplicación HandTracking.
Arquitectura de 3 Capas:
- Presentación: views/
- Negocio: controller/
- Datos: datos/
"""

from controller.motor import MotorHandTracking


def main():
    print("=" * 50)
    print("  HandTracking - Control del cursor con la mano")
    print("=" * 50)
    print()

    motor = MotorHandTracking()
    motor.iniciar(mostrar_preview=True)


if __name__ == "__main__":
    main()
