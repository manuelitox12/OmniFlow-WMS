from flask import g
from datetime import datetime

def registrar_cambio(conn, tabla, registro_id, campo, valor_viejo, valor_nuevo):
    """
    Registra una modificación en la tabla de auditoría.
    Solo registra si el valor realmente cambió.
    """
    # Normalizar valores para comparación
    v1 = str(valor_viejo).strip() if valor_viejo is not None else ""
    v2 = str(valor_nuevo).strip() if valor_nuevo is not None else ""
    
    if v1 == v2:
        return # No hay cambio real

    usuario_id = g.user["id"] if g.user else None
    usuario_nombre = g.user["username"] if g.user else "sistema"

    conn.execute("""
        INSERT INTO auditoria (usuario_id, usuario_nombre, tabla, registro_id, campo, valor_anterior, valor_nuevo)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (usuario_id, usuario_nombre, tabla, registro_id, campo, v1, v2))
