import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ventas.db")

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS proveedores (
    id_proveedor    INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre          TEXT NOT NULL,
    contacto        TEXT,
    telefono        TEXT,
    email           TEXT,
    direccion       TEXT
);

CREATE TABLE IF NOT EXISTS clientes (
    id_cliente      INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre          TEXT NOT NULL,
    telefono        TEXT,
    email           TEXT,
    direccion       TEXT,
    fecha_registro  TEXT DEFAULT (date('now'))
);

CREATE TABLE IF NOT EXISTS productos (
    id_producto     INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre          TEXT NOT NULL,
    descripcion     TEXT,
    categoria       TEXT DEFAULT 'MEDICATION',
    precio          REAL NOT NULL DEFAULT 0,
    costo_unitario  REAL NOT NULL DEFAULT 0,
    volumen_ml      REAL,
    stock           INTEGER NOT NULL DEFAULT 0,
    id_proveedor    INTEGER,
    FOREIGN KEY (id_proveedor) REFERENCES proveedores(id_proveedor) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS trabajadores (
    id_trabajador       INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre              TEXT NOT NULL,
    puesto              TEXT,
    telefono            TEXT,
    email               TEXT,
    fecha_contratacion  TEXT,
    salario             REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS usuarios (
    id_usuario      INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    rol             TEXT DEFAULT 'empleado',
    id_trabajador   INTEGER,
    FOREIGN KEY (id_trabajador) REFERENCES trabajadores(id_trabajador) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS ventas (
    id_venta        INTEGER PRIMARY KEY AUTOINCREMENT,
    id_cliente      INTEGER,
    id_trabajador   INTEGER,
    fecha           TEXT DEFAULT (date('now')),
    total           REAL DEFAULT 0,
    estado_pago     TEXT DEFAULT 'Paid',
    metodo_pago     TEXT,
    FOREIGN KEY (id_cliente) REFERENCES clientes(id_cliente) ON DELETE SET NULL,
    FOREIGN KEY (id_trabajador) REFERENCES trabajadores(id_trabajador) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS detalle_ventas (
    id_detalle      INTEGER PRIMARY KEY AUTOINCREMENT,
    id_venta        INTEGER NOT NULL,
    id_producto     INTEGER NOT NULL,
    cantidad        INTEGER NOT NULL DEFAULT 1,
    precio_unitario REAL NOT NULL,
    FOREIGN KEY (id_venta) REFERENCES ventas(id_venta) ON DELETE CASCADE,
    FOREIGN KEY (id_producto) REFERENCES productos(id_producto) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS nomina (
    id_nomina       INTEGER PRIMARY KEY AUTOINCREMENT,
    id_trabajador   INTEGER NOT NULL,
    fecha_pago      TEXT DEFAULT (date('now')),
    periodo         TEXT,
    salario_bruto   REAL DEFAULT 0,
    deducciones     REAL DEFAULT 0,
    salario_neto    REAL DEFAULT 0,
    FOREIGN KEY (id_trabajador) REFERENCES trabajadores(id_trabajador) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS compras_proveedores (
    id_compra       INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha           TEXT DEFAULT (date('now')),
    id_proveedor    INTEGER,
    id_cliente      INTEGER,
    id_producto     INTEGER NOT NULL,
    cantidad        REAL NOT NULL DEFAULT 1,
    costo_unitario  REAL NOT NULL DEFAULT 0,
    total           REAL NOT NULL DEFAULT 0,
    numero_factura  TEXT,
    tarjeta_usada   TEXT,
    estado_pago     TEXT DEFAULT 'Paid',
    FOREIGN KEY (id_proveedor) REFERENCES proveedores(id_proveedor) ON DELETE SET NULL,
    FOREIGN KEY (id_cliente) REFERENCES clientes(id_cliente) ON DELETE SET NULL,
    FOREIGN KEY (id_producto) REFERENCES productos(id_producto) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS documentos_clientes (
    id_documento    INTEGER PRIMARY KEY AUTOINCREMENT,
    id_cliente      INTEGER NOT NULL,
    nombre_archivo  TEXT NOT NULL,
    ruta_archivo    TEXT NOT NULL,
    fecha_subida    TEXT DEFAULT (date('now')),
    FOREIGN KEY (id_cliente) REFERENCES clientes(id_cliente) ON DELETE CASCADE
);
"""

# Columnas nuevas agregadas a tablas que ya podrían existir en bases de datos previas
MIGRACIONES = [
    ("productos", "categoria", "TEXT DEFAULT 'MEDICATION'"),
    ("productos", "costo_unitario", "REAL NOT NULL DEFAULT 0"),
    ("productos", "volumen_ml", "REAL"),
    ("ventas", "estado_pago", "TEXT DEFAULT 'Paid'"),
    ("ventas", "metodo_pago", "TEXT"),
]


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn


def _aplicar_migraciones(conn):
    for tabla, columna, tipo in MIGRACIONES:
        cols = [row["name"] for row in conn.execute(f"PRAGMA table_info({tabla})").fetchall()]
        if columna not in cols:
            conn.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo}")
    conn.commit()


def init_db():
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.commit()
    _aplicar_migraciones(conn)
    # Crear un usuario administrador por defecto si la tabla usuarios está vacía
    count = conn.execute("SELECT COUNT(*) c FROM usuarios").fetchone()["c"]
    if count == 0:
        conn.execute(
            "INSERT INTO usuarios (username, password_hash, rol) VALUES (?,?,?)",
            ("admin", generate_password_hash("admin123"), "admin"),
        )
        conn.commit()
        print("Usuario administrador creado -> usuario: admin / clave: admin123")
        print("IMPORTANTE: cambia esta clave desde la pantalla de Usuarios en cuanto entres.")
    conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Base de datos creada en: {DB_PATH}")
