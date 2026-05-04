"""
OmniFlow-WMS
Copyright (c) 2026 manuelitox12. All rights reserved.
This is proprietary software published for portfolio evaluation only.
Commercial use is strictly prohibited.


app.py — Punto de entrada principal de la aplicación
=====================================================
ARQUITECTURA:
  - Flask actúa como framework web (ligero, extensible)
  - Blueprints organizan las rutas por dominio (pedidos, estados, auth, etc.)
  - La autenticación se maneja vía cookies de sesión firmadas con SECRET_KEY
  - Para producción, usar Waitress (Windows) o Gunicorn (Linux) en lugar de
    el servidor de desarrollo de Flask (ver comentario al final)

PARA NUEVOS DESARROLLADORES:
  - Cada blueprint está en routes/ y se registra aquí
  - Las plantillas están en templates/ y extienden base.html
  - La lógica de negocio pesada va en services/ y models/
  - La configuración está en config.py (horarios, secretos, BD)
"""

from datetime import timedelta
from flask import Flask
from config import get_config
from database import init_db, close_db

#  Importar Blueprints 
from routes.auth import auth_bp
from routes.main import main_bp
from routes.registros import registros_bp
from routes.pedidos import pedidos_bp
from routes.estados import estados_bp
from routes.anexos import anexos_bp
from routes.catalogo import catalogo_bp
from routes.exportar import exportar_bp
from routes.estadisticas import estadisticas_bp
from routes.configuracion import configuracion_bp


def create_app(env=None):
    app = Flask(__name__)
    config = get_config(env)
    app.config.from_object(config)

    #  Cierre automático de BD al terminar cada request 
    app.teardown_appcontext(close_db)

    #  Configuración de Sesiones y CSRF 
    # Las sesiones persisten 8 horas (una jornada laboral).
    # Si SECRET_KEY cambia, todas las sesiones activas se invalidan.
    app.permanent_session_lifetime = timedelta(hours=8)
    app.config.update(
        SESSION_COOKIE_SAMESITE='Lax', # Defensa pasiva principal contra CSRF
        SESSION_COOKIE_HTTPONLY=True,  # Defensa contra XSS robando cookies
    )

    #  Filtros Jinja personalizados 
    def str_to_time(s):
        """Convierte datetime string a formato legible: '10 Abr 02:30 PM'"""
        if not s: return ""
        try:
            from datetime import datetime
            dt_str = s[:16].replace("T", " ")
            dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
            meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
            mes_txt = meses[dt.month - 1]
            return dt.strftime(f"%d {mes_txt} %I:%M %p")
        except:
            return s[11:16] if len(s) >= 16 else ""
    app.jinja_env.filters['str_to_time'] = str_to_time

    def month_name(m):
        """Convierte número de mes a abreviatura: 4 → 'Abr'"""
        try:
            m = int(m)
            meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
            if 1 <= m <= 12:
                return meses[m-1]
            return str(m)
        except:
            return m
    app.jinja_env.filters['month_name'] = month_name

    #  Registrar Blueprints 
    # IMPORTANTE: auth_bp debe ir PRIMERO porque contiene before_app_request
    # que carga g.user y g.empresa en cada petición
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(registros_bp)
    app.register_blueprint(pedidos_bp)
    app.register_blueprint(estados_bp)
    app.register_blueprint(anexos_bp)
    app.register_blueprint(catalogo_bp)
    app.register_blueprint(exportar_bp)
    app.register_blueprint(estadisticas_bp)
    app.register_blueprint(configuracion_bp)

    #  Security Headers (Enterprise Grade) 
    @app.after_request
    def add_security_headers(response):
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        # CSP básica para prevenir inyección de scripts externos
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:;"
        # Prevent caching of sensitive routes
        if 'Cache-Control' not in response.headers:
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return response

    #  Strict CSRF Origin Checking 
    # Dado que no usamos tokens pesados, bloqueamos cualquier petición POST
    # que provenga de un origen o referer externo (Defensa Activa CSRF).
    from flask import request, abort
    from urllib.parse import urlparse

    @app.before_request
    def check_csrf():
        if request.method == "POST":
            referer = request.headers.get("Referer")
            origin = request.headers.get("Origin")
            
            # Helper to normalize localhost/127.0.0.1
            def normalize(netloc):
                return netloc.replace("localhost", "127.0.0.1")

            host_norm = normalize(request.host)

            if origin:
                if normalize(urlparse(origin).netloc) != host_norm:
                    abort(403, "Bad Origin - CSRF Blocked")
            elif referer:
                if normalize(urlparse(referer).netloc) != host_norm:
                    abort(403, "Bad Referer - CSRF Blocked")

    return app

app = create_app()

if __name__ == "__main__":
    init_db()

    # host="0.0.0.0" permite que otras computadoras en la red se conecten
    app.run(host="0.0.0.0", debug=app.config["DEBUG"], port=5001, use_reloader=app.config["DEBUG"])
    #  Servidor de Producción (descomentar para deploy) 
    # from waitress import serve
    # serve(app, host="0.0.0.0", port=5000)
