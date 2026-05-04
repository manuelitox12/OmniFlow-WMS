"""
registros.py — Tablero de control de pedidos
===============================================
Muestra pedidos activos (en proceso + empacados), historial de retirados,
y papelera. Calcula tiempos laborales para cada fila.
"""
from flask import Blueprint, render_template, request
from database import get_db
from datetime import datetime
from services.tiempo import calcular_tiempo_laboral

registros_bp = Blueprint('registros', __name__)


def _enriquecer(filas):
    """Convierte sqlite3.Row a dict y añade tiempo_laboral calculado."""
    result = []
    for f in filas:
        d = dict(f)
        if "tipo" not in d or not d["tipo"]:
            d["tipo"] = "empaque"
        if "eliminado" not in d:
            d["eliminado"] = 0
        d["tiempo_laboral"] = calcular_tiempo_laboral(
            d.get("inicio_empaque"), d.get("fin_empaque")
        )
        result.append(d)
    return result


def _enriquecer_pedido_completo(pedido, conn):
    """Enriquece un pedido individual con secciones, anexos y tiempos calculados."""
    pedido = dict(pedido)
    
    # Tiempos principales
    pedido["tiempo_laboral"] = calcular_tiempo_laboral(
        pedido.get("inicio_empaque"), pedido.get("fin_empaque")
    )

    # Tiempo de preparación global (si existe)
    pedido["tiempo_preparacion"] = calcular_tiempo_laboral(
        pedido.get("inicio_preparacion"), pedido.get("fin_preparacion")
    )

    # Secciones del bloque pedido (agrupadas por número de sección)
    secs_raw = conn.execute(
        "SELECT * FROM pedido_secciones WHERE pedido_id=? AND bloque_tipo='pedido' ORDER BY seccion_num, id",
        (pedido["id"],)
    ).fetchall()
    
    secciones = {n: [] for n in range(1, 6)}
    for r in secs_raw:
        s = dict(r)
        s["tiempo_laboral"] = calcular_tiempo_laboral(s.get("inicio"), s.get("fin"))
        secciones[s["seccion_num"]].append(s)
    pedido['secciones'] = secciones

    # Hojas de preparación (Modo Dinámico)
    hojas_raw = conn.execute(
        "SELECT * FROM pedido_hojas WHERE pedido_id=? ORDER BY hoja_num, id",
        (pedido["id"],)
    ).fetchall()
    
    # Trataremos de deducir cuántas hojas hay según lo que tipeó el usuario
    num_hojas_str = str(pedido.get("hojas") or "")
    max_hoja = 0
    try:
        import re
        numeros = re.findall(r'\d+', num_hojas_str)
        if numeros:
            max_hoja = max(int(n) for n in numeros)
    except Exception as e:
        print("Error deducing hojas:", e)
        pass

    # Asegurar que generamos al menos listas vacías hasta max_hoja
    hoja_records = {n: [] for n in range(1, max_hoja + 1)}
    for r in hojas_raw:
        h = dict(r)
        h["tiempo_laboral"] = calcular_tiempo_laboral(h.get("inicio"), h.get("fin"))
        num = h["hoja_num"]
        if num not in hoja_records:
            hoja_records[num] = []
        hoja_records[num].append(h)
        
    pedido['hoja_records'] = hoja_records
    pedido['max_hoja_calc'] = max(max_hoja, max(hoja_records.keys()) if hoja_records else 0)

    # Anexos con secciones
    anx_raw = conn.execute('SELECT * FROM pedido_anexos WHERE pedido_id=? ORDER BY id', (pedido["id"],)).fetchall()
    anexos = []
    for a in anx_raw:
        anx = dict(a)
        secs_anx_raw = conn.execute(
            "SELECT * FROM pedido_secciones WHERE pedido_id=? AND bloque_tipo='anexo' AND bloque_ref_id=? ORDER BY seccion_num, id",
            (pedido["id"], anx["id"])
        ).fetchall()
        
        secs_anx = {n: [] for n in range(1, 6)}
        for r in secs_anx_raw:
            s = dict(r)
            s["tiempo_laboral"] = calcular_tiempo_laboral(s.get("inicio"), s.get("fin"))
            secs_anx[s["seccion_num"]].append(s)
        
        anx["secciones"] = secs_anx
        anexos.append(anx)
        
    pedido['anexos'] = anexos
    pedido['total_bultos_final'] = (pedido.get('bultos') or 0) + sum((a.get('cantidad_bultos') or 0) for a in anexos)
    
    # Fallback: Resolver nombre de Dictado por si falta pero hay ID
    if not pedido.get('dictado_por') and pedido.get('empacador_id'):
        p_row = conn.execute("SELECT nombre, apellido FROM personal WHERE id=?", (pedido['empacador_id'],)).fetchone()
        if p_row:
            pedido['dictado_por'] = f"{p_row['nombre']} {p_row['apellido']}".strip()

    return pedido


