from services.tiempo import calcular_tiempo_laboral

def _resolver_personal_id(conn, nombre_completo: str):
    """
    Dado un nombre completo (ej: 'Juan Zapata'), busca el personal_id correspondiente.
    Intenta: 'nombre apellido', luego solo 'nombre'.
    Retorna None si no encuentra coincidencia.
    """
    if not nombre_completo:
        return None
    partes = nombre_completo.strip().split(None, 1)
    nombre  = partes[0]
    apellido = partes[1] if len(partes) > 1 else ""

    # Búsqueda exacta nombre + apellido
    row = conn.execute(
        "SELECT id FROM personal WHERE LOWER(nombre)=LOWER(?) AND LOWER(apellido)=LOWER(?)",
        (nombre, apellido)
    ).fetchone()
    if row:
        return row["id"]

    # Búsqueda solo por nombre (apellido puede estar en nombre del DB)
    row = conn.execute(
        "SELECT id FROM personal WHERE LOWER(nombre)=LOWER(?)",
        (nombre_completo.strip(),)
    ).fetchone()
    if row:
        return row["id"]

    # Búsqueda por nombre solo
    row = conn.execute(
        "SELECT id FROM personal WHERE LOWER(nombre)=LOWER(?)",
        (nombre,)
    ).fetchone()
    return row["id"] if row else None


def is_recibido_completo(data):
    """
    Verifica si los campos de RECIBIDO están completos.
    data puede ser un dict (de SQL row) o un sqlite3.Row.
    """
    if not data:
        return False
    # Verificamos los 4 campos críticos
    keys = ["recibido_mes", "recibido_dia", "recibido_ano", "recibido_hora"]
    for k in keys:
        try:
            val = data[k]
        except (KeyError, IndexError, TypeError):
            return False
        if not val or str(val).strip() == "":
            return False
    return True


def _enriquecer_bloque_secciones(conn, pedido_id, bloque_tipo, bloque_ref_id, lunch_map, flags):
    """
    Función auxiliar para evitar repetir la lógica de carga de secciones entre
    el pedido principal y sus anexos.
    """
    secs_raw = conn.execute(
        """SELECT seccion_num, inicio, fin, persona, personal_id
           FROM pedido_secciones
           WHERE pedido_id=? AND bloque_tipo=? AND bloque_ref_id=?
           ORDER BY seccion_num""",
        (pedido_id, bloque_tipo, bloque_ref_id)
    ).fetchall()
    
    secciones = {}
    for r in secs_raw:
        alm_i = alm_f = None
        if r["personal_id"] in lunch_map:
            alm_i, alm_f = lunch_map[r["personal_id"]]
        
        secciones[r["seccion_num"]] = {
            "inicio":      r["inicio"],
            "fin":         r["fin"],
            "persona":     r["persona"],
            "personal_id": r["personal_id"],
            "tiempo_laboral": calcular_tiempo_laboral(
                r["inicio"], r["fin"], 
                alm_inicio=alm_i, 
                alm_fin=alm_f,
                activas_extras=flags.get("activas_extras", False),
                sabado_reposicion=flags.get("sabado_reposicion", False)
            )
        }
    return secciones


def enriquecer_pedidos(conn, filas_raw):
    """
    Toma una lista de filas RAW de la DB (pedidos) y les inyecta los cálculos
    de tiempo laboral, tipos y totales. Procesa en lote para eficiencia.
    """
    if not filas_raw:
        return []

    # Cargamos el mapa de almuerzos una sola vez para todo el lote
    personal_data = conn.execute("SELECT id, almuerzo_inicio, almuerzo_fin FROM personal").fetchall()
    lunch_map = {p["id"]: (p["almuerzo_inicio"], p["almuerzo_fin"]) for p in personal_data}

    result = []
    for f in filas_raw:
        pedido = dict(f)
        
        # Valores por defecto
        if not pedido.get("tipo"):
            pedido["tipo"] = "empaque"
        if "eliminado" not in pedido:
            pedido["eliminado"] = 0

        flags = {
            "activas_extras":   bool(pedido.get("es_hora_extra")),
            "sabado_reposicion": bool(pedido.get("sabado_reposicion"))
        }

        # Tiempo global del pedido
        alm_i = alm_f = None
        emp_id = pedido.get("empacador_id")
        if emp_id and emp_id in lunch_map:
            alm_i, alm_f = lunch_map[emp_id]

        pedido["tiempo_laboral"] = calcular_tiempo_laboral(
            pedido.get("inicio_empaque"), 
            pedido.get("fin_empaque"), 
            alm_inicio=alm_i, 
            alm_fin=alm_f,
            activas_extras=flags["activas_extras"],
            sabado_reposicion=flags["sabado_reposicion"]
        )

        # Si el pedido tiene campos de digitación (usado en registros y Excel)
        dig_alm_i = dig_alm_f = None
        dig_id = pedido.get("digitador_id")
        if dig_id and dig_id in lunch_map:
            dig_alm_i, dig_alm_f = lunch_map[dig_id]

        pedido["tiempo_digitacion"] = calcular_tiempo_laboral(
            pedido.get("digitacion_inicio"),
            pedido.get("digitacion_fin"),
            alm_inicio=dig_alm_i,
            alm_fin=dig_alm_f,
            activas_extras=flags["activas_extras"],
            sabado_reposicion=flags["sabado_reposicion"]
        )
        
        result.append(pedido)
    return result


