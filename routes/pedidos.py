"""
pedidos.py — Creación y gestión del ciclo de vida de pedidos
=============================================================
Incluye: registrar nuevo, iniciar/terminar empaque, retirar,
         soft-delete, restaurar, y reset de empaque.
"""
from flask import Blueprint, request, redirect, url_for, flash, jsonify
from datetime import datetime
from database import get_db
from services.auditoria import registrar_cambio

pedidos_bp = Blueprint('pedidos', __name__)


@pedidos_bp.route('/registrar', methods=['POST'])
def registrar():
    marca = request.form.get('marca', '').strip()
    tipo  = request.form.get('tipo', 'empaque').strip()
    if not marca:
        flash('La marca es obligatoria.', 'error')
        return redirect(url_for('main.index'))
    if tipo not in ('empaque', 'directo'):
        tipo = 'empaque'
    fecha_prefix = datetime.now().strftime('%Y-%m')
    fecha_full   = datetime.now().strftime('%Y-%m-%d %H:%M')
    
    conn  = get_db()
    
    #  Calcular Siguiente correlativo_mes 
    # Buscamos el máximo correlativo del mes actual (según el prefijo YYYY-MM)
    row_correlativo = conn.execute(
        "SELECT MAX(correlativo_mes) as max_corr FROM pedidos WHERE tipo='empaque' AND eliminado=0 AND fecha LIKE ?",
        (f"{fecha_prefix}%",)
    ).fetchone()
    
    prox_correlativo = 1
    if row_correlativo and row_correlativo["max_corr"]:
        prox_correlativo = row_correlativo["max_corr"] + 1

    cur = conn.execute(
        """INSERT INTO pedidos 
           (marca, bultos, tipo, retirado_por, fecha, estado, eliminado, correlativo_mes) 
           VALUES (?, NULL, ?, NULL, ?, 'pendiente', 0, ?)""",
        (marca, tipo, fecha_full, prox_correlativo if tipo == 'empaque' else None)
    )
    nuevo_id = cur.lastrowid
    
    # AUDITORÍA: Creación
    registrar_cambio(conn, "pedidos", nuevo_id, "estado", None, "pendiente")
    registrar_cambio(conn, "pedidos", nuevo_id, "marca",  None, marca)
    
    conn.commit()
    
    tipo_label = " con empaque" if tipo == "empaque" else " retiro directo"
    flash(f' Pedido de {marca} creado (#{prox_correlativo}) — {tipo_label}.', 'success')
    return redirect(url_for('registros.detalle_pedido', pedido_id=nuevo_id))


@pedidos_bp.route('/iniciar_empaque/<int:id>', methods=['POST'])
def iniciar_empaque(id):
    conn   = get_db()
    pedido = conn.execute(
        "SELECT estado, tipo FROM pedidos WHERE id=? AND eliminado=0", (id,)
    ).fetchone()
    if not pedido:
        flash("Pedido no encontrado.", "error")
    elif pedido["tipo"] == "directo":
        flash(" Este pedido es de retiro directo y no requiere empaque.", "error")
    elif pedido["estado"] != "pendiente":
        flash("Solo se puede iniciar empaque en pedidos pendientes.", "error")
    else:
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("UPDATE pedidos SET estado='empacando', inicio_empaque=? WHERE id=?", (ahora, id))
        conn.commit()
        flash(" Empaque iniciado.", "success")
    return redirect(url_for("registros.registros"))


@pedidos_bp.route('/terminar_empaque/<int:id>', methods=['POST'])
def terminar_empaque(id):
    conn   = get_db()
    pedido = conn.execute(
        "SELECT estado, tipo, bultos FROM pedidos WHERE id=? AND eliminado=0", (id,)
    ).fetchone()
    if not pedido:
        flash("Pedido no encontrado.", "error")
    elif pedido["tipo"] == "directo":
        flash(" Este pedido es de retiro directo y no requiere empaque.", "error")
    elif pedido["estado"] != "empacando":
        flash("Solo se puede terminar empaque en pedidos que están empacando.", "error")
    elif not pedido["bultos"]:
        flash(" Debes registrar la cantidad de bultos antes de terminar el empaque.", "error")
        return redirect(url_for("registros.detalle_pedido", pedido_id=id))
    else:
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("UPDATE pedidos SET estado='empacado', fin_empaque=? WHERE id=?", (ahora, id))
        conn.commit()
        flash("⏹ Empaque terminado. Listo para retirar.", "success")
    return redirect(url_for("registros.registros"))


