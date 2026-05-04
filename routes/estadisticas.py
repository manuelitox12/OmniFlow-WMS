from flask import Blueprint, render_template
from database import get_db
from models.estadisticas import get_rendimiento_personal

estadisticas_bp = Blueprint('estadisticas', __name__)

@estadisticas_bp.route('/estadisticas')
def estadisticas():
    conn = get_db()
    all_stats = get_rendimiento_personal(conn)
    
    # Separar por áreas para el template
    stats_digitadores = [s for s in all_stats if s['area'] == 'oficina']
    stats_pasillos    = [s for s in all_stats if s['area'] == 'bodega']
    
    # Filtrar aquellos que no tengan ninguna actividad registrada para no saturar la vista
    # (Opcional, pero suele ser mejor solo mostrar los activos)
    stats_digitadores = [s for s in stats_digitadores if (s['digitacion_empaque']['total'] > 0 or s['digitacion_directo']['total'] > 0 or s['empaque']['total'] > 0)]
    stats_pasillos    = [s for s in stats_pasillos if s['picking']['total'] > 0]
    
    return render_template('estadisticas.html', 
                           stats_digitadores=stats_digitadores, 
                           stats_pasillos=stats_pasillos)
