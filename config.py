"""
config.py — Configuración centralizada
========================================
Constantes, horario laboral y clases de configuración por entorno.
Para agregar un entorno nuevo (staging, producción), solo agrega una clase aquí.
"""

import os
from datetime import time


# 
# CONFIGURACIÓN DE HORARIO LABORAL (CEREBRO DE CÁLCULO DE TIEMPOS)
# 
# NOTA ARQUITECTÓNICA PARA FUTUROS DESARROLLADORES (MULTITENANT):
# Este diccionario "hardcodeado" refleja el horario maestro de una sola fábrica.
# Si el sistema va a ser licenciado a múltiples empresas (Software as a Service)
# o cuenta con múltiples sucursales con horarios diferentes, este diccionario
# DEBE ser migrado a la base de datos (e.g. tabla `company_settings` o `horarios_sucursal`).
# El servicio `calcular_tiempo_laboral` ya está adaptado para recibir un `cfg` 
# dinámico inyectado por parámetro. Solo tendrías que instanciar el diccionario 
# leyendo desde la BD del tenant actual.
# 

WORK_CONFIG = {
    "work_start":          time(7, 0),
    "work_end":            time(16, 30),
    "friday_work_end":     time(15, 30),   # Viernes: salida a las 3:30 pm
    "lunch_start":         time(12, 0),
    "lunch_end":           time(12, 30),
    "work_days":           {0, 1, 2, 3, 4},   # 0=Lunes … 4=Viernes
    "include_saturday":    False,
    "saturday_is_regular": False,
    "sunday_is_extra":     False,
}


# 
# CLASES DE CONFIGURACIÓN DE FLASK
# 

class Config:
    """Configuración base compartida por todos los entornos."""
    #  SEGURIDAD 
    # En PRODUCCIÓN: establece la variable de entorno SECRET_KEY con un valor
    # aleatorio largo (ej: python -c "import secrets; print(secrets.token_hex(32))")
    SECRET_KEY    = os.environ.get("SECRET_KEY", "dev-bodega-key-CAMBIAR-EN-PRODUCCION")
    DATABASE      = os.environ.get("DATABASE",   "bodega.db")
    DEBUG         = False
    TIPOS_VALIDOS = ("empaque", "directo")


class DevelopmentConfig(Config):
    """Entorno de desarrollo — recarga automática, errores detallados."""
    DEBUG = True


class ProductionConfig(Config):
    """
    Entorno de producción con waitress.
    SECRET_KEY y DATABASE deben venir de variables de entorno.
    """
    DEBUG = False


# Mapa para seleccionar config por nombre
config_map = {
    "development": DevelopmentConfig,
    "production":  ProductionConfig,
    "default":     DevelopmentConfig,
}

def get_config(env: str = None) -> Config:
    """Retorna la clase de configuración para el entorno indicado."""
    env = env or os.environ.get("FLASK_ENV", "development")
    return config_map.get(env, DevelopmentConfig)