@pedidos_bp.route('/retirar/<int:id>', methods=['GET', 'POST'])
def confirmar_retiro_pedido(id):
    if request.method == 'GET':
        return redirect(url_for("registros.registros"))

    conn   = get_db()
    pedido = conn.execute(
        "SELECT estado, tipo, marca FROM pedidos WHERE id=? AND eliminado=0", (id,)
    ).fetchone()
    
    retirado_por = request.form.get("retirado_por", "").strip()
    bultos_final = request.form.get("bultos", "").strip()
    fecha_manual = request.form.get("retirado_en", "").strip() # YYYY-MM-DDTHH:MM

    if not pedido:
        flash("Pedido no encontrado.", "error")
        return redirect(url_for("registros.registros"))

    tipo = pedido["tipo"]; estado = pedido["estado"]; marca = pedido["marca"]

    if tipo == "empaque" and estado != "empacado":
        flash(" Los pedidos de empaque solo pueden retirarse cuando están empacados.", "error")
        return redirect(url_for("registros.registros"))
    if tipo == "directo" and estado != "pendiente":
        flash(" Este pedido directo ya fue procesado.", "error")
        return redirect(url_for("registros.registros"))
    if not retirado_por:
        flash("Debes indicar quién retira el pedido.", "error")
        return redirect(url_for("registros.registros"))

    # Determinar fecha/hora de retiro
    if fecha_manual:
        # datetime-local envía T como separador
        ahora = fecha_manual.replace("T", " ")
        if len(ahora) == 16: ahora += ":00"
    else:
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Si se pasaron bultos por el modal (porque no estaban), los guardamos
    if bultos_final and bultos_final.isdigit():
        conn.execute("UPDATE pedidos SET bultos=? WHERE id=?", (int(bultos_final), id))
    
    conn.execute(
        "UPDATE pedidos SET estado='retirado', retirado_por=?, retirado_en=? WHERE id=?",
        (retirado_por, ahora, id)
    )
    conn.commit()
    flash(f" Pedido de {marca} retirado por {retirado_por}.", "success")
    return redirect(url_for("registros.registros"))


@pedidos_bp.route('/pedido/<int:id>/editar_retiro', methods=['POST'])
def editar_retiro(id):
    """Actualiza los datos de un pedido que ya fue retirado."""
    conn = get_db()
    retirado_por = request.form.get("retirado_por", "").strip()
    fecha_manual = request.form.get("retirado_en", "").strip()
    
    if not retirado_por:
        flash("El nombre de quien retira es obligatorio.", "error")
        return redirect(url_for("registros.registros"))
        
    if fecha_manual:
        ahora = fecha_manual.replace("T", " ")
        if len(ahora) == 16: ahora += ":00"
    else:
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
    conn.execute(
        "UPDATE pedidos SET retirado_por=?, retirado_en=? WHERE id=? AND estado='retirado'",
        (retirado_por, ahora, id)
    )
    conn.commit()
    flash(" Datos de retiro actualizados.", "success")
    return redirect(url_for("registros.registros"))


@pedidos_bp.route('/pedido/<int:id>/deshacer_retiro', methods=['POST'])
def deshacer_retiro(id):
    """Deshace el retiro de un pedido y lo devuelve al tablero activo."""
    conn = get_db()
    pedido = conn.execute("SELECT marca, tipo, inicio_empaque, fin_empaque, bultos FROM pedidos WHERE id=?", (id,)).fetchone()
    if not pedido:
        flash("Pedido no encontrado.", "error")
        return redirect(url_for("registros.registros"))
        
    # Calcular estado previo
    if pedido['tipo'] == 'directo':
        nuevo_estado = 'pendiente'
    else:
        if pedido['fin_empaque']:
            if pedido['bultos'] and int(pedido['bultos']) > 0:
                nuevo_estado = 'empacado'
            else:
                nuevo_estado = 'empacando'
        elif pedido['inicio_empaque']:
            nuevo_estado = 'empacando'
        else:
            nuevo_estado = 'pendiente'
            
    conn.execute(
        "UPDATE pedidos SET estado=?, retirado_por=NULL, retirado_en=NULL WHERE id=?",
        (nuevo_estado, id)
    )
    conn.commit()
    flash(f"↩ Retiro de {pedido['marca']} deshecho. El pedido ha vuelto al tablero.", "success")
    return redirect(url_for("registros.registros"))



@pedidos_bp.route('/retirar/batch', methods=['POST'])
def confirmar_retiro_batch():
    ids_str      = request.form.get("ids", "").strip()
    retirado_por = request.form.get("retirado_por", "").strip()
    fecha_manual = request.form.get("retirado_en", "").strip()

    if not ids_str:
        flash("No se seleccionaron pedidos.", "error")
        return redirect(url_for("registros.registros"))
    
    if not retirado_por:
        flash("Debes indicar quién retira los pedidos.", "error")
        return redirect(url_for("registros.registros"))

    ids = [int(i) for i in ids_str.split(",") if i.isdigit()]
    if not ids:
        flash("IDs inválidos.", "error")
        return redirect(url_for("registros.registros"))

    # Determinar fecha/hora
    if fecha_manual:
        ahora = fecha_manual.replace("T", " ")
        if len(ahora) == 16: ahora += ":00"
    else:
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db()
    count = 0
    for pedido_id in ids:
        # Solo actualizamos si el pedido existe y no está eliminado
        # Podríamos añadir validación de estado aquí si quisiéramos ser estrictos
        conn.execute(
            "UPDATE pedidos SET estado='retirado', retirado_por=?, retirado_en=? WHERE id=? AND eliminado=0",
            (retirado_por, ahora, pedido_id)
        )
        count += 1
    
    conn.commit()
    flash(f" {count} pedidos marcados como retirados por {retirado_por}.", "success")
    return redirect(url_for("registros.registros"))


