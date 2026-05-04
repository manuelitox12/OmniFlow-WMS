from flask import Blueprint, request, redirect, url_for, flash
from datetime import datetime
from database import get_db

anexos_bp = Blueprint('anexos', __name__)

@anexos_bp.route('/pedido/<int:pedido_id>/anexo', methods=['POST'])
def agregar_anexo(pedido_id):
    conn = get_db()
    bultos = int(request.form.get('cantidad_bultos', '0').strip())
    ahora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn.execute('''
        INSERT INTO pedido_anexos 
        (pedido_id, cantidad_bultos, hojas, observacion, digitado_por, dictado_por, digitacion_inicio, digitacion_fin, recibido_mes, recibido_dia, recibido_ano, recibido_hora, creado_en)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (pedido_id, bultos, request.form.get('hojas', ''), request.form.get('observacion', ''), request.form.get('digitado_por', ''), request.form.get('dictado_por', ''), None, None, request.form.get('recibido_mes', ''), request.form.get('recibido_dia', ''), request.form.get('recibido_ano', ''), request.form.get('recibido_hora', ''), ahora))
    conn.commit()
    flash('Anexo agregado.', 'success')
    return redirect(url_for('registros.detalle_pedido', pedido_id=pedido_id))

@anexos_bp.route('/pedido/<int:pedido_id>/anexo/<int:anx_id>/eliminar', methods=['POST'])
def eliminar_anexo(pedido_id, anx_id):
    conn = get_db()
    conn.execute("DELETE FROM pedido_secciones WHERE bloque_tipo='anexo' AND bloque_ref_id=?", (anx_id,))
    conn.execute("DELETE FROM pedido_anexos WHERE id=? AND pedido_id=?", (anx_id, pedido_id))
    conn.commit()
    flash('Anexo eliminado.', 'info')
    return redirect(url_for('registros.detalle_pedido', pedido_id=pedido_id))