def get_pedido_completo(conn, pedido_id):
    """
    Carga un pedido con sus secciones y anexos (incluidos sus secciones).
    Recibe la conexión conn directamente abierta.
    Retorna dict o None si no existe.
    """
    row = conn.execute("SELECT * FROM pedidos WHERE id=?", (pedido_id,)).fetchone()
    if not row:
        return None

    # Usamos la función de lote para enriquecer el pedido base
    pedido = enriquecer_pedidos(conn, [row])[0]
    
    # Mapa de almuerzos (necesario para las secciones internas)
    personal_data = conn.execute("SELECT id, almuerzo_inicio, almuerzo_fin FROM personal").fetchall()
    lunch_map = {p["id"]: (p["almuerzo_inicio"], p["almuerzo_fin"]) for p in personal_data}
    
    flags = {
        "activas_extras":   bool(pedido.get("es_hora_extra")),
        "sabado_reposicion": bool(pedido.get("sabado_reposicion"))
    }

    # Secciones del bloque pedido
    pedido["secciones"] = _enriquecer_bloque_secciones(conn, pedido_id, "pedido", 0, lunch_map, flags)
    
    # Anexos
    anexos_raw = conn.execute(
        "SELECT * FROM pedido_anexos WHERE pedido_id=? ORDER BY id",
        (pedido_id,)
    ).fetchall()
    
    anexos = []
    for a in anexos_raw:
        anx = dict(a)
        anx["secciones"] = _enriquecer_bloque_secciones(conn, pedido_id, "anexo", anx["id"], lunch_map, flags)
        anexos.append(anx)

    pedido["anexos"] = anexos
    pedido["total_bultos_final"] = (pedido.get("bultos") or 0) + sum(
        (a.get("cantidad_bultos") or 0) for a in anexos
    )

    return pedido


def get_nuevo_correlativo_mes(conn, tipo: str, fecha_texto: str):
    """
    Retorna el siguiente correlativo para el mes especificado, 
    solo si el tipo de pedido es 'empaque'. De lo contrario, retorna None.
    """
    if tipo != 'empaque':
        return None
        
    if not fecha_texto or len(fecha_texto) < 7:
        return None
        
    # Extraer YYYY-MM
    mes_anio = fecha_texto[:7] 
    
    row = conn.execute("""
        SELECT MAX(correlativo_mes) as m 
        FROM pedidos 
        WHERE tipo='empaque' AND fecha LIKE ? AND eliminado=0
    """, (f"{mes_anio}%",)).fetchone()
    
    actual = row["m"] if row and row["m"] is not None else 0
    return actual + 1


def reindex_monthly_correlativos(conn, fecha_texto):
    """
    Recalcula todos los correlativos de un mes específico para pedidos tipo 'empaque'.
    Se basa en el orden de ID (orden de creación) para asignar 1, 2, 3...
    """
    if not fecha_texto or len(fecha_texto) < 7:
        return
        
    mes_anio = fecha_texto[:7] # YYYY-MM
    
    # Obtener todos los pedidos de empaque NO eliminados de ese mes
    pedidos = conn.execute("""
        SELECT id FROM pedidos 
        WHERE tipo='empaque' AND eliminado=0 AND fecha LIKE ?
        ORDER BY id ASC
    """, (f"{mes_anio}%",)).fetchall()
    
    # Resetear todos los correlativos del mes para evitar conflictos o números huérfanos
    # (Primero los ponemos en NULL para el mes actual)
    conn.execute("""
        UPDATE pedidos SET correlativo_mes = NULL
        WHERE fecha LIKE ?
    """, (f"{mes_anio}%",))
    
    # Asignar nuevos correlativos
    for i, p in enumerate(pedidos, 1):
        conn.execute("UPDATE pedidos SET correlativo_mes=? WHERE id=?", (i, p["id"]))
    
    # Para pedidos 'directo', asegurar que NO tengan correlativo
    conn.execute("""
        UPDATE pedidos SET correlativo_mes = NULL
        WHERE tipo != 'empaque' AND fecha LIKE ?
    """, (f"{mes_anio}%",))