@pedidos_bp.route('/pedido/<int:pedido_id>', methods=['POST'])
def actualizar_pedido(pedido_id):
    """Guarda la información general del pedido (header)."""
    conn = get_db()
    
    # Datos de fecha de recibido
    rec_fecha = request.form.get("recibido_fecha", "").strip() # YYYY-MM-DD
    rec_hora  = request.form.get("recibido_hora_picker", "").strip() # HH:MM
    
    ano, mes, dia = (None, None, None)
    if rec_fecha:
        parts = rec_fecha.split("-")
        if len(parts) == 3:
            ano, mes, dia = parts
            
    # Tiempos de empaque
    ini_emp = request.form.get("inicio_empaque", "").strip().replace("T", " ")
    fin_emp = request.form.get("fin_empaque", "").strip().replace("T", " ")
    
    # Checkboxes
    es_extra = 1 if request.form.get("es_hora_extra") else 0
    sab_repo = 1 if request.form.get("sabado_reposicion") else 0
    
    # Otros campos
    bultos       = request.form.get("bultos")
    hojas        = request.form.get("hojas", "").strip()
    empacador_id = request.form.get("empacador_id")
    digitado_por = request.form.get("digitado_por", "").strip()
    observacion  = request.form.get("observacion", "").strip()
    tipo         = request.form.get("tipo", "empaque")
    
    #  CARGAR DATOS ACTUALES PARA COMPARAR 
    old_row = conn.execute("SELECT * FROM pedidos WHERE id=?", (pedido_id,)).fetchone()
    if not old_row:
        flash(" Error: Pedido no encontrado.", "error")
        return redirect(url_for("registros.registros"))

    #  GESTIÓN DE CORRELATIVO (Si cambia de Directo a Empaque) 
    nuevo_correlativo = old_row['correlativo_mes']
    if tipo == 'empaque' and not nuevo_correlativo:
        fecha_prefix = datetime.now().strftime('%Y-%m')
        row_max = conn.execute(
            "SELECT MAX(correlativo_mes) as max_corr FROM pedidos WHERE tipo='empaque' AND eliminado=0 AND fecha LIKE ?",
            (f"{fecha_prefix}%",)
        ).fetchone()
        nuevo_correlativo = (row_max["max_corr"] or 0) + 1

    #  LÓGICA DE ESTADOS AUTOMÁTICOS 
    nuevo_estado = old_row['estado']
    if nuevo_estado != 'retirado':
        if fin_emp:
            # Regla: Se necesitan bultos para marcar como empacado
            if bultos and bultos.strip() != "" and int(bultos) > 0:
                nuevo_estado = 'empacado'
            else:
                nuevo_estado = 'empacando'
                flash(" Nota: El estado sigue en 'Empacando' porque se requieren bultos para finalizar el empaque.", "warning")
        elif ini_emp:
            nuevo_estado = 'empacando'
        else:
            nuevo_estado = 'pendiente'

    #  VALIDACIÓN 
    try:
        ahora = datetime.now()
        if ini_emp:
            dt_ini = datetime.strptime(ini_emp, "%Y-%m-%d %H:%M:%S")
            if dt_ini > ahora:
                flash(" Error: La fecha de inicio no puede ser en el futuro.", "error")
                return redirect(url_for("registros.detalle_pedido", pedido_id=pedido_id))
        if fin_emp:
            dt_fin = datetime.strptime(fin_emp, "%Y-%m-%d %H:%M:%S")
            if dt_fin > ahora:
                flash(" Error: La fecha de fin no puede ser en el futuro.", "error")
                return redirect(url_for("registros.detalle_pedido", pedido_id=pedido_id))
            if ini_emp:
                dt_ini = datetime.strptime(ini_emp, "%Y-%m-%d %H:%M:%S")
                if dt_fin < dt_ini:
                    flash(" Error: La hora de fin de empaque no puede ser anterior a la de inicio.", "error")
                    return redirect(url_for("registros.detalle_pedido", pedido_id=pedido_id))
    except ValueError:
        pass # Formato inválido capturado luego por la DB o ignorado

    #  AUDITORÍA DE CAMBIOS 
    if old_row:
        if nuevo_estado != old_row['estado']:
            registrar_cambio(conn, "pedidos", pedido_id, "estado", old_row["estado"], nuevo_estado)
        
        registrar_cambio(conn, "pedidos", pedido_id, "inicio_empaque", old_row["inicio_empaque"], ini_emp or None)
        registrar_cambio(conn, "pedidos", pedido_id, "fin_empaque",    old_row["fin_empaque"],    fin_emp or None)
        registrar_cambio(conn, "pedidos", pedido_id, "bultos",         old_row["bultos"],         int(bultos) if bultos else None)
        registrar_cambio(conn, "pedidos", pedido_id, "digitado_por",   old_row["digitado_por"],   digitado_por)

    #  OBTENER NOMBRE DEL EMPACADOR (para dictado_por) 
    dictado_por = request.form.get("dictado_por", "").strip()
    if empacador_id and not dictado_por:
        p_row = conn.execute("SELECT nombre, apellido FROM personal WHERE id=?", (empacador_id,)).fetchone()
        if p_row:
            dictado_por = f"{p_row['nombre']} {p_row['apellido']}".strip()

    sql = """
        UPDATE pedidos SET
            recibido_ano=?, recibido_mes=?, recibido_dia=?, recibido_hora=?,
            inicio_empaque=?, fin_empaque=?,
            es_hora_extra=?, sabado_reposicion=?,
            bultos=?, hojas=?, empacador_id=?, digitado_por=?, dictado_por=?, observacion=?,
            tipo=?, estado=?, correlativo_mes=?,
            preparador_nombre=?, preparador_id=?, inicio_preparacion=?, fin_preparacion=?
        WHERE id=?
    """
    #  GESTIÓN DE PREPARACION GLOBAL (Preservar si no vienen en el form) 
    prep_nom = request.form.get("preparador_nombre")
    if prep_nom is None:
        # No vienen en el form, mantenemos lo que hay en DB
        prep_nom = old_row["preparador_nombre"]
        prep_id  = old_row["preparador_id"]
        ini_prep = old_row["inicio_preparacion"]
        fin_prep = old_row["fin_preparacion"]
    else:
        # Vienen en el form (probablemente desde edición manual)
        prep_nom = prep_nom.strip()
        prep_id  = request.form.get("preparador_id")
        if prep_nom and not prep_id:
            p_row = conn.execute("SELECT id FROM personal WHERE (nombre || ' ' || apellido) = ? OR nombre = ? LIMIT 1", (prep_nom, prep_nom)).fetchone()
            if p_row: prep_id = p_row["id"]
        
        ini_prep = request.form.get("inicio_preparacion", "").strip().replace("T", " ")
        fin_prep = request.form.get("fin_preparacion", "").strip().replace("T", " ")

    conn.execute(sql, (
        ano, mes, dia, rec_hora,
        ini_emp or None, fin_emp or None,
        es_extra, sab_repo,
        int(bultos) if bultos else None,
        hojas,
        int(empacador_id) if empacador_id else None,
        digitado_por,
        dictado_por,
        observacion,
        tipo if tipo in ('empaque', 'directo') else 'empaque',
        nuevo_estado,
        nuevo_correlativo,
        prep_nom or None,
        int(prep_id) if prep_id else None,
        ini_prep or None,
        fin_prep or None,
        pedido_id
    ))
    conn.commit()
    
    flash(" Información del pedido actualizada.", "success")
    return redirect(url_for("registros.detalle_pedido", pedido_id=pedido_id))


