import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, current_app, send_file
from werkzeug.utils import secure_filename
from database import get_db
from services.auditoria import registrar_cambio

configuracion_bp = Blueprint('configuracion', __name__)

# Configuración de subida de archivos
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'svg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@configuracion_bp.route('/configuracion', methods=['GET', 'POST'])
def ajustes():
    """Panel de administración de identidad corporativa y ajustes del sistema."""
    if not g.user or g.user.get('rol') != 'admin':
        flash("Acceso denegado. Se requiere rol de administrador.", "error")
        return redirect(url_for('registros.registros'))
    
    conn = get_db()
    empresa = conn.execute("SELECT * FROM empresa LIMIT 1").fetchone()
    
    if request.method == 'POST':
        nombre = request.form.get("nombre", "").strip()
        subtitulo = request.form.get("subtitulo", "").strip()
        color_primario = request.form.get("color_primario", "#0d2a6e")
        color_secundario = request.form.get("color_secundario", "#f5c800")
        
        # Manejo de logo
        logo_url = empresa['logo_url'] if empresa else ""
        file = request.files.get('logo_file')
        
        if file and allowed_file(file.filename):
            filename = secure_filename(f"logo_{g.user['id']}_{file.filename}")
            # Carpeta específica por base de datos para evitar colisiones
            db_name = os.path.basename(current_app.config['DATABASE']).split('.')[0]
            upload_folder = os.path.join(current_app.static_folder, 'uploads', db_name)
            
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)
                
            file.save(os.path.join(upload_folder, filename))
            logo_url = f"/static/uploads/{db_name}/{filename}"

        if empresa:
            # Auditoría antes de actualizar
            registrar_cambio(conn, "empresa", empresa['id'], "nombre", empresa['nombre'], nombre)
            registrar_cambio(conn, "empresa", empresa['id'], "color_primario", empresa['color_primario'], color_primario)
            
            conn.execute("""
                UPDATE empresa SET 
                    nombre=?, subtitulo=?, color_primario=?, color_secundario=?, logo_url=?
                WHERE id=?
            """, (nombre, subtitulo, color_primario, color_secundario, logo_url, empresa['id']))
        else:
            conn.execute("""
                INSERT INTO empresa (nombre, subtitulo, color_primario, color_secundario, logo_url)
                VALUES (?, ?, ?, ?, ?)
            """, (nombre, subtitulo, color_primario, color_secundario, logo_url))
            
        conn.commit()
        flash(" Configuración de empresa actualizada correctamente.", "success")
        return redirect(url_for('configuracion.ajustes'))

    return render_template('configuracion.html', empresa=empresa)

@configuracion_bp.route('/configuracion/backup')
def descargar_respaldo():
    """Descarga de seguridad de la base de datos completa (SQLite)."""
    if not g.user or g.user.get('rol') != 'admin':
        flash("Acceso denegado. Solo administradores pueden descargar respaldos.", "error")
        return redirect(url_for('registros.registros'))
    
    db_path = current_app.config.get('DATABASE')
    if not db_path or not os.path.exists(db_path):
        flash("Error: No se encontró el archivo de base de datos.", "error")
        return redirect(url_for('configuracion.ajustes'))
        
    try:
        from datetime import datetime
        fecha = datetime.now().strftime("%Y-%m-%d_%H-%M")
        nombre_descarga = f"Respaldo_Bodega_{fecha}.sqlite"
        return send_file(db_path, as_attachment=True, download_name=nombre_descarga)
    except Exception as e:
        flash(f"Error al generar el respaldo: {e}", "error")
        return redirect(url_for('configuracion.ajustes'))
