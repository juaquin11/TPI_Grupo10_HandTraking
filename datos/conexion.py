"""
Módulo de conexión a la base de datos SQLite usando SQLAlchemy.
"""

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

# Nombre de la base de datos local SQLite
DB_NAME = "handtracking.db"
DATABASE_URL = f"sqlite:///{DB_NAME}"

# Motor de base de datos SQLAlchemy (check_same_thread=False para hilos múltiples como la webcam)
engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})

# Fábrica de sesiones para interactuar con la base de datos
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Clase base declarativa para los modelos ORM
Base = declarative_base()


def inicializar_db():
    """Crea las tablas y agrega columnas nuevas a bases existentes."""
    Base.metadata.create_all(bind=engine)

    columnas_faltantes = {
        "zona_muerta_px": "INTEGER NOT NULL DEFAULT 3",
        "es_zurdo": "BOOLEAN NOT NULL DEFAULT 0",
        "id_camara": "INTEGER NOT NULL DEFAULT 0",
        "umbral_pellizco": "REAL NOT NULL DEFAULT 0.06",
    }

    inspector = inspect(engine)
    columnas_actuales = {
        columna["name"] for columna in inspector.get_columns("perfil_calibracion")
    }

    with engine.begin() as conexion:
        for nombre, definicion in columnas_faltantes.items():
            if nombre not in columnas_actuales:
                conexion.execute(
                    text(
                        f"ALTER TABLE perfil_calibracion "
                        f"ADD COLUMN {nombre} {definicion}"
                    )
                )


def obtener_sesion():
    """Genera y retorna una nueva sesión para interactuar con la base de datos."""
    return SessionLocal()
