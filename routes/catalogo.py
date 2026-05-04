"""
catalogo.py — Gestión de Catálogos
=====================================
Permite administrar:
1. Marcas (clientes)
2. Personas externas (choferes/retiro)
3. Personal de planilla (empleados de bodega)
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from database import get_db
import sqlite3

catalogo_bp = Blueprint('catalogo', __name__)

@catalogo_bp.route('/catalogo', methods=['GET'])
def catalogo():
    conn = get_db()
    marcas   = conn.execute('SELECT * FROM marcas ORDER BY nombre').fetchall()
    personas = conn.execute('SELECT * FROM personas ORDER BY nombre').fetchall()
    personal = conn.execute('SELECT * FROM personal ORDER BY nombre ASC, apellido ASC').fetchall()
    
    return render_template('catalogo.html', 
                          marcas=marcas, 
                          personas=personas, 
                          personal=personal)

#  API endpoints for AJAX / Fetch 

@catalogo_bp.route('/api/marcas', methods=['POST'])
def api_agregar_marca():
    data = request.get_json() or {}
    nombre = data.get('nombre', '').strip().upper()
    if not nombre:
        return jsonify({"ok": False, "msg": "Nombre requerido"})
    
    conn = get_db()
    try:
        conn.execute('INSERT INTO marcas (nombre) VALUES (?)', (nombre,))
        conn.commit()
        return jsonify({"ok": True})
    except sqlite3.IntegrityError:
        return jsonify({"ok": False, "msg": "La marca ya existe"})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})

@catalogo_bp.route('/api/personas', methods=['POST'])
def api_agregar_persona():
    data = request.get_json() or {}
    nombre = data.get('nombre', '').strip()
    if not nombre:
        return jsonify({"ok": False, "msg": "Nombre requerido"})
    
    conn = get_db()
    try:
        conn.execute('INSERT INTO personas (nombre) VALUES (?)', (nombre,))
        conn.commit()
        return jsonify({"ok": True})
    except sqlite3.IntegrityError:
        return jsonify({"ok": False, "msg": "La persona ya existe"})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})

@catalogo_bp.route('/api/personal', methods=['POST'])
def api_agregar_personal():
    data = request.get_json() or {}
    nombre   = data.get('nombre', '').strip()
    apellido = data.get('apellido', '').strip()
    cedula   = data.get('cedula', '').strip()
    area     = data.get('area', 'bodega').strip()
    alm_i    = data.get('almuerzo_inicio', '12:00').strip()
    alm_f    = data.get('almuerzo_fin', '12:30').strip()

    if not nombre:
        return jsonify({"ok": False, "msg": "Nombre requerido"})

    conn = get_db()
    try:
        conn.execute('''
            INSERT INTO personal (nombre, apellido, cedula, area, almuerzo_inicio, almuerzo_fin)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (nombre, apellido, cedula, area, alm_i, alm_f))
        conn.commit()
        return jsonify({"ok": True})
    except sqlite3.IntegrityError:
        return jsonify({"ok": False, "msg": "La cédula ya existe"})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})

#  Standard Post/Redirect endpoints 

@catalogo_bp.route('/eliminar_marca/<int:id>', methods=['POST'])
def eliminar_marca(id):
    conn = get_db()
    conn.execute('DELETE FROM marcas WHERE id=?', (id,))
    conn.commit()
    flash('Marca eliminada.', 'info')
    return redirect(url_for('catalogo.catalogo'))

@catalogo_bp.route('/eliminar_persona/<int:id>', methods=['POST'])
def eliminar_persona(id):
    conn = get_db()
    conn.execute('DELETE FROM personas WHERE id=?', (id,))
    conn.commit()
    flash('Persona eliminada.', 'info')
    return redirect(url_for('catalogo.catalogo'))

@catalogo_bp.route('/eliminar_personal/<int:id>', methods=['POST'])
def eliminar_personal(id):
    conn = get_db()
    conn.execute('DELETE FROM personal WHERE id=?', (id,))
    conn.commit()
    flash('Personal eliminado.', 'info')
    return redirect(url_for('catalogo.catalogo'))

@catalogo_bp.route('/editar_personal/<int:id>', methods=['POST'])
def editar_personal(id):
    nombre   = request.form.get('nombre', '').strip()
    apellido = request.form.get('apellido', '').strip()
    cedula   = request.form.get('cedula', '').strip()
    area     = request.form.get('area', 'bodega').strip()
    alm_i    = request.form.get('almuerzo_inicio', '12:00').strip()
    alm_f    = request.form.get('almuerzo_fin', '12:30').strip()

    conn = get_db()
    try:
        conn.execute('''
            UPDATE personal SET
                nombre=?, apellido=?, cedula=?, area=?, almuerzo_inicio=?, almuerzo_fin=?
            WHERE id=?
        ''', (nombre, apellido, cedula, area, alm_i, alm_f, id))
        conn.commit()
        flash('Personal actualizado.', 'success')
    except sqlite3.IntegrityError:
        flash('Error: La cédula ya está registrada para otro empleado.', 'error')
    except Exception as e:
        flash(f'Error al actualizar: {e}', 'error')
    
    return redirect(url_for('catalogo.catalogo'))
