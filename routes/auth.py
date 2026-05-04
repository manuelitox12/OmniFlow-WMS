"""
auth.py — Autenticación y gestión de usuarios
===============================================
Maneja login/logout, carga de usuario y empresa en cada request,
y CRUD de usuarios (solo admin).
"""
import sqlite3
import os
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, g, current_app
from werkzeug.security import check_password_hash, generate_password_hash
from database import get_db

auth_bp = Blueprint("auth", __name__)


#  Middleware: cargar usuario y empresa en cada request 
@auth_bp.before_app_request
def cargar_usuario():
    user_id = session.get("user_id")
    session_db = session.get("session_db")
    
    # AISLAMIENTO ESTRICTO: 
    # Si hay un usuario logueado en la sesión, la "etiqueta" de DB debe coincidir.
    # Si no hay etiqueta (sesión antigua) o no coincide (cambio de empresa), expulsar.
    current_db = os.path.basename(current_app.config.get('DATABASE', 'bodega.db'))
    if user_id and (session_db is None or session_db != current_db):
        session.clear()
        g.user = None
        return

    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
    else:
        conn = get_db()
        row = conn.execute(
            "SELECT id, username, nombre_completo, rol FROM usuarios WHERE id=? AND activo=1",
            (user_id,)
        ).fetchone()
        g.user = dict(row) if row else None
        # Si el usuario fue desactivado mientras tenía sesión, expulsar
        if g.user is None:
            session.clear()


@auth_bp.before_app_request
def cargar_empresa():
    """Carga g.empresa desde la tabla empresa en cada petición."""
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM empresa LIMIT 1").fetchone()
        g.empresa = dict(row) if row else None
    except Exception:
        g.empresa = None


@auth_bp.before_app_request
def proteger_rutas():
    """Redirige a login si el usuario no ha iniciado sesión."""
    rutas_publicas = ("auth.login", "static")
    if request.endpoint and request.endpoint not in rutas_publicas and g.user is None:
        return redirect(url_for("auth.login", next=request.url))


#  Login / Logout 
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("registros.registros"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            flash("Usuario y contraseña son obligatorios.", "error")
            return render_template("login.html")

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM usuarios WHERE username=? AND activo=1",
            (username,)
        ).fetchone()

        if user and check_password_hash(user["password_hash"], password):
            # Identificador de la DB actual para aislar la sesión
            current_db = os.path.basename(current_app.config.get('DATABASE', 'bodega.db'))
            
            session.clear()
            session["user_id"]    = user["id"]
            session["user_name"]  = user["nombre_completo"]
            session["user_rol"]   = user["rol"]
            session["session_db"] = current_db
            session.permanent = True
            
            flash(f"Bienvenido, {user['nombre_completo']}.", "success")
            next_url = request.args.get("next")
            return redirect(next_url or url_for("registros.registros"))

        flash("Usuario o contraseña incorrectos.", "error")

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("Has cerrado sesión exitosamente.", "info")
    return redirect(url_for("auth.login"))


#  CRUD de Usuarios (solo admin) 
@auth_bp.route("/usuarios")
def lista_usuarios():
    if not g.user or g.user.get("rol") != "admin":
        flash("Acceso denegado.", "error")
        return redirect(url_for("registros.registros"))
    conn = get_db()
    usuarios = conn.execute("SELECT * FROM usuarios ORDER BY id").fetchall()
    return render_template("usuarios.html", usuarios=usuarios)


@auth_bp.route("/usuarios/crear", methods=["POST"])
def crear_usuario():
    if not g.user or g.user.get("rol") != "admin":
        flash("Acceso denegado.", "error")
        return redirect(url_for("registros.registros"))

    username        = request.form.get("username", "").strip().lower()
    password        = request.form.get("password", "").strip()
    nombre_completo = request.form.get("nombre_completo", "").strip()
    rol             = request.form.get("rol", "bodega").strip()

    if not username or not password:
        flash("El usuario y contraseña son obligatorios.", "error")
        return redirect(url_for("auth.lista_usuarios"))
    if len(password) < 8:
        flash("La contraseña debe tener al menos 8 caracteres.", "error")
        return redirect(url_for("auth.lista_usuarios"))
    if rol not in ("admin", "oficina", "bodega"):
        rol = "bodega"

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO usuarios (username, password_hash, nombre_completo, rol, activo) VALUES (?, ?, ?, ?, 1)",
            (username, generate_password_hash(password), nombre_completo or username, rol)
        )
        conn.commit()
        flash(f" Usuario '{username}' creado con rol '{rol}'.", "success")
    except sqlite3.IntegrityError:
        flash(f" El usuario '{username}' ya existe.", "error")
    return redirect(url_for("auth.lista_usuarios"))


@auth_bp.route("/usuarios/<int:user_id>/toggle", methods=["POST"])
def toggle_usuario(user_id):
    if not g.user or g.user.get("rol") != "admin":
        flash("Acceso denegado.", "error")
        return redirect(url_for("registros.registros"))
    conn = get_db()
    user = conn.execute("SELECT activo, username FROM usuarios WHERE id=?", (user_id,)).fetchone()
    if user:
        nuevo = 0 if user["activo"] else 1
        conn.execute("UPDATE usuarios SET activo=? WHERE id=?", (nuevo, user_id))
        conn.commit()
        estado = "activado" if nuevo else "desactivado"
        flash(f"Usuario '{user['username']}' {estado}.", "info")
    return redirect(url_for("auth.lista_usuarios"))


@auth_bp.route("/usuarios/<int:user_id>/reset", methods=["POST"])
def reset_password(user_id):
    if not g.user or g.user.get("rol") != "admin":
        flash("Acceso denegado.", "error")
        return redirect(url_for("registros.registros"))
    new_password = request.form.get("new_password", "").strip()
    if len(new_password) < 8:
        flash("La contraseña debe tener al menos 8 caracteres.", "error")
        return redirect(url_for("auth.lista_usuarios"))
    conn = get_db()
    conn.execute(
        "UPDATE usuarios SET password_hash=? WHERE id=?",
        (generate_password_hash(new_password), user_id)
    )
    conn.commit()
    flash(" Contraseña restablecida.", "success")
    return redirect(url_for("auth.lista_usuarios"))
