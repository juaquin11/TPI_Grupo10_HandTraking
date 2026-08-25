"""
Punto de entrada principal de la aplicación HandTracking.
Arquitectura de 3 Capas:
- Presentación: views/
- Negocio: controller/
- Datos: datos/
"""

from views.dashboard import Dashboard


def main():
    app = Dashboard()
    app.mainloop()


if __name__ == "__main__":
    main()
