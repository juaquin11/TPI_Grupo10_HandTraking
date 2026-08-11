"""
Módulo de conexión a la base de datos SQLite usando SQLAlchemy.
"""

from sqlalchemy import create_engine
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
    """Crea todas las tablas definidas en los modelos si aún no existen."""
    Base.metadata.create_all(bind=engine)


def obtener_sesion():
    """Genera y retorna una nueva sesión para interactuar con la base de datos."""
    return SessionLocal()