@pedidos_bp.route('/pedido/<int:pedido_id>/reset_empaque', methods=['POST'])
def reset_empaque(pedido_id):
    conn = get_db()
    conn.execute(
        "UPDATE pedidos SET estado='pendiente', inicio_empaque=NULL, fin_empaque=NULL WHERE id=? AND eliminado=0",
        (pedido_id,)
    )
    conn.commit()
    flash("↺ Pedido reiniciado a pendiente.", "info")
    return redirect(url_for("registros.registros"))


#  SECCIONES / PASILLOS 

@pedidos_bp.route('/api/pedido/<int:id>/secciones', methods=['GET'])
def get_secciones_json(id):
    conn = get_db()
    rows = conn.execute(
        "SELECT id, seccion_num, inicio, fin, persona FROM pedido_secciones WHERE pedido_id=? AND bloque_tipo='pedido' ORDER BY id",
        (id,)
    ).fetchall()
    
    res = {str(n): [] for n in range(1, 6)}
    for r in rows:
        res[str(r["seccion_num"])].append(dict(r))
    return jsonify(res)

# Las rutas legacy han sido eliminadas. Ahora se usa update_seccion_record via ID de registro.

@pedidos_bp.route('/api/seccion_record/<int:record_id>', methods=['POST'])
def update_seccion_record(record_id):
    """Actualiza una fila de sección específica por su ID único."""
    return _update_record(record_id, request.json)

def _update_record(record_id, data):
    tipo_campo = data.get("tipo_campo")
    valor      = data.get("valor")
    persona    = data.get("persona", "").strip()
    
    # Validar que si hay tiempo, hay persona
    if tipo_campo in ['inicio', 'fin'] and valor and not persona:
        return {"error": "Debe asignar un Responsable antes de marcar el tiempo."}

    conn = get_db()
    
    #  AUDITORÍA E INTEGRIDAD 
    old_row = conn.execute("SELECT * FROM pedido_secciones WHERE id=?", (record_id,)).fetchone()
    if not old_row:
        return {"error": "Registro no encontrado"}

    # Normalizar valor de tiempo si aplica
    if valor == "now":
        valor = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    elif valor and tipo_campo in ['inicio', 'fin']:
        valor = valor.replace("T", " ")
        if len(valor) == 16: valor += ":00"

    # Validación de tiempos
    try:
        if valor and tipo_campo in ['inicio', 'fin']:
            ahora = datetime.now()
            dt_nuevo = datetime.strptime(valor, "%Y-%m-%d %H:%M:%S")
            if dt_nuevo > ahora:
                return {"error": "La fecha no puede ser en el futuro."}
            
            # Comparar inicio vs fin
            if tipo_campo == 'inicio' and old_row['fin']:
                dt_fin = datetime.strptime(old_row['fin'], "%Y-%m-%d %H:%M:%S")
                if dt_nuevo > dt_fin:
                    return {"error": "La hora de inicio no puede ser posterior a la de fin."}
            elif tipo_campo == 'fin' and old_row['inicio']:
                dt_ini = datetime.strptime(old_row['inicio'], "%Y-%m-%d %H:%M:%S")
                if dt_nuevo < dt_ini:
                    return {"error": "La hora de fin no puede ser anterior a la de inicio."}
    except ValueError:
        pass

    # Registro de auditoría
    if tipo_campo:
        registrar_cambio(conn, "pedido_secciones", record_id, tipo_campo, old_row[tipo_campo], valor)
    if persona != old_row["persona"]:
        registrar_cambio(conn, "pedido_secciones", record_id, "persona", old_row["persona"], persona)

    #  ACTUALIZACIÓN 
    # Buscar el personal_id basado en el nombre (persona)
    personal_id = None
    if persona:
        p_row = conn.execute(
            "SELECT id FROM personal WHERE (nombre || ' ' || apellido) = ? OR nombre = ? LIMIT 1",
            (persona, persona)
        ).fetchone()
        if p_row:
            personal_id = p_row["id"]

    if tipo_campo:
        conn.execute(f"UPDATE pedido_secciones SET {tipo_campo}=?, persona=?, personal_id=? WHERE id=?", 
                     (valor, persona, personal_id, record_id))
    else:
        conn.execute("UPDATE pedido_secciones SET persona=?, personal_id=? WHERE id=?", 
                     (persona, personal_id, record_id))
    
    conn.commit()
    row = conn.execute("SELECT id, seccion_num, inicio, fin, persona FROM pedido_secciones WHERE id=?", (record_id,)).fetchone()
    return jsonify({**dict(row), "ok": True})

