from flask import Blueprint, request, redirect, url_for, flash
from datetime import datetime
from database import get_db

estados_bp = Blueprint('estados', __name__)

@estados_bp.route('/pedido/<int:pedido_id>/estado/pendientear', methods=['POST'])
def a_pendiente(pedido_id):
    conn = get_db()
    conn.execute("UPDATE pedidos SET estado='pendiente', inicio_empaque=NULL, fin_empaque=NULL WHERE id=?", (pedido_id,))
    conn.commit()
    return redirect(url_for('registros.detalle_pedido', pedido_id=pedido_id))

@estados_bp.route('/pedido/<int:pedido_id>/estado/empacando', methods=['POST'])
def empacando(pedido_id):
    conn = get_db()
    ahora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn.execute("UPDATE pedidos SET estado='empacando', inicio_empaque=? WHERE id=?", (ahora, pedido_id))
    conn.commit()
    return redirect(url_for('registros.detalle_pedido', pedido_id=pedido_id))

@estados_bp.route('/pedido/<int:pedido_id>/estado/finalizar', methods=['POST'])
def empacado(pedido_id):
    conn = get_db()
    ahora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn.execute("UPDATE pedidos SET estado='empacado', fin_empaque=? WHERE id=?", (ahora, pedido_id))
    conn.commit()
    flash('Pedido empacado.', 'success')
    return redirect(url_for('registros.registros'))


# La ruta de retirar se movió a pedidos.py para centralizar la lógica del ciclo de vida.
