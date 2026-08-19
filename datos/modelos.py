"""
Modelos ORM de la base de datos usando SQLAlchemy.
Representan las tablas y entidades del dominio del sistema.
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datos.conexion import Base


class PerfilCalibracion(Base):
    """
    Representa el perfil de calibración del usuario para el seguimiento de mano.
    Almacena los parámetros de suavizado y el área activa (bounding box).
    """
    __tablename__ = "perfil_calibracion"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(50), nullable=False, default="Predeterminado")
    suavizado_factor = Column(Float, nullable=False, default=0.5)  # Alpha para filtro exponencial (0.1 a 1.0)
    
    # Coordenadas relativas de la zona activa (Bounding Box entre 0.0 y 1.0)
    zona_activa_x_min = Column(Float, nullable=False, default=0.2)
    zona_activa_y_min = Column(Float, nullable=False, default=0.2)
    zona_activa_x_max = Column(Float, nullable=False, default=0.8)
    zona_activa_y_max = Column(Float, nullable=False, default=0.8)
    
    es_activo = Column(Boolean, nullable=False, default=True)

    # Relación con las configuraciones de gestos asignadas a este perfil
    gestos = relationship("ConfiguracionGesto", back_populates="perfil", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<PerfilCalibracion(id={self.id}, nombre='{self.nombre}', suavizado={self.suavizado_factor})>"


class ConfiguracionGesto(Base):
    """
    Representa la reasignación entre un gesto detectado y la acción del SO a ejecutar.
    """
    __tablename__ = "configuracion_gesto"

    id = Column(Integer, primary_key=True, autoincrement=True)
    perfil_id = Column(Integer, ForeignKey("perfil_calibracion.id"), nullable=False)
    
    nombre_gesto = Column(String(50), nullable=False)    # Ej: "PELLIZCO", "MANO_ABIERTA", "DOS_DEDOS"
    accion_sistema = Column(String(50), nullable=False)  # Ej: "CLIC_IZQUIERDO", "MOVER_CURSOR", "SCROLL"
    habilitado = Column(Boolean, nullable=False, default=True)

    perfil = relationship("PerfilCalibracion", back_populates="gestos")

    def __repr__(self):
        return f"<ConfiguracionGesto(gesto='{self.nombre_gesto}', accion='{self.accion_sistema}')>"