@pedidos_bp.route('/api/pedido/<int:id>/seccion/<int:sec_num>/nueva', methods=['POST'])
def nueva_parte_seccion(id, sec_num):
    """Crea una nueva fila (parte) para una sección existente."""
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO pedido_secciones (pedido_id, seccion_num, bloque_tipo) VALUES (?, ?, 'pedido')",
        (id, sec_num)
    )
    new_id = cur.lastrowid
    conn.commit()
    row = conn.execute("SELECT * FROM pedido_secciones WHERE id=?", (new_id,)).fetchone()
    return jsonify({**dict(row), "ok": True})

@pedidos_bp.route('/api/seccion_record/<int:record_id>/limpiar', methods=['POST'])
def limpiar_seccion_record(record_id):
    conn = get_db()
    # Si hay más de una parte para esta sección, tal vez queremos ELIMINAR la fila en vez de solo limpiarla
    row = conn.execute("SELECT pedido_id, seccion_num, bloque_tipo FROM pedido_secciones WHERE id=?", (record_id,)).fetchone()
    if row:
        # Contar cuántas partes tiene esta sección
        count = conn.execute(
            "SELECT COUNT(*) as c FROM pedido_secciones WHERE pedido_id=? AND seccion_num=? AND bloque_tipo=?",
            (row["pedido_id"], row["seccion_num"], row["bloque_tipo"])
        ).fetchone()["c"]
        
        if count > 1:
            conn.execute("DELETE FROM pedido_secciones WHERE id=?", (record_id,))
            conn.commit()
            return jsonify({"ok": True, "deleted": True})
            
    conn.execute("UPDATE pedido_secciones SET inicio=NULL, fin=NULL, persona=NULL WHERE id=?", (record_id,))
    conn.commit()
    return jsonify({"ok": True})


@pedidos_bp.route('/api/pedido/<int:id>/seccion/batch', methods=['POST'])
def update_secciones_batch(id):
    """Actualiza múltiples secciones (pasillos) a la vez."""
    data = request.json
    ids_data     = data.get("ids", []) # Lista de {record_id: X} o {sec_num: Y}
    persona      = data.get("persona", "").strip()
    valor_manual = data.get("valor", "").strip()
    auto_inicio  = data.get("auto_inicio", False)
    
    if not persona:
        return jsonify({"ok": False, "msg": "Debe indicar un responsable."})

    conn = get_db()
    
    # Buscar personal_id
    personal_id = None
    p_row = conn.execute(
        "SELECT id FROM personal WHERE (nombre || ' ' || apellido) = ? OR nombre = ? LIMIT 1",
        (persona, persona)
    ).fetchone()
    if p_row:
        personal_id = p_row["id"]

    # Determinar el tiempo a asignar
    if valor_manual:
        tiempo_final = valor_manual.replace("T", " ")
        if len(tiempo_final) == 16: tiempo_final += ":00"
    else:
        tiempo_final = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    count = 0
    for item in ids_data:
        record_id = item.get("record_id")
        sec_num   = item.get("sec_num")
        
        if record_id:
            # Actualizar registro existente
            if auto_inicio or valor_manual:
                conn.execute(
                    "UPDATE pedido_secciones SET persona=?, personal_id=?, inicio=COALESCE(inicio, ?) WHERE id=?",
                    (persona, personal_id, tiempo_final, record_id)
                )
            else:
                conn.execute(
                    "UPDATE pedido_secciones SET persona=?, personal_id=? WHERE id=?",
                    (persona, personal_id, record_id)
                )
            count += 1
        elif sec_num:
            # Crear y asignar
            cur = conn.execute(
                "INSERT INTO pedido_secciones (pedido_id, seccion_num, bloque_tipo, persona, personal_id, inicio) VALUES (?, ?, 'pedido', ?, ?, ?)",
                (id, sec_num, persona, personal_id, tiempo_final if (auto_inicio or valor_manual) else None)
            )
            count += 1

    conn.commit()
    return jsonify({"ok": True, "count": count})


# Las rutas de limpieza legacy se han removido.

@pedidos_bp.route('/api/pedido/<int:id>/marca', methods=['POST'])
def editar_marca_api(id):
    nueva_marca = request.json.get("marca", "").strip()
    if not nueva_marca:
        return jsonify({"ok": False, "msg": "Nombre vacío"})
    conn = get_db()
    conn.execute("UPDATE pedidos SET marca=? WHERE id=?", (nueva_marca, id))
    conn.commit()
    return jsonify({"ok": True, "marca": nueva_marca})

