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
        zona_activa_x_min=0.2,
        zona_activa_y_min=0.2,
        zona_activa_x_max=0.8,
        zona_activa_y_max=0.8,
        zona_muerta_px=3,
        es_zurdo=False,
        id_camara=0,
        umbral_pellizco=0.06,
        es_activo=True
    )
    sesion.add(nuevo_perfil)
    sesion.commit()
    sesion.refresh(nuevo_perfil)

    # Gestos por defecto acordados (v2: Centro de Palma + Pellizcos)
    gestos_iniciales = [
        ConfiguracionGesto(perfil_id=nuevo_perfil.id, nombre_gesto="MANO_ABIERTA", accion_sistema="MOVER_CURSOR"),
        ConfiguracionGesto(perfil_id=nuevo_perfil.id, nombre_gesto="PELLIZCO_INDICE", accion_sistema="CLIC_IZQUIERDO"),
        ConfiguracionGesto(perfil_id=nuevo_perfil.id, nombre_gesto="PELLIZCO_MEDIO", accion_sistema="CLIC_DERECHO"),
        ConfiguracionGesto(perfil_id=nuevo_perfil.id, nombre_gesto="PELLIZCO_TRIPLE", accion_sistema="DRAG_AND_DROP"),
        ConfiguracionGesto(perfil_id=nuevo_perfil.id, nombre_gesto="DOS_DEDOS", accion_sistema="SCROLL"),
    ]
    sesion.add_all(gestos_iniciales)
    sesion.commit()
    return sesion.query(PerfilCalibracion).options(joinedload(PerfilCalibracion.gestos)).filter_by(id=nuevo_perfil.id).first()


def guardar_perfil(id_perfil, nombre, suavizado, x_min, y_min, x_max, y_max,
                   zona_muerta_px=3, es_zurdo=False, id_camara=0, umbral_pellizco=0.06):
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
            perfil.zona_muerta_px = zona_muerta_px
            perfil.es_zurdo = es_zurdo
            perfil.id_camara = id_camara
            perfil.umbral_pellizco = umbral_pellizco
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


def guardar_mapeo_completo_gestos(id_perfil, mapeo_dict):
    """
    Guarda o actualiza el mapeo completo de gestos para un perfil.
    mapeo_dict: dict con {nombre_gesto: accion_sistema}
    """
    sesion = obtener_sesion()
    try:
        gestos = sesion.query(ConfiguracionGesto).filter_by(perfil_id=id_perfil).all()
        gestos_map = {g.nombre_gesto: g for g in gestos}

        for nombre_gesto, accion in mapeo_dict.items():
            habilitado = (accion != "NINGUNA")
            if nombre_gesto in gestos_map:
                gestos_map[nombre_gesto].accion_sistema = accion
                gestos_map[nombre_gesto].habilitado = habilitado
            else:
                nuevo = ConfiguracionGesto(
                    perfil_id=id_perfil,
                    nombre_gesto=nombre_gesto,
                    accion_sistema=accion,
                    habilitado=habilitado
                )
                sesion.add(nuevo)
        sesion.commit()
    finally:
        sesion.close()


def restaurar_gestos_predeterminados(id_perfil):
    """
    Restaura los gestos de un perfil a los valores predeterminados de fábrica.
    Elimina los gestos existentes y los recrea con el mapeo original.
    """
    gestos_default = {
        "MANO_ABIERTA": "MOVER_CURSOR",
        "PELLIZCO_INDICE": "CLIC_IZQUIERDO",
        "PELLIZCO_MEDIO": "CLIC_DERECHO",
        "PELLIZCO_TRIPLE": "DRAG_AND_DROP",
        "DOS_DEDOS": "SCROLL",
    }
    sesion = obtener_sesion()
    try:
        # Eliminar gestos actuales del perfil
        sesion.query(ConfiguracionGesto).filter_by(perfil_id=id_perfil).delete()

        # Recrear con defaults
        for nombre_gesto, accion in gestos_default.items():
            sesion.add(ConfiguracionGesto(
                perfil_id=id_perfil,
                nombre_gesto=nombre_gesto,
                accion_sistema=accion,
                habilitado=True
            ))
        sesion.commit()

        # Retornar los gestos recién creados
        return sesion.query(ConfiguracionGesto).filter_by(perfil_id=id_perfil).all()
    finally:
        sesion.close()