@registros_bp.route('/registros')
def registros():
    busqueda  = request.args.get("q", "").strip()
    fecha_ini = request.args.get("fecha_ini", "").strip()
    fecha_fin = request.args.get("fecha_fin", "").strip()
    sort_mode = request.args.get("sort", "prioridad")

    conn     = get_db()
    personas = conn.execute("SELECT nombre FROM personas ORDER BY nombre").fetchall()

    #  Pedidos activos (pendiente, empacando, empacado) 
    activos_raw = conn.execute(
        """SELECT * FROM pedidos
           WHERE estado IN ('pendiente','empacando','empacado')
             AND eliminado = 0
           ORDER BY fecha DESC"""
    ).fetchall()

    #  Historial de retirados 
    tipo_filter = request.args.get("tipo", "").strip()
    query  = "SELECT * FROM pedidos WHERE estado = 'retirado' AND eliminado = 0"
    params = []
    if busqueda:
        query  += " AND (marca LIKE ? OR retirado_por LIKE ?)"
        params += [f"%{busqueda}%", f"%{busqueda}%"]
    if fecha_ini:
        query  += " AND fecha >= ?"
        params.append(fecha_ini)
    if fecha_fin:
        query  += " AND fecha <= ?"
        params.append(fecha_fin + " 23:59")
    if tipo_filter in ['empaque', 'directo']:
        query += " AND tipo = ?"
        params.append(tipo_filter)
        
    query += " ORDER BY retirado_en DESC"
    historial_raw = conn.execute(query, params).fetchall()

    #  Papelera 
    eliminados_raw = conn.execute(
        "SELECT * FROM pedidos WHERE eliminado = 1 ORDER BY fecha DESC"
    ).fetchall()

    #  Enriquecer datos 
    activos    = _enriquecer(activos_raw)
    historial  = _enriquecer(historial_raw)
    eliminados = _enriquecer(eliminados_raw)

    # Separar activos en proceso vs empacados
    procesos  = [p for p in activos if p["estado"] != "empacado"]
    empacados = [p for p in activos if p["estado"] == "empacado"]

    return render_template("registros.html",
        activos_proceso      = procesos,
        activos_empacados    = empacados,
        historial            = historial,
        eliminados           = eliminados,
        personas             = personas,
        total_bultos_activos = sum((p["bultos"] or 0) for p in activos),
        total_bultos_historial = sum((p["bultos"] or 0) for p in historial),
        busqueda             = busqueda,
        fecha_ini            = fecha_ini,
        fecha_fin            = fecha_fin,
        tipo_filter          = tipo_filter,
        sort_mode            = sort_mode,
    )


@registros_bp.route('/pedido/<int:pedido_id>', methods=['GET'])
def detalle_pedido(pedido_id):
    conn = get_db()

    row = conn.execute('SELECT * FROM pedidos WHERE id=?', (pedido_id,)).fetchone()
    if not row:
        return 'No encontrado', 404
    
    # Usar el nuevo ayudante para traer secciones, anexos y tiempos calculados
    pedido = _enriquecer_pedido_completo(row, conn)

    # Catálogos de personal
    pers_bodega  = conn.execute("SELECT * FROM personal WHERE area='bodega' ORDER BY nombre").fetchall()
    pers_oficina = conn.execute("SELECT * FROM personal WHERE area='oficina' ORDER BY nombre").fetchall()
    
    # Catálogo de personas externas (para retiro)
    personas = conn.execute('SELECT nombre FROM personas ORDER BY nombre').fetchall()

    return render_template('detalle.html', 
                           pedido=pedido, 
                           personas=personas, 
                           pers_bodega=pers_bodega, 
                           pers_oficina=pers_oficina)