@pedidos_bp.route('/pedido/<int:id>/secciones/bulk', methods=['POST'])
def secciones_bulk(id):
    tipo_campo = request.form.get("tipo_campo")
    valor      = request.form.get("valor", "").strip()
    
    if not valor or valor == "":
        valor = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    else:
        valor = valor.replace("T", " ")
        if len(valor) == 16: valor += ":00"

    conn = get_db()
    for n in range(1, 6):
        exists = conn.execute(
            "SELECT 1 FROM pedido_secciones WHERE pedido_id=? AND seccion_num=? AND bloque_tipo='pedido'",
            (id, n)
        ).fetchone()
        
        if not exists:
            conn.execute("INSERT INTO pedido_secciones (pedido_id, seccion_num, bloque_tipo) VALUES (?, ?, 'pedido')", (id, n))
            
        update_sql = f"UPDATE pedido_secciones SET {tipo_campo}=? WHERE pedido_id=? AND seccion_num=? AND bloque_tipo='pedido'"
        conn.execute(update_sql, (valor, id, n))
    
    conn.commit()
    flash(f" Secciones actualizadas en lote ({tipo_campo}).", "info")
    return redirect(url_for("registros.detalle_pedido", pedido_id=id))


@pedidos_bp.route('/api/pedido/<int:id>/preparacion_global', methods=['POST'])
def preparacion_global_api(id):
    """API para registrar el reclamo o finalización de la preparación global."""
    data = request.json
    tipo_campo = data.get("tipo_campo") # 'inicio' o 'fin' o 'eliminar'
    valor      = data.get("valor")
    persona    = data.get("persona", "").strip()

    conn = get_db()
    if tipo_campo == 'eliminar':
        conn.execute("UPDATE pedidos SET preparador_nombre=NULL, preparador_id=NULL, inicio_preparacion=NULL, fin_preparacion=NULL WHERE id=?", (id,))
        conn.commit()
        return jsonify({"ok": True})

    if valor == "now" or not valor:
        valor = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    else:
        valor = valor.replace("T", " ")
        if len(valor) == 16: valor += ":00"

    # Buscar personal_id
    personal_id = None
    if persona:
        p_row = conn.execute("SELECT id FROM personal WHERE (nombre || ' ' || apellido) = ? OR nombre = ? LIMIT 1", (persona, persona)).fetchone()
        if p_row: personal_id = p_row["id"]

    if tipo_campo == 'inicio':
        if not persona:
            # Si solo estamos actualizando la hora (edición manual), no borremos al encargado
            conn.execute("UPDATE pedidos SET inicio_preparacion=? WHERE id=?", (valor, id))
        else:
            conn.execute("UPDATE pedidos SET preparador_nombre=?, preparador_id=?, inicio_preparacion=? WHERE id=?", (persona, personal_id, valor, id))
    elif tipo_campo == 'fin':
        if not persona:
             conn.execute("UPDATE pedidos SET fin_preparacion=? WHERE id=?", (valor, id))
        else:
             conn.execute("UPDATE pedidos SET fin_preparacion=?, preparador_nombre=?, preparador_id=? WHERE id=?", (valor, persona, personal_id, id))

    conn.commit()
    row = conn.execute("SELECT preparador_nombre, inicio_preparacion, fin_preparacion FROM pedidos WHERE id=?", (id,)).fetchone()
    return jsonify({**dict(row), "ok": True})

#  MODO HOJAS (Dinámico) 


@pedidos_bp.route('/api/pedido/<int:id>/hoja/batch', methods=['POST'])
def update_hojas_batch(id):
    """Actualiza múltiples hojas a la vez (asignación masiva)."""
    data = request.json
    ids_data     = data.get("ids", []) # Lista de {record_id: X} o {hoja_num: Y}
    persona      = data.get("persona", "").strip()
    valor_manual = data.get("valor", "").strip()
    auto_inicio  = data.get("auto_inicio", False)
    
    if not persona:
        return jsonify({"ok": False, "msg": "Debe indicar un responsable."})

    conn = get_db()
    
    # Buscar personal_id
    personal_id = None
    p_row = conn.execute(
        "SELECT id FROM personal WHERE (nombre || ' ' || apellido) = ? OR nombre = ? LIMIT 1",
        (persona, persona)
    ).fetchone()
    if p_row:
        personal_id = p_row["id"]

    # Determinar el tiempo a asignar
    if valor_manual:
        tiempo_final = valor_manual.replace("T", " ")
        if len(tiempo_final) == 16: tiempo_final += ":00"
    else:
        tiempo_final = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    count = 0
    for item in ids_data:
        record_id = item.get("record_id")
        hoja_num  = item.get("hoja_num")
        
        if record_id:
            # Actualizar registro existente
            if auto_inicio or valor_manual:
                conn.execute(
                    "UPDATE pedido_hojas SET persona=?, personal_id=?, inicio=COALESCE(inicio, ?) WHERE id=?",
                    (persona, personal_id, tiempo_final, record_id)
                )
            else:
                conn.execute(
                    "UPDATE pedido_hojas SET persona=?, personal_id=? WHERE id=?",
                    (persona, personal_id, record_id)
                )
            count += 1
        elif hoja_num:
            # Crear y asignar
            cur = conn.execute(
                "INSERT INTO pedido_hojas (pedido_id, hoja_num, persona, personal_id, inicio) VALUES (?, ?, ?, ?, ?)",
                (id, hoja_num, persona, personal_id, tiempo_final if (auto_inicio or valor_manual) else None)
            )
            count += 1

    conn.commit()
    return jsonify({"ok": True, "count": count})

