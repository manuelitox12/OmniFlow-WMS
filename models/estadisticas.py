from datetime import datetime
from services.tiempo import calcular_tiempo_laboral

def get_rendimiento_personal(conn):
    """
    Calcula el rendimiento de todo el personal (Bodega y Oficina).
    Retorna un diccionario estructurado para la vista de estadísticas.
    """
    # 1. Obtener todo el personal para inicializar sus estructuras
    personal_rows = conn.execute("SELECT * FROM personal").fetchall()
    stats = {}
    for p in personal_rows:
        stats[p['id']] = {
            'id': p['id'],
            'nombre': f"{p['nombre']} {p['apellido']}",
            'area': p['area'],
            'picking': {'total': 0, 'suma_minutos': 0, 'avg': 0},
            'digitacion_empaque': {'total': 0, 'suma_minutos': 0, 'avg': 0},
            'digitacion_directo': {'total': 0, 'suma_minutos': 0, 'avg': 0},
            'empaque': {'total': 0, 'suma_minutos': 0, 'suma_bultos': 0, 'avg_pedido': 0, 'avg_bulto': 0},
            'detalles_recientes': []
        }

    # 2. Rendimiento en Picking (Secciones/Pasillos)
    picking_rows = conn.execute("""
        SELECT ps.personal_id, ps.inicio, ps.fin, p.marca, ps.seccion_num
        FROM pedido_secciones ps
        JOIN pedidos p ON ps.pedido_id = p.id
        WHERE ps.personal_id IS NOT NULL 
          AND ps.inicio IS NOT NULL 
          AND ps.fin IS NOT NULL
          AND p.eliminado = 0
    """).fetchall()

    for row in picking_rows:
        pid = row['personal_id']
        if pid in stats:
            t = calcular_tiempo_laboral(row['inicio'], row['fin'])
            if t:
                mins = t['minutos_regulares']
                stats[pid]['picking']['total'] += 1
                stats[pid]['picking']['suma_minutos'] += mins
                
                # Agregar a detalles recientes (limitado a 5)
                if len(stats[pid]['detalles_recientes']) < 5:
                    stats[pid]['detalles_recientes'].append({
                        'tipo': 'Picking',
                        'ref': f"{row['marca']} (P.{row['seccion_num']})",
                        'tiempo': t['texto_regulares']
                    })

    # 3. Rendimiento en Digitación (Oficina/Bodega) - Basado en pedidos
    # Buscamos por nombre en digitado_por para oficina, o digitador_id si existiera
    # NOTA: Actualmente se guarda por nombre en digitado_por. 
    # Mapearemos nombres de personal a sus IDs para las estadísticas.
    nombre_to_id = {f"{p['nombre']} {p['apellido']}".strip(): p['id'] for p in personal_rows}
    # También mapear solo por nombre de pila por si acaso
    nombre_pila_to_id = {p['nombre'].strip(): p['id'] for p in personal_rows}

    digitacion_rows = conn.execute("""
        SELECT digitado_por, digitacion_inicio, digitacion_fin, tipo, marca
        FROM pedidos
        WHERE digitado_por IS NOT NULL 
          AND digitacion_inicio IS NOT NULL 
          AND digitacion_fin IS NOT NULL
          AND eliminado = 0
    """).fetchall()

    for row in digitacion_rows:
        nombre = row['digitado_por'].strip()
        pid = nombre_to_id.get(nombre) or nombre_pila_to_id.get(nombre)
        if pid and pid in stats:
            t = calcular_tiempo_laboral(row['digitacion_inicio'], row['digitacion_fin'])
            if t:
                mins = t['minutos_regulares']
                key = 'digitacion_empaque' if row['tipo'] == 'empaque' else 'digitacion_directo'
                stats[pid][key]['total'] += 1
                stats[pid][key]['suma_minutos'] += mins
                
                if len(stats[pid]['detalles_recientes']) < 5:
                    stats[pid]['detalles_recientes'].append({
                        'tipo': 'Digitado',
                        'ref': row['marca'],
                        'tiempo': t['texto_regulares']
                    })

    # 4. Rendimiento en Empaque (Directo en pedido)
    empaque_rows = conn.execute("""
        SELECT empacador_id, inicio_empaque, fin_empaque, bultos, marca
        FROM pedidos
        WHERE empacador_id IS NOT NULL 
          AND inicio_empaque IS NOT NULL 
          AND fin_empaque IS NOT NULL
          AND eliminado = 0
    """).fetchall()

    for row in empaque_rows:
        pid = row['empacador_id']
        if pid in stats:
            t = calcular_tiempo_laboral(row['inicio_empaque'], row['fin_empaque'])
            if t:
                mins = t['minutos_regulares']
                bultos = row['bultos'] or 1
                stats[pid]['empaque']['total'] += 1
                stats[pid]['empaque']['suma_minutos'] += mins
                stats[pid]['empaque']['suma_bultos'] += bultos
                
                if len(stats[pid]['detalles_recientes']) < 5:
                    stats[pid]['detalles_recientes'].append({
                        'tipo': 'Empaque',
                        'ref': row['marca'],
                        'tiempo': t['texto_regulares']
                    })

    # 5. Calcular promedios finales
    for pid in stats:
        s = stats[pid]
        if s['picking']['total'] > 0:
            s['picking']['avg'] = round(s['picking']['suma_minutos'] / s['picking']['total'], 1)
        
        if s['digitacion_empaque']['total'] > 0:
            s['digitacion_empaque']['avg'] = round(s['digitacion_empaque']['suma_minutos'] / s['digitacion_empaque']['total'], 1)
            
        if s['digitacion_directo']['total'] > 0:
            s['digitacion_directo']['avg'] = round(s['digitacion_directo']['suma_minutos'] / s['digitacion_directo']['total'], 1)

        if s['empaque']['total'] > 0:
            s['empaque']['avg_pedido'] = round(s['empaque']['suma_minutos'] / s['empaque']['total'], 1)
            if s['empaque']['suma_bultos'] > 0:
                s['empaque']['avg_bulto'] = round(s['empaque']['suma_minutos'] / s['empaque']['suma_bultos'], 1)

    return list(stats.values())
