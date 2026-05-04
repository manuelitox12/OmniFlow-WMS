import sqlite3
from flask import g
from config import get_config

# 
# GESTOR DE BASE DE DATOS LOCAL (SQLITE)
# 
# NOTA ARQUITECTÓNICA PARA FUTUROS DESARROLLADORES:
# Si posteriormente se desea escalar esta aplicación a múltiples empresas 
# (Multitenancy) o desplegarla en servicios en la nube efímeros (ej. Heroku/AWS),
# se recomienda encarecidamente migrar este adaptador de SQLite a PostgreSQL. 
# Solo tienes que cambiar la URI en Config (config.py) y adaptar el cursor 
# de `sqlite3.Row` a `psycopg2.extras.DictCursor` para mantener la misma 
# respuesta de diccionarios en toda la aplicación. Todo el SQL base es compatible.
#
# GESTIÓN DE CONEXIONES:
# get_db() reutiliza la conexión dentro del mismo request de Flask.
# close_db() se llama automáticamente al terminar cada request vía teardown.
# Esto PREVIENE fugas de conexiones: ya NO necesitas llamar conn.close() 
# manualmente (aunque hacerlo extra no causa error).
# 

def get_db():
    """Obtiene una conexión a la BD, reutilizándola dentro del mismo request.
    Si estamos fuera de un request de Flask (ej: init_db), crea una nueva."""
    try:
        if 'db' not in g:
            config = get_config()
            g.db = sqlite3.connect(config.DATABASE)
            g.db.row_factory = sqlite3.Row
        return g.db
    except RuntimeError:
        # Estamos fuera de un request de Flask (ej: init_db al arranque)
        config = get_config()
        conn = sqlite3.connect(config.DATABASE)
        conn.row_factory = sqlite3.Row
        return conn