@pedidos_bp.route('/api/pedido/<int:id>/modo_preparacion', methods=['POST'])
def cambiar_modo_preparacion(id):
    nuevo_modo = request.json.get("modo", "SECCIONES")
    if nuevo_modo not in ("SECCIONES", "HOJAS"):
        return jsonify({"ok": False, "msg": "Modo inválido"})
    conn = get_db()
    conn.execute("UPDATE pedidos SET modo_preparacion=? WHERE id=?", (nuevo_modo, id))
    conn.commit()
    return jsonify({"ok": True, "modo": nuevo_modo})

@pedidos_bp.route('/api/hoja_record/<int:record_id>', methods=['POST'])
def update_hoja_record(record_id):
    """Actualiza campos (inicio, fin, persona) en un registro de hoja puntual."""
    data = request.json
    tipo_campo = data.get("tipo_campo") # 'inicio' o 'fin' (puede no venir para update de nombre solo)
    valor      = data.get("valor")
    persona    = data.get("persona", "").strip()

    conn = get_db()
    if valor == "now":
        valor = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    elif valor:
        valor = valor.replace("T", " ")
        if len(valor) == 16: valor += ":00"

    personal_id = None
    if persona:
        p_row = conn.execute(
            "SELECT id FROM personal WHERE (nombre || ' ' || apellido) = ? OR nombre = ? LIMIT 1",
            (persona, persona)
        ).fetchone()
        if p_row:
            personal_id = p_row["id"]

    if tipo_campo:
        conn.execute(f"UPDATE pedido_hojas SET {tipo_campo}=?, persona=?, personal_id=? WHERE id=?", 
                     (valor, persona, personal_id, record_id))
    else:
        conn.execute("UPDATE pedido_hojas SET persona=?, personal_id=? WHERE id=?", 
                     (persona, personal_id, record_id))
    
    conn.commit()
    row = conn.execute("SELECT id, hoja_num, inicio, fin, persona FROM pedido_hojas WHERE id=?", (record_id,)).fetchone()
    return jsonify({**dict(row), "ok": True})

@pedidos_bp.route('/api/pedido/<int:id>/hoja/<int:hoja_num>/nueva', methods=['POST'])
def nueva_parte_hoja(id, hoja_num):
    """Crea una fila nueva para una hoja."""
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO pedido_hojas (pedido_id, hoja_num) VALUES (?, ?)",
        (id, hoja_num)
    )
    new_id = cur.lastrowid
    conn.commit()
    row = conn.execute("SELECT * FROM pedido_hojas WHERE id=?", (new_id,)).fetchone()
    return jsonify({**dict(row), "ok": True})

@pedidos_bp.route('/api/hoja_record/<int:record_id>/limpiar', methods=['POST'])
def limpiar_hoja_record(record_id):
    conn = get_db()
    row = conn.execute("SELECT pedido_id, hoja_num FROM pedido_hojas WHERE id=?", (record_id,)).fetchone()
    if row:
        count = conn.execute(
            "SELECT COUNT(*) as c FROM pedido_hojas WHERE pedido_id=? AND hoja_num=?",
            (row["pedido_id"], row["hoja_num"])
        ).fetchone()["c"]
        
        if count > 1:
            conn.execute("DELETE FROM pedido_hojas WHERE id=?", (record_id,))
            conn.commit()
            return jsonify({"ok": True, "deleted": True})
            
    conn.execute("UPDATE pedido_hojas SET inicio=NULL, fin=NULL, persona=NULL WHERE id=?", (record_id,))
    conn.commit()
    return jsonify({"ok": True})

#  ANEXOS 


@pedidos_bp.route('/pedido/<int:id>/anexo', methods=['POST'])
def agregar_anexo(id):
    cant  = request.form.get("cantidad_bultos", "0")
    hojas = request.form.get("hojas", "").strip()
    obs   = request.form.get("observacion", "").strip()
    dig_p = request.form.get("digitado_por", "").strip()
    
    if not dig_p:
        from flask import flash
        flash(" Error: El responsable de digitación es obligatorio para anexos.", "error")
        return redirect(url_for("registros.detalle_pedido", pedido_id=id))

    conn = get_db()
    conn.execute(
        "INSERT INTO pedido_anexos (pedido_id, cantidad_bultos, hojas, observacion, digitado_por) VALUES (?, ?, ?, ?, ?)",
        (id, int(cant), hojas, obs, dig_p)
    )
    conn.commit()
    flash(" Anexo agregado.", "success")
    return redirect(url_for("registros.detalle_pedido", pedido_id=id))

@pedidos_bp.route('/pedido/<int:id>/anexo/<int:anx_id>/editar', methods=['POST'])
def editar_anexo(id, anx_id):
    cant  = request.form.get("cantidad_bultos", "0")
    hojas = request.form.get("hojas", "").strip()
    obs   = request.form.get("observacion", "").strip()
    dig_p = request.form.get("digitado_por", "").strip()
    
    r_mes = request.form.get("recibido_mes", "").strip()
    r_dia = request.form.get("recibido_dia", "").strip()
    r_ano = request.form.get("recibido_ano", "").strip()
    r_hor = request.form.get("recibido_hora", "").strip()
    
    d_ini = request.form.get("digitacion_inicio", "").strip().replace("T", " ")
    d_fin = request.form.get("digitacion_fin", "").strip().replace("T", " ")
    
    conn = get_db()
    conn.execute("""
        UPDATE pedido_anexos SET
            cantidad_bultos=?, hojas=?, observacion=?, digitado_por=?,
            recibido_mes=?, recibido_dia=?, recibido_ano=?, recibido_hora=?,
            digitacion_inicio=?, digitacion_fin=?
        WHERE id=? AND pedido_id=?
    """, (int(cant), hojas, obs, dig_p, r_mes, r_dia, r_ano, r_hor, d_ini, d_fin, anx_id, id))
    conn.commit()
    flash(" Anexo actualizado.", "success")
    return redirect(url_for("registros.detalle_pedido", pedido_id=id))

