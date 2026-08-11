"""
Repositorio para la capa de datos.
Contiene todas las funciones de consulta y manipulación de datos (CRUD).
REGLA DEL CHECKLIST: Todas las funciones de acceso a la base de datos residen únicamente aquí.
"""

from sqlalchemy.orm import joinedload
from datos.conexion import obtener_sesion, inicializar_db
from datos.modelos import PerfilCalibracion, ConfiguracionGesto


def obtener_perfil_activo():
    """
    Obtiene el perfil de calibración que está marcado como activo (con sus gestos cargados).
    Si no existe ninguno, inicializa la BD y crea un perfil predeterminado.
    """
    inicializar_db()
    sesion = obtener_sesion()
    try:
        perfil = (
            sesion.query(PerfilCalibracion)
            .options(joinedload(PerfilCalibracion.gestos))
            .filter_by(es_activo=True)
            .first()
        )
        if not perfil:
            perfil = _crear_perfil_predeterminado(sesion)
        return perfil
    finally:
        sesion.close()


def _crear_perfil_predeterminado(sesion):
    """Función auxiliar interna para poblar la BD con un perfil inicial si está vacía."""
    nuevo_perfil = PerfilCalibracion(
        nombre="Predeterminado",
        suavizado_factor=0.5,
        zona_activa_x_min=0.1,
        zona_activa_y_min=0.1,
        zona_activa_x_max=0.9,
        zona_activa_y_max=0.9,
        es_activo=True
    )
    sesion.add(nuevo_perfil)
    sesion.commit()
    sesion.refresh(nuevo_perfil)

    # Gestos por defecto acordados
    gestos_iniciales = [
        ConfiguracionGesto(perfil_id=nuevo_perfil.id, nombre_gesto="DOS_DEDOS", accion_sistema="MOVER_CURSOR"),
        ConfiguracionGesto(perfil_id=nuevo_perfil.id, nombre_gesto="CLIC_INDICE", accion_sistema="CLIC_IZQUIERDO"),
        ConfiguracionGesto(perfil_id=nuevo_perfil.id, nombre_gesto="CLIC_MEDIO", accion_sistema="CLIC_DERECHO"),
        ConfiguracionGesto(perfil_id=nuevo_perfil.id, nombre_gesto="PELLIZCO", accion_sistema="DRAG_AND_DROP"),
        ConfiguracionGesto(perfil_id=nuevo_perfil.id, nombre_gesto="UN_DEDO_INDICE", accion_sistema="SCROLL"),
    ]
    sesion.add_all(gestos_iniciales)
    sesion.commit()
    return sesion.query(PerfilCalibracion).options(joinedload(PerfilCalibracion.gestos)).filter_by(id=nuevo_perfil.id).first()


def guardar_perfil(id_perfil, nombre, suavizado, x_min, y_min, x_max, y_max):
    """
    Actualiza los datos del perfil de calibración especificado.
    """
    sesion = obtener_sesion()
    try:
        perfil = sesion.query(PerfilCalibracion).filter_by(id=id_perfil).first()
        if perfil:
            perfil.nombre = nombre
            perfil.suavizado_factor = suavizado
            perfil.zona_activa_x_min = x_min
            perfil.zona_activa_y_min = y_min
            perfil.zona_activa_x_max = x_max
            perfil.zona_activa_y_max = y_max
            sesion.commit()
            sesion.refresh(perfil)
        return perfil
    finally:
        sesion.close()


def obtener_todos_los_perfiles():
    """Retorna una lista de todos los perfiles guardados."""
    sesion = obtener_sesion()
    try:
        return sesion.query(PerfilCalibracion).all()
    finally:
        sesion.close()


def actualizar_mapeo_gesto(id_gesto, nueva_accion, habilitado=True):
    """Actualiza la acción asignada a un gesto específico."""
    sesion = obtener_sesion()
    try:
        gesto = sesion.query(ConfiguracionGesto).filter_by(id=id_gesto).first()
        if gesto:
            gesto.accion_sistema = nueva_accion
            gesto.habilitado = habilitado
            sesion.commit()
            sesion.refresh(gesto)
        return gesto
    finally:
        sesion.close()
