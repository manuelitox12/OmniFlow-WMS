from flask import Blueprint, render_template
from database import get_db

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    conn = get_db()
    marcas = conn.execute('SELECT nombre FROM marcas ORDER BY nombre').fetchall()
    personas = conn.execute('SELECT nombre FROM personas ORDER BY nombre').fetchall()
    return render_template('index.html', marcas=marcas, personas=personas)