@pedidos_bp.route('/pedido/<int:id>/anexo/<int:anx_id>/eliminar', methods=['POST'])
def eliminar_anexo(id, anx_id):
    conn = get_db()
    conn.execute("DELETE FROM pedido_anexos WHERE id=? AND pedido_id=?", (anx_id, id))
    conn.execute("DELETE FROM pedido_secciones WHERE bloque_tipo='anexo' AND bloque_ref_id=?", (anx_id,))
    conn.commit()
    flash(" Anexo eliminado.", "info")
    return redirect(url_for("registros.detalle_pedido", pedido_id=id))

@pedidos_bp.route('/pedido/<int:id>/anexo/<int:anx_id>/seccion/<int:sec_num>', methods=['POST'])
def save_seccion_anexo(id, anx_id, sec_num):
    tipo_campo = request.form.get("tipo_campo")
    valor      = request.form.get("valor", "").strip()
    
    if valor == "now":
        valor = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    else:
        valor = valor.replace("T", " ")
        if len(valor) == 16: valor += ":00"

    conn = get_db()
    exists = conn.execute(
        "SELECT 1 FROM pedido_secciones WHERE pedido_id=? AND seccion_num=? AND bloque_tipo='anexo' AND bloque_ref_id=?",
        (id, sec_num, anx_id)
    ).fetchone()
    
    if not exists:
        conn.execute(
            "INSERT INTO pedido_secciones (pedido_id, seccion_num, bloque_tipo, bloque_ref_id) VALUES (?, ?, 'anexo', ?)",
            (id, sec_num, anx_id)
        )
    
    update_sql = f"UPDATE pedido_secciones SET {tipo_campo}=? WHERE pedido_id=? AND seccion_num=? AND bloque_tipo='anexo' AND bloque_ref_id=?"
    conn.execute(update_sql, (valor, id, sec_num, anx_id))
    conn.commit()
    return redirect(url_for("registros.detalle_pedido", pedido_id=id))


@pedidos_bp.route('/eliminar/<int:id>', methods=['POST'])
def eliminar_pedido(id):
    conn   = get_db()
    pedido = conn.execute(
        "SELECT marca, bultos FROM pedidos WHERE id=? AND eliminado=0", (id,)
    ).fetchone()
    if not pedido:
        flash("Pedido no encontrado o ya eliminado.", "error")
    else:
        conn.execute("UPDATE pedidos SET eliminado=1 WHERE id=?", (id,))
        registrar_cambio(conn, "pedidos", id, "eliminado", 0, 1)
        conn.commit()
        bultos_txt = f"{pedido['bultos']} bultos" if pedido['bultos'] else "sin bultos"
        flash(f" Pedido de {pedido['marca']} ({bultos_txt}) eliminado.", "info")
    return redirect(url_for("registros.registros"))


@pedidos_bp.route('/restaurar/<int:id>', methods=['POST'])
def restaurar_pedido(id):
    conn   = get_db()
    pedido = conn.execute(
        "SELECT marca, estado FROM pedidos WHERE id=? AND eliminado=1", (id,)
    ).fetchone()
    if not pedido:
        flash("Pedido no encontrado en papelera.", "error")
    else:
        conn.execute("UPDATE pedidos SET eliminado=0 WHERE id=?", (id,))
        registrar_cambio(conn, "pedidos", id, "eliminado", 1, 0)
        conn.commit()
        flash(f"↩ Pedido de {pedido['marca']} restaurado (estado: {pedido['estado']}).", "success")
    return redirect(url_for("registros.registros"))


@pedidos_bp.route('/pedido/<int:id>/cambiar_tipo', methods=['POST'])
def cambiar_tipo(id):
    conn = get_db()
    pedido = conn.execute("SELECT tipo, correlativo_mes FROM pedidos WHERE id=?", (id,)).fetchone()
    if not pedido:
        flash("Pedido no encontrado.", "error")
        return redirect(url_for("registros.registros"))

    nuevo_tipo = 'empaque' if pedido['tipo'] == 'directo' else 'directo'
    
    # Si cambia a directo, opcionalmente podrías borrar el correlativo_mes
    if nuevo_tipo == 'directo':
        conn.execute("UPDATE pedidos SET tipo=?, correlativo_mes=NULL WHERE id=?", (nuevo_tipo, id))
    else:
        # Si cambia a empaque, asignar un correlativo si no tiene uno
        if not pedido['correlativo_mes']:
            fecha_curr = datetime.now().strftime('%Y-%m')
            row = conn.execute(
                "SELECT MAX(correlativo_mes) as m FROM pedidos WHERE tipo='empaque' AND fecha LIKE ?",
                (f"{fecha_curr}%",)
            ).fetchone()
            siguiente = (row["m"] if row["m"] else 0) + 1
            conn.execute("UPDATE pedidos SET tipo=?, correlativo_mes=? WHERE id=?", (nuevo_tipo, siguiente, id))
        else:
            conn.execute("UPDATE pedidos SET tipo=? WHERE id=?", (nuevo_tipo, id))
        
    conn.commit()
    flash(f" Tipo de pedido cambiado a {nuevo_tipo.upper()}.", "success")
    return redirect(url_for("registros.detalle_pedido", pedido_id=id))