def close_db(e=None):
    """Cierra automáticamente la conexión al terminar el request.
    Se registra en app.teardown_appcontext desde app.py."""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    """
    Crea las tablas si no existen y aplica migraciones seguras.
    Idempotente: seguro de llamar múltiples veces.
    """
    conn = get_db()
    conn.executescript("""
        --  Tabla principal de pedidos 
        CREATE TABLE IF NOT EXISTS pedidos (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            marca               TEXT    NOT NULL,
            bultos              INTEGER,
            tipo                TEXT    NOT NULL DEFAULT 'empaque',
            retirado_por        TEXT,
            fecha               TEXT    NOT NULL,
            estado              TEXT    NOT NULL DEFAULT 'pendiente',
            inicio_empaque      TEXT,
            fin_empaque         TEXT,
            retirado_en         TEXT,
            eliminado           INTEGER NOT NULL DEFAULT 0,
            creado_en           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            hojas               TEXT,
            digitado_por        TEXT,
            digitador_id        INTEGER,
            dictado_por         TEXT,
            dictador_id         INTEGER,
            empacador_id        INTEGER,
            digitacion_inicio   TEXT,
            digitacion_fin      TEXT,
            recibido_mes        TEXT,
            recibido_dia        TEXT,
            recibido_ano        TEXT,
            recibido_hora       TEXT,
            observacion         TEXT,
            correlativo_mes     INTEGER,
            es_hora_extra       INTEGER NOT NULL DEFAULT 0,
            sabado_reposicion   INTEGER NOT NULL DEFAULT 0,
            preparador_nombre   TEXT,
            preparador_id       INTEGER,
            inicio_preparacion  TEXT,
            fin_preparacion     TEXT,
            modo_preparacion    TEXT    NOT NULL DEFAULT 'SECCIONES',
            FOREIGN KEY (digitador_id)   REFERENCES personal(id),
            FOREIGN KEY (dictador_id)    REFERENCES personal(id),
            FOREIGN KEY (empacador_id)   REFERENCES personal(id),
            FOREIGN KEY (preparador_id)  REFERENCES personal(id)
        );

        --  Secciones (pasillos) por pedido 
        CREATE TABLE IF NOT EXISTS pedido_secciones (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            pedido_id     INTEGER NOT NULL,
            bloque_tipo   TEXT    NOT NULL DEFAULT 'pedido',
            bloque_ref_id INTEGER,
            seccion_num   INTEGER NOT NULL CHECK(seccion_num BETWEEN 1 AND 5),
            inicio        TEXT,
            fin           TEXT,
            persona       TEXT,
            personal_id   INTEGER,
            FOREIGN KEY (pedido_id)   REFERENCES pedidos(id),
            FOREIGN KEY (personal_id) REFERENCES personal(id)
        );

        --  Preparación por Hojas (Dinámica) 
        CREATE TABLE IF NOT EXISTS pedido_hojas (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            pedido_id     INTEGER NOT NULL,
            hoja_num      INTEGER NOT NULL,
            inicio        TEXT,
            fin           TEXT,
            persona       TEXT,
            personal_id   INTEGER,
            FOREIGN KEY (pedido_id)   REFERENCES pedidos(id),
            FOREIGN KEY (personal_id) REFERENCES personal(id)
        );

        --  Anexos por pedido 
        CREATE TABLE IF NOT EXISTS pedido_anexos (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            pedido_id           INTEGER NOT NULL,
            cantidad_bultos     INTEGER NOT NULL DEFAULT 0,
            hojas               TEXT,
            observacion         TEXT,
            digitado_por        TEXT,
            digitador_id        INTEGER,
            dictado_por         TEXT,
            dictador_id         INTEGER,
            digitacion_inicio   TEXT,
            digitacion_fin      TEXT,
            recibido_mes        TEXT,
            recibido_dia        TEXT,
            recibido_ano        TEXT,
            recibido_hora       TEXT,
            creado_en           TEXT,
            FOREIGN KEY (pedido_id) REFERENCES pedidos(id),
            FOREIGN KEY (digitador_id) REFERENCES personal(id),
            FOREIGN KEY (dictador_id) REFERENCES personal(id)
        );

        --  Catálogos 
        CREATE TABLE IF NOT EXISTS marcas (
            id     INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE NOT NULL
        );

        CREATE TABLE IF NOT EXISTS personas (
            id     INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE NOT NULL
        );

        CREATE TABLE IF NOT EXISTS personal (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre  TEXT    NOT NULL,
            apellido TEXT   NOT NULL DEFAULT '',
            cedula          TEXT    NOT NULL DEFAULT '',
            area            TEXT    NOT NULL DEFAULT 'bodega', -- 'bodega' o 'oficina'
            almuerzo_inicio TEXT    DEFAULT '12:00',
            almuerzo_fin    TEXT    DEFAULT '12:30'
        );

        --  Tabla de usuarios (Autenticación y Roles) 
        CREATE TABLE IF NOT EXISTS usuarios (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            username        TEXT    UNIQUE NOT NULL,
            password_hash   TEXT    NOT NULL,
            nombre_completo TEXT    NOT NULL DEFAULT '',
            rol             TEXT    NOT NULL DEFAULT 'bodega',
            activo          INTEGER NOT NULL DEFAULT 1,
            creado_en       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        --  Tabla de Auditoría (Trazabilidad) 
        CREATE TABLE IF NOT EXISTS auditoria (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            usuario_id      INTEGER,
            usuario_nombre  TEXT,
            tabla           TEXT    NOT NULL,
            registro_id     INTEGER NOT NULL,
            campo           TEXT    NOT NULL,
            valor_anterior  TEXT,
            valor_nuevo     TEXT,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        );

        --  Tabla de empresa (Marca Blanca / White Label) 
        CREATE TABLE IF NOT EXISTS empresa (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre            TEXT    NOT NULL DEFAULT 'Mi Empresa',
            subtitulo         TEXT    DEFAULT 'Sistema de Bodega',
            color_primario    TEXT    DEFAULT '#0d2a6e',
            color_secundario  TEXT    DEFAULT '#f5c800',
            logo_url          TEXT    DEFAULT '',
            work_start        TEXT    DEFAULT '07:00',
            work_end          TEXT    DEFAULT '16:30',
            friday_work_end   TEXT    DEFAULT '15:30',
            lunch_start       TEXT    DEFAULT '12:00',
            lunch_end         TEXT    DEFAULT '12:30',
            include_saturday  INTEGER DEFAULT 0,
            saturday_regular  INTEGER DEFAULT 0,
            sunday_extra      INTEGER DEFAULT 0
        );

        -- Seed de empresa inicial (Genérico para nueva instancia)
        INSERT OR IGNORE INTO empresa (nombre, subtitulo, color_primario, color_secundario, logo_url)
        VALUES ('Mi Empresa', 'Sistema de Bodega', '#0d2a6e', '#f5c800', '');
    """)

    #  Migraciones seguras para bases de datos existentes 
    migraciones = [
        "ALTER TABLE pedidos ADD COLUMN estado         TEXT NOT NULL DEFAULT 'pendiente'",
        "ALTER TABLE pedidos ADD COLUMN inicio_empaque TEXT",
        "ALTER TABLE pedidos ADD COLUMN fin_empaque    TEXT",
        "ALTER TABLE pedidos ADD COLUMN retirado_en    TEXT",
        "ALTER TABLE pedidos ADD COLUMN tipo           TEXT NOT NULL DEFAULT 'empaque'",
        "ALTER TABLE pedidos ADD COLUMN eliminado      INTEGER NOT NULL DEFAULT 0",
        
        "ALTER TABLE pedidos ADD COLUMN hojas               TEXT",
        "ALTER TABLE pedidos ADD COLUMN digitado_por        TEXT",
        "ALTER TABLE pedidos ADD COLUMN dictado_por         TEXT",
        "ALTER TABLE pedidos ADD COLUMN digitacion_inicio   TEXT",
        "ALTER TABLE pedidos ADD COLUMN digitacion_fin      TEXT",
        "ALTER TABLE pedidos ADD COLUMN recibido_mes        TEXT",
        "ALTER TABLE pedidos ADD COLUMN recibido_dia        TEXT",
        "ALTER TABLE pedidos ADD COLUMN recibido_ano        TEXT",
        "ALTER TABLE pedidos ADD COLUMN recibido_hora       TEXT",
        
        "ALTER TABLE pedido_secciones ADD COLUMN persona TEXT",
        "ALTER TABLE pedido_secciones ADD COLUMN personal_id INTEGER REFERENCES personal(id)",
        
        # NUEVA MIGRACIÓN: Correlativo mensual
        "ALTER TABLE pedidos ADD COLUMN correlativo_mes INTEGER",

        # V10: IDs para rendimiento
        "ALTER TABLE pedidos ADD COLUMN digitador_id INTEGER REFERENCES personal(id)",
        "ALTER TABLE pedidos ADD COLUMN dictador_id  INTEGER REFERENCES personal(id)",
        "ALTER TABLE pedido_anexos ADD COLUMN digitador_id INTEGER REFERENCES personal(id)",
        "ALTER TABLE pedido_anexos ADD COLUMN dictador_id  INTEGER REFERENCES personal(id)",
        
        # V13: Almuerzos y Roles
        "ALTER TABLE personal ADD COLUMN area            TEXT NOT NULL DEFAULT 'bodega'",
        "ALTER TABLE personal ADD COLUMN almuerzo_inicio TEXT DEFAULT '12:00'",
        "ALTER TABLE personal ADD COLUMN almuerzo_fin    TEXT DEFAULT '12:30'",
        "ALTER TABLE pedidos  ADD COLUMN empacador_id    INTEGER REFERENCES personal(id)",
        "ALTER TABLE pedidos  ADD COLUMN observacion     TEXT",
        
        # V14: Preparación Global
        "ALTER TABLE pedidos  ADD COLUMN preparador_nombre TEXT",
        "ALTER TABLE pedidos  ADD COLUMN preparador_id     INTEGER REFERENCES personal(id)",
        "ALTER TABLE pedidos  ADD COLUMN inicio_preparacion TEXT",
        "ALTER TABLE pedidos  ADD COLUMN fin_preparacion    TEXT",
        
        # V15: Preparación por Hojas (Dinámica)
        "ALTER TABLE pedidos  ADD COLUMN modo_preparacion   TEXT NOT NULL DEFAULT 'SECCIONES'",
    ]
    
    for sql in migraciones:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass  # columna ya existe

    #  Migración v6: hacer bultos nullable en tablas existentes 
    col_info   = conn.execute("PRAGMA table_info(pedidos)").fetchall()
    bultos_col = next((c for c in col_info if c["name"] == "bultos"), None)
    if bultos_col and bultos_col["notnull"] == 1:
        conn.executescript("""
            PRAGMA foreign_keys=OFF;
            CREATE TABLE pedidos_v6 (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                marca               TEXT    NOT NULL,
                bultos              INTEGER,
                tipo                TEXT    NOT NULL DEFAULT 'empaque',
                retirado_por        TEXT,
                fecha               TEXT    NOT NULL,
                estado              TEXT    NOT NULL DEFAULT 'pendiente',
                inicio_empaque      TEXT,
                fin_empaque         TEXT,
                retirado_en         TEXT,
                eliminado           INTEGER NOT NULL DEFAULT 0,
                creado_en           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                hojas               TEXT,
                digitado_por        TEXT,
                dictado_por         TEXT,
                digitacion_inicio   TEXT,
                digitacion_fin      TEXT,
                recibido_mes        TEXT,
                recibido_dia        TEXT,
                recibido_ano        TEXT,
                recibido_hora       TEXT,
                correlativo_mes     INTEGER,
                observacion         TEXT
            );
            INSERT INTO pedidos_v6
                SELECT id, marca, NULLIF(bultos, 0), tipo, retirado_por, fecha, estado,
                       inicio_empaque, fin_empaque, retirado_en, eliminado, creado_en,
                       hojas, digitado_por, dictado_por, digitacion_inicio, digitacion_fin,
                       recibido_mes, recibido_dia, recibido_ano, recibido_hora, correlativo_mes, observacion
                FROM pedidos;
            DROP TABLE pedidos;
            ALTER TABLE pedidos_v6 RENAME TO pedidos;
            PRAGMA foreign_keys=ON;
        """)

    #  Migración v8: bloque_ref_id NULL → 0 para el bloque pedido 
    try:
        conn.execute(
            "UPDATE pedido_secciones SET bloque_ref_id=0 "
            "WHERE bloque_tipo='pedido' AND bloque_ref_id IS NULL"
        )
    except Exception:
        pass

    # -- Migración v9: desduplicar secciones (ELIMINADO por ser destructivo con splits) --

    #  Asignar correlativo retroactivo a pedidos viejos si no tienen 
    try:
        # Vamos a asignarles correlativo basándonos en su FECHA y TIPO=empaque, preservando orden.
        pedidos_sin_correlativo = conn.execute("""
            SELECT id, fecha FROM pedidos 
            WHERE tipo='empaque' AND (correlativo_mes IS NULL OR correlativo_mes = 0)
            ORDER BY id ASC
        """).fetchall()
        
        for p in pedidos_sin_correlativo:
            # extraer mes y anio de la fecha "YYYY-MM-DD"
            fecha_str = p["fecha"]
            if len(fecha_str) >= 7:
                mes_anio = fecha_str[:7] # YYYY-MM
                max_corr_row = conn.execute("""
                    SELECT MAX(correlativo_mes) as m 
                    FROM pedidos 
                    WHERE tipo='empaque' AND fecha LIKE ? 
                """, (f"{mes_anio}%",)).fetchone()
                
                siguiente = (max_corr_row["m"] if max_corr_row["m"] else 0) + 1
                conn.execute("UPDATE pedidos SET correlativo_mes=? WHERE id=?", (siguiente, p["id"]))
    except Exception as e:
        print(f"Error migrando correlativos viejos: {e}")

    #  Migración v12: Column for extra hours flag 
    try:
        conn.execute("ALTER TABLE pedidos ADD COLUMN es_hora_extra INTEGER NOT NULL DEFAULT 0")
    except Exception:
        pass

    #  Migración v13: Sábado Reposición 
    # Esta bandera indica si el pedido fue trabajado un sábado en horario especial (8AM - 2PM)
    # y por ende debe considerarse tiempo neto "regular" en vez de tiempo extra.
    try:
        conn.execute("ALTER TABLE pedidos ADD COLUMN sabado_reposicion INTEGER NOT NULL DEFAULT 0")
    except Exception:
        pass

    #  Migración v16: Preparación Global (Operador Único) 
    try:
        conn.execute("ALTER TABLE pedidos ADD COLUMN preparador_nombre TEXT")
        conn.execute("ALTER TABLE pedidos ADD COLUMN preparador_id     INTEGER REFERENCES personal(id)")
        conn.execute("ALTER TABLE pedidos ADD COLUMN inicio_preparacion TEXT")
        conn.execute("ALTER TABLE pedidos ADD COLUMN fin_preparacion    TEXT")
    except Exception:
        pass
    #  Migración v14: Seed usuario admin por defecto 
    # Contraseña inicial: admin123 (el admin DEBE cambiarla inmediatamente)
    # werkzeug.security genera hashes seguros con pbkdf2:sha256
    try:
        from werkzeug.security import generate_password_hash
        existing = conn.execute("SELECT id FROM usuarios LIMIT 1").fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO usuarios (username, password_hash, nombre_completo, rol) VALUES (?, ?, ?, ?)",
                ("admin", generate_password_hash("admin123"), "Administrador", "admin")
            )
    except Exception:
        pass

    #  Migración v14: Seed empresa por defecto 
    try:
        existing_emp = conn.execute("SELECT id FROM empresa LIMIT 1").fetchone()
        if not existing_emp:
            conn.execute(
                "INSERT INTO empresa (nombre, subtitulo, color_primario, color_secundario, logo_url) VALUES (?, ?, ?, ?, ?)",
                ("MEGA ENSAMBLES INT, S.A.", "Sistema de Bodega", "#0d2a6e", "#f5c800", "/static/img/logo.png")
            )
        else:
            # Si ya existe, asegurarnos de que el logo_url este actualizado para esta visualizacion (testing/demo)
            # Solo si esta vacio
            conn.execute("UPDATE empresa SET logo_url = '/static/img/logo.png' WHERE logo_url = '' OR logo_url IS NULL")
    except Exception:
        pass

    #  Migración v15: Remover UNIQUE de pedido_secciones para permitir Splits 
    try:
        # Verificamos si la tabla tiene el constraint UNIQUE buscando en el SQL original
        db_conn = get_db()
        table_sql_row = db_conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='pedido_secciones'").fetchone()
        if table_sql_row and "UNIQUE" in table_sql_row[0]:
            print("Aplicando migración v15: Eliminando UNIQUE de pedido_secciones...")
            db_conn.executescript("""
                PRAGMA foreign_keys=OFF;
                CREATE TABLE pedido_secciones_new (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    pedido_id     INTEGER NOT NULL,
                    bloque_tipo   TEXT    NOT NULL DEFAULT 'pedido',
                    bloque_ref_id INTEGER,
                    seccion_num   INTEGER NOT NULL CHECK(seccion_num BETWEEN 1 AND 5),
                    inicio        TEXT,
                    fin           TEXT,
                    persona       TEXT,
                    personal_id   INTEGER,
                    FOREIGN KEY (pedido_id)   REFERENCES pedidos(id),
                    FOREIGN KEY (personal_id) REFERENCES personal(id)
                );
                INSERT INTO pedido_secciones_new (id, pedido_id, bloque_tipo, bloque_ref_id, seccion_num, inicio, fin, persona, personal_id)
                SELECT id, pedido_id, bloque_tipo, bloque_ref_id, seccion_num, inicio, fin, persona, personal_id FROM pedido_secciones;
                DROP TABLE pedido_secciones;
                ALTER TABLE pedido_secciones_new RENAME TO pedido_secciones;
                PRAGMA foreign_keys=ON;
            """)
    except Exception as e:
        print(f"Error migración v15: {e}")

    conn.commit()
    conn.close()
