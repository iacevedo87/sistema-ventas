from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_connection, init_db
import plantillas
import os
import sqlite3
from datetime import date

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "cambia-esta-clave-en-produccion")

# La sesión NO es permanente: la cookie de sesión no lleva fecha de expiración,
# así que el navegador la borra al cerrarse por completo (no solo al cerrar la pestaña).
# Al volver a abrir el navegador, la app pedirá usuario y clave de nuevo.
app.config["SESSION_PERMANENT"] = False

init_db()

# Rutas que NO requieren haber iniciado sesión
RUTAS_PUBLICAS = {"login", "static"}


@app.before_request
def requerir_login():
    if request.endpoint in RUTAS_PUBLICAS or request.endpoint is None:
        return
    if not session.get("usuario"):
        return redirect(url_for("login"))


# ---------- LOGIN ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        conn = get_connection()
        user = conn.execute("SELECT * FROM usuarios WHERE username=?", (username,)).fetchone()
        conn.close()
        if user and check_password_hash(user["password_hash"], password):
            session.permanent = False
            session["usuario"] = user["username"]
            session["rol"] = user["rol"]
            return redirect(url_for("index"))
        flash("Usuario o clave incorrectos.")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------- DASHBOARD ----------
@app.route("/")
def index():
    conn = get_connection()
    stats = {
        "clientes": conn.execute("SELECT COUNT(*) c FROM clientes").fetchone()["c"],
        "proveedores": conn.execute("SELECT COUNT(*) c FROM proveedores").fetchone()["c"],
        "productos": conn.execute("SELECT COUNT(*) c FROM productos").fetchone()["c"],
        "trabajadores": conn.execute("SELECT COUNT(*) c FROM trabajadores").fetchone()["c"],
        "usuarios": conn.execute("SELECT COUNT(*) c FROM usuarios").fetchone()["c"],
        "ventas": conn.execute("SELECT COUNT(*) c FROM ventas").fetchone()["c"],
        "nomina": conn.execute("SELECT COUNT(*) c FROM nomina").fetchone()["c"],
        "compras": conn.execute("SELECT COUNT(*) c FROM compras_proveedores").fetchone()["c"],
    }
    conn.close()
    return render_template("index.html", stats=stats)


# ---------- CLIENTES ----------
@app.route("/clientes", methods=["GET", "POST"])
def clientes():
    conn = get_connection()
    if request.method == "POST":
        edit_id = request.form.get("id_cliente")
        data = (request.form["nombre"], request.form.get("telefono"),
                request.form.get("email"), request.form.get("direccion"))
        if edit_id:
            # numero_record NUNCA se toca aquí: una vez asignado, es permanente
            conn.execute("UPDATE clientes SET nombre=?, telefono=?, email=?, direccion=? WHERE id_cliente=?",
                         data + (edit_id,))
            id_cliente_actual = int(edit_id)
        else:
            siguiente = conn.execute(
                "SELECT COALESCE(MAX(numero_record), 0) + 1 AS n FROM clientes"
            ).fetchone()["n"]
            cur = conn.execute(
                "INSERT INTO clientes (numero_record, nombre, telefono, email, direccion) VALUES (?,?,?,?,?)",
                (siguiente,) + data)
            id_cliente_actual = cur.lastrowid

        # Archivos subidos junto con el formulario (labs, identificación, etc.) -> quedan en el expediente
        for archivo in request.files.getlist("documentos"):
            if archivo and archivo.filename:
                _guardar_documento_cliente(conn, id_cliente_actual, archivo)

        conn.commit()
        return redirect(url_for("clientes"))
    edit_row = None
    if request.args.get("edit"):
        edit_row = conn.execute("SELECT * FROM clientes WHERE id_cliente=?", (request.args["edit"],)).fetchone()
    rows = conn.execute("SELECT * FROM clientes ORDER BY id_cliente DESC").fetchall()
    conn.close()
    return render_template("clientes.html", rows=rows, edit_row=edit_row)


@app.route("/clientes/delete/<int:id_cliente>", methods=["POST"])
def delete_cliente(id_cliente):
    conn = get_connection()
    conn.execute("DELETE FROM clientes WHERE id_cliente=?", (id_cliente,))
    conn.commit()
    conn.close()
    return redirect(url_for("clientes"))


# ---------- DOCUMENTOS DEL EXPEDIENTE DEL PACIENTE ----------
# Igual que con la base de datos: si hay un disco persistente montado (variable PERSISTENT_DATA_DIR),
# los documentos de pacientes se guardan ahí para que no se pierdan con cada reinicio.
_PERSISTENT_DIR = os.environ.get("PERSISTENT_DATA_DIR")
if _PERSISTENT_DIR:
    UPLOAD_FOLDER = os.path.join(_PERSISTENT_DIR, "uploads", "clientes")
else:
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads", "clientes")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def _guardar_documento_cliente(conn, id_cliente, archivo):
    """Guarda un FileStorage en disco y registra la fila en documentos_clientes.
    Se usa tanto desde 'Nuevo cliente' como desde la pantalla de Documentos del expediente."""
    from werkzeug.utils import secure_filename
    nombre_seguro = secure_filename(archivo.filename)
    carpeta_cliente = os.path.join(UPLOAD_FOLDER, str(id_cliente))
    os.makedirs(carpeta_cliente, exist_ok=True)
    ruta_disco = os.path.join(carpeta_cliente, nombre_seguro)
    archivo.save(ruta_disco)
    ruta_relativa = f"{id_cliente}/{nombre_seguro}"
    conn.execute("""INSERT INTO documentos_clientes (id_cliente, nombre_archivo, ruta_archivo)
                     VALUES (?,?,?)""", (id_cliente, archivo.filename, ruta_relativa))


@app.route("/clientes/<int:id_cliente>/documentos", methods=["GET", "POST"])
def documentos_cliente(id_cliente):
    conn = get_connection()
    cliente = conn.execute("SELECT * FROM clientes WHERE id_cliente=?", (id_cliente,)).fetchone()
    if not cliente:
        conn.close()
        return redirect(url_for("clientes"))

    if request.method == "POST":
        for archivo in request.files.getlist("archivo"):
            if archivo and archivo.filename:
                _guardar_documento_cliente(conn, id_cliente, archivo)
        conn.commit()
        conn.close()
        return redirect(url_for("documentos_cliente", id_cliente=id_cliente))

    documentos = conn.execute(
        "SELECT * FROM documentos_clientes WHERE id_cliente=? ORDER BY id_documento DESC", (id_cliente,)
    ).fetchall()
    conn.close()
    return render_template("documentos_cliente.html", cliente=cliente, documentos=documentos)


@app.route("/clientes/documentos/<int:id_documento>/descargar")
def descargar_documento(id_documento):
    from flask import send_from_directory
    conn = get_connection()
    doc = conn.execute("SELECT * FROM documentos_clientes WHERE id_documento=?", (id_documento,)).fetchone()
    conn.close()
    if not doc:
        return redirect(url_for("clientes"))
    carpeta, archivo = os.path.split(doc["ruta_archivo"])
    return send_from_directory(os.path.join(UPLOAD_FOLDER, carpeta), archivo, as_attachment=True,
                                download_name=doc["nombre_archivo"])


@app.route("/clientes/documentos/<int:id_documento>/eliminar", methods=["POST"])
def eliminar_documento(id_documento):
    conn = get_connection()
    doc = conn.execute("SELECT * FROM documentos_clientes WHERE id_documento=?", (id_documento,)).fetchone()
    if doc:
        ruta_completa = os.path.join(UPLOAD_FOLDER, doc["ruta_archivo"])
        if os.path.exists(ruta_completa):
            os.remove(ruta_completa)
        id_cliente = doc["id_cliente"]
        conn.execute("DELETE FROM documentos_clientes WHERE id_documento=?", (id_documento,))
        conn.commit()
    else:
        id_cliente = None
    conn.close()
    return redirect(url_for("documentos_cliente", id_cliente=id_cliente) if id_cliente else url_for("clientes"))


# ---------- TARJETAS DE LA COMPAÑÍA ----------
@app.route("/tarjetas", methods=["GET", "POST"])
def tarjetas():
    conn = get_connection()
    if request.method == "POST":
        edit_id = request.form.get("id_tarjeta")
        data = (request.form["nombre"], request.form.get("banco"),
                request.form.get("ultimos4"), request.form.get("notas"))
        if edit_id:
            conn.execute("UPDATE tarjetas SET nombre=?, banco=?, ultimos4=?, notas=? WHERE id_tarjeta=?",
                         data + (edit_id,))
        else:
            conn.execute("INSERT INTO tarjetas (nombre, banco, ultimos4, notas) VALUES (?,?,?,?)", data)
        conn.commit()
        return redirect(url_for("tarjetas"))
    edit_row = None
    if request.args.get("edit"):
        edit_row = conn.execute("SELECT * FROM tarjetas WHERE id_tarjeta=?", (request.args["edit"],)).fetchone()
    rows = conn.execute("SELECT * FROM tarjetas ORDER BY nombre").fetchall()
    conn.close()
    return render_template("tarjetas.html", rows=rows, edit_row=edit_row)


@app.route("/tarjetas/delete/<int:id_tarjeta>", methods=["POST"])
def delete_tarjeta(id_tarjeta):
    conn = get_connection()
    conn.execute("DELETE FROM tarjetas WHERE id_tarjeta=?", (id_tarjeta,))
    conn.commit()
    conn.close()
    return redirect(url_for("tarjetas"))


# ---------- CATEGORÍAS DE PRODUCTO ----------
@app.route("/categorias/agregar", methods=["POST"])
def agregar_categoria():
    nombre = (request.form.get("nueva_categoria") or "").strip().upper()
    if nombre:
        conn = get_connection()
        conn.execute("INSERT OR IGNORE INTO categorias (nombre) VALUES (?)", (nombre,))
        conn.commit()
        conn.close()
    # Vuelve al formulario de productos, con la categoría recién creada ya seleccionable
    return redirect(url_for("productos", nueva_cat=nombre))


@app.route("/categorias/agregar-ajax", methods=["POST"])
def agregar_categoria_ajax():
    """Igual que /categorias/agregar pero responde en JSON, sin recargar la página
    (así no se pierden los demás campos que ya llenaste en el formulario de producto)."""
    from flask import jsonify
    nombre = (request.form.get("nueva_categoria") or "").strip().upper()
    if not nombre:
        return jsonify({"ok": False, "error": "Escribe un nombre de categoría."}), 400
    conn = get_connection()
    conn.execute("INSERT OR IGNORE INTO categorias (nombre) VALUES (?)", (nombre,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "nombre": nombre})


# ---------- PROVEEDORES ----------
@app.route("/proveedores", methods=["GET", "POST"])
def proveedores():
    conn = get_connection()
    if request.method == "POST":
        edit_id = request.form.get("id_proveedor")
        data = (request.form["nombre"], request.form.get("contacto"), request.form.get("telefono"),
                request.form.get("email"), request.form.get("direccion"))
        if edit_id:
            conn.execute("""UPDATE proveedores SET nombre=?, contacto=?, telefono=?, email=?, direccion=?
                             WHERE id_proveedor=?""", data + (edit_id,))
        else:
            conn.execute("""INSERT INTO proveedores (nombre, contacto, telefono, email, direccion)
                             VALUES (?,?,?,?,?)""", data)
        conn.commit()
        return redirect(url_for("proveedores"))
    edit_row = None
    if request.args.get("edit"):
        edit_row = conn.execute("SELECT * FROM proveedores WHERE id_proveedor=?", (request.args["edit"],)).fetchone()
    rows = conn.execute("SELECT * FROM proveedores ORDER BY id_proveedor DESC").fetchall()
    conn.close()
    return render_template("proveedores.html", rows=rows, edit_row=edit_row)


@app.route("/proveedores/delete/<int:id_proveedor>", methods=["POST"])
def delete_proveedor(id_proveedor):
    conn = get_connection()
    conn.execute("DELETE FROM proveedores WHERE id_proveedor=?", (id_proveedor,))
    conn.commit()
    conn.close()
    return redirect(url_for("proveedores"))


# ---------- PRODUCTOS ----------
@app.route("/productos", methods=["GET", "POST"])
def productos():
    conn = get_connection()
    if request.method == "POST":
        edit_id = request.form.get("id_producto")
        volumen = request.form.get("volumen_ml")
        data = (request.form["nombre"], request.form.get("descripcion"),
                request.form.get("categoria") or "MEDICATION",
                float(request.form.get("precio") or 0),
                float(request.form.get("costo_unitario") or 0),
                float(volumen) if volumen else None,
                int(float(request.form.get("stock") or 0)),
                request.form.get("lote_numero"),
                request.form.get("fecha_vencimiento") or None,
                request.form.get("id_proveedor") or None)
        if edit_id:
            conn.execute("""UPDATE productos SET nombre=?, descripcion=?, categoria=?, precio=?,
                             costo_unitario=?, volumen_ml=?, stock=?, lote_numero=?, fecha_vencimiento=?, id_proveedor=?
                             WHERE id_producto=?""", data + (edit_id,))
        else:
            conn.execute("""INSERT INTO productos
                             (nombre, descripcion, categoria, precio, costo_unitario, volumen_ml, stock,
                              lote_numero, fecha_vencimiento, id_proveedor)
                             VALUES (?,?,?,?,?,?,?,?,?,?)""", data)
        conn.commit()
        return redirect(url_for("productos"))
    edit_row = None
    if request.args.get("edit"):
        edit_row = conn.execute("SELECT * FROM productos WHERE id_producto=?", (request.args["edit"],)).fetchone()
    proveedores_list = conn.execute("SELECT * FROM proveedores ORDER BY nombre").fetchall()
    categorias_list = [r["nombre"] for r in conn.execute("SELECT nombre FROM categorias ORDER BY nombre").fetchall()]
    rows = conn.execute("""SELECT p.*, pr.nombre AS proveedor_nombre FROM productos p
                            LEFT JOIN proveedores pr ON p.id_proveedor = pr.id_proveedor
                            ORDER BY p.id_producto DESC""").fetchall()
    conn.close()
    return render_template("productos.html", rows=rows, edit_row=edit_row, proveedores=proveedores_list,
                           categorias=categorias_list, nueva_cat=request.args.get("nueva_cat"))


@app.route("/productos/delete/<int:id_producto>", methods=["POST"])
def delete_producto(id_producto):
    conn = get_connection()
    conn.execute("DELETE FROM productos WHERE id_producto=?", (id_producto,))
    conn.commit()
    conn.close()
    return redirect(url_for("productos"))


# ---------- TRABAJADORES ----------
@app.route("/trabajadores", methods=["GET", "POST"])
def trabajadores():
    conn = get_connection()
    if request.method == "POST":
        edit_id = request.form.get("id_trabajador")
        data = (request.form["nombre"], request.form.get("puesto"), request.form.get("telefono"),
                request.form.get("email"), request.form.get("fecha_contratacion"),
                float(request.form.get("salario") or 0))
        if edit_id:
            conn.execute("""UPDATE trabajadores SET nombre=?, puesto=?, telefono=?, email=?,
                             fecha_contratacion=?, salario=? WHERE id_trabajador=?""", data + (edit_id,))
        else:
            conn.execute("""INSERT INTO trabajadores (nombre, puesto, telefono, email, fecha_contratacion, salario)
                             VALUES (?,?,?,?,?,?)""", data)
        conn.commit()
        return redirect(url_for("trabajadores"))
    edit_row = None
    if request.args.get("edit"):
        edit_row = conn.execute("SELECT * FROM trabajadores WHERE id_trabajador=?", (request.args["edit"],)).fetchone()
    rows = conn.execute("SELECT * FROM trabajadores ORDER BY id_trabajador DESC").fetchall()
    conn.close()
    return render_template("trabajadores.html", rows=rows, edit_row=edit_row)


@app.route("/trabajadores/delete/<int:id_trabajador>", methods=["POST"])
def delete_trabajador(id_trabajador):
    conn = get_connection()
    conn.execute("DELETE FROM trabajadores WHERE id_trabajador=?", (id_trabajador,))
    conn.commit()
    conn.close()
    return redirect(url_for("trabajadores"))


# ---------- USUARIOS ----------
@app.route("/usuarios", methods=["GET", "POST"])
def usuarios():
    conn = get_connection()
    if request.method == "POST":
        edit_id = request.form.get("id_usuario")
        username = request.form["username"]
        rol = request.form.get("rol") or "empleado"
        id_trabajador = request.form.get("id_trabajador") or None
        password = request.form.get("password")
        try:
            if edit_id:
                if password:
                    conn.execute("""UPDATE usuarios SET username=?, password_hash=?, rol=?, id_trabajador=?
                                     WHERE id_usuario=?""",
                                 (username, generate_password_hash(password), rol, id_trabajador, edit_id))
                else:
                    conn.execute("UPDATE usuarios SET username=?, rol=?, id_trabajador=? WHERE id_usuario=?",
                                 (username, rol, id_trabajador, edit_id))
            else:
                conn.execute("""INSERT INTO usuarios (username, password_hash, rol, id_trabajador)
                                 VALUES (?,?,?,?)""",
                             (username, generate_password_hash(password or "changeme123"), rol, id_trabajador))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            flash(f'Ya existe un usuario con el nombre "{username}". Elige un nombre de usuario distinto.')
            return redirect(url_for("usuarios"))
        return redirect(url_for("usuarios"))
    edit_row = None
    if request.args.get("edit"):
        edit_row = conn.execute("SELECT * FROM usuarios WHERE id_usuario=?", (request.args["edit"],)).fetchone()
    trabajadores_list = conn.execute("SELECT * FROM trabajadores ORDER BY nombre").fetchall()
    rows = conn.execute("""SELECT u.*, t.nombre AS trabajador_nombre FROM usuarios u
                            LEFT JOIN trabajadores t ON u.id_trabajador = t.id_trabajador
                            ORDER BY u.id_usuario DESC""").fetchall()
    conn.close()
    return render_template("usuarios.html", rows=rows, edit_row=edit_row, trabajadores=trabajadores_list)


@app.route("/usuarios/delete/<int:id_usuario>", methods=["POST"])
def delete_usuario(id_usuario):
    conn = get_connection()
    conn.execute("DELETE FROM usuarios WHERE id_usuario=?", (id_usuario,))
    conn.commit()
    conn.close()
    return redirect(url_for("usuarios"))


# ---------- VENTAS ----------
@app.route("/ventas", methods=["GET", "POST"])
def ventas():
    conn = get_connection()
    if request.method == "POST":
        id_cliente = request.form.get("id_cliente") or None
        id_trabajador = request.form.get("id_trabajador") or None
        estado_pago = request.form.get("estado_pago") or "Paid"
        metodo_pago = request.form.get("metodo_pago") or None
        observaciones = request.form.get("observaciones") or None
        fecha = request.form.get("fecha") or date.today().isoformat()
        productos_ids = request.form.getlist("id_producto[]")
        cantidades = request.form.getlist("cantidad[]")
        precios_editados = request.form.getlist("precio_unitario[]")
        try:
            descuento_pct = float(request.form.get("descuento_porcentaje") or 0)
        except ValueError:
            descuento_pct = 0
        descuento_pct = max(0, min(100, descuento_pct))  # nunca negativo ni mayor a 100%

        detalles = []
        subtotal = 0.0
        for i, (pid, cant) in enumerate(zip(productos_ids, cantidades)):
            if not pid or not cant:
                continue
            prod = conn.execute("SELECT precio FROM productos WHERE id_producto=?", (pid,)).fetchone()
            if not prod:
                continue
            cant = float(cant)
            # Si el usuario ajustó el precio en la pantalla, se respeta ese valor;
            # si no, se usa el precio actual registrado en Productos.
            precio_editado = precios_editados[i] if i < len(precios_editados) and precios_editados[i] not in (None, "") else None
            precio_final = float(precio_editado) if precio_editado is not None else prod["precio"]
            subtotal += precio_final * cant
            detalles.append((pid, cant, precio_final))

        monto_descuento = subtotal * (descuento_pct / 100)
        total = subtotal - monto_descuento

        if detalles:
            cur = conn.execute(
                """INSERT INTO ventas (id_cliente, id_trabajador, subtotal, descuento_porcentaje, total,
                                        estado_pago, metodo_pago, fecha, observaciones)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (id_cliente, id_trabajador, subtotal, descuento_pct, total, estado_pago, metodo_pago,
                 fecha, observaciones))
            id_venta = cur.lastrowid
            for pid, cant, precio in detalles:
                conn.execute("""INSERT INTO detalle_ventas (id_venta, id_producto, cantidad, precio_unitario)
                                 VALUES (?,?,?,?)""", (id_venta, pid, cant, precio))
                conn.execute("UPDATE productos SET stock = stock - ? WHERE id_producto=?", (cant, pid))
            conn.commit()
        return redirect(url_for("ventas"))

    clientes_list = conn.execute("SELECT * FROM clientes ORDER BY nombre").fetchall()
    trabajadores_list = conn.execute("SELECT * FROM trabajadores ORDER BY nombre").fetchall()
    productos_list = conn.execute("SELECT * FROM productos ORDER BY nombre").fetchall()
    ventas_rows = conn.execute("""SELECT v.*, c.nombre AS cliente_nombre, t.nombre AS trabajador_nombre
                                   FROM ventas v
                                   LEFT JOIN clientes c ON v.id_cliente = c.id_cliente
                                   LEFT JOIN trabajadores t ON v.id_trabajador = t.id_trabajador
                                   ORDER BY v.fecha DESC, v.id_venta DESC""").fetchall()
    detalles_por_venta = {}
    for v in ventas_rows:
        dets = conn.execute("""SELECT d.*, p.nombre AS producto_nombre FROM detalle_ventas d
                                JOIN productos p ON d.id_producto = p.id_producto
                                WHERE d.id_venta=?""", (v["id_venta"],)).fetchall()
        detalles_por_venta[v["id_venta"]] = dets
    conn.close()
    return render_template("ventas.html", clientes=clientes_list, trabajadores=trabajadores_list,
                           productos=productos_list, ventas=ventas_rows, detalles=detalles_por_venta,
                           hoy=date.today().isoformat())


@app.route("/ventas/delete/<int:id_venta>", methods=["POST"])
def delete_venta(id_venta):
    conn = get_connection()
    conn.execute("DELETE FROM ventas WHERE id_venta=?", (id_venta,))
    conn.commit()
    conn.close()
    return redirect(url_for("ventas"))


# ---------- NOMINA ----------
@app.route("/nomina", methods=["GET", "POST"])
def nomina():
    conn = get_connection()
    if request.method == "POST":
        edit_id = request.form.get("id_nomina")
        bruto = float(request.form.get("salario_bruto") or 0)
        deducciones = float(request.form.get("deducciones") or 0)
        neto = bruto - deducciones
        data = (request.form["id_trabajador"], request.form.get("periodo"), bruto, deducciones, neto)
        if edit_id:
            conn.execute("""UPDATE nomina SET id_trabajador=?, periodo=?, salario_bruto=?, deducciones=?,
                             salario_neto=? WHERE id_nomina=?""", data + (edit_id,))
        else:
            conn.execute("""INSERT INTO nomina (id_trabajador, periodo, salario_bruto, deducciones, salario_neto)
                             VALUES (?,?,?,?,?)""", data)
        conn.commit()
        return redirect(url_for("nomina"))
    edit_row = None
    if request.args.get("edit"):
        edit_row = conn.execute("SELECT * FROM nomina WHERE id_nomina=?", (request.args["edit"],)).fetchone()
    trabajadores_list = conn.execute("SELECT * FROM trabajadores ORDER BY nombre").fetchall()
    rows = conn.execute("""SELECT n.*, t.nombre AS trabajador_nombre FROM nomina n
                            JOIN trabajadores t ON n.id_trabajador = t.id_trabajador
                            ORDER BY n.id_nomina DESC""").fetchall()
    conn.close()
    return render_template("nomina.html", rows=rows, edit_row=edit_row, trabajadores=trabajadores_list)


@app.route("/nomina/delete/<int:id_nomina>", methods=["POST"])
def delete_nomina(id_nomina):
    conn = get_connection()
    conn.execute("DELETE FROM nomina WHERE id_nomina=?", (id_nomina,))
    conn.commit()
    conn.close()
    return redirect(url_for("nomina"))


# ---------- PLANTILLAS PDF PARA SMS ----------
@app.route("/plantillas")
def plantillas_home():
    conn = get_connection()
    clientes_list = conn.execute("SELECT * FROM clientes ORDER BY nombre").fetchall()
    trabajadores_list = conn.execute("SELECT * FROM trabajadores ORDER BY nombre").fetchall()
    conn.close()
    return render_template("plantillas.html", clientes=clientes_list, trabajadores=trabajadores_list)


@app.route("/plantillas/pago", methods=["POST"])
def plantilla_pago():
    buf = plantillas.generar_aviso_pago(
        paciente=request.form.get("paciente", ""),
        monto=request.form.get("monto", ""),
    )
    return send_file(buf, mimetype="application/pdf", as_attachment=True,
                      download_name="aviso_de_pago.pdf")


@app.route("/plantillas/cita", methods=["POST"])
def plantilla_cita():
    buf = plantillas.generar_confirmacion_cita(
        paciente=request.form.get("paciente", ""),
        fecha=request.form.get("fecha", ""),
        hora=request.form.get("hora", ""),
        proveedor=request.form.get("proveedor", ""),
    )
    return send_file(buf, mimetype="application/pdf", as_attachment=True,
                      download_name="confirmacion_de_cita.pdf")


@app.route("/plantillas/promocion", methods=["POST"])
def plantilla_promocion():
    buf = plantillas.generar_promocion(titulo=request.form.get("titulo", "WEIGHT LOSS PROGRAM"))
    return send_file(buf, mimetype="application/pdf", as_attachment=True,
                      download_name="promocion.pdf")


@app.route("/plantillas/recibo", methods=["POST"])
def plantilla_recibo():
    buf = plantillas.generar_recibo_pago(
        paciente=request.form.get("paciente", ""),
        concepto=request.form.get("concepto", ""),
        monto=request.form.get("monto", ""),
        metodo=request.form.get("metodo", ""),
        fecha=request.form.get("fecha", ""),
    )
    return send_file(buf, mimetype="application/pdf", as_attachment=True,
                      download_name="recibo_de_pago.pdf")


@app.route("/plantillas/carta", methods=["POST"])
def plantilla_carta():
    buf = plantillas.generar_carta_personalizada(
        asunto=request.form.get("asunto", "Comunicado"),
        cuerpo=request.form.get("cuerpo", ""),
        paciente=request.form.get("paciente", ""),
    )
    nombre_archivo = (request.form.get("asunto") or "carta").strip().lower().replace(" ", "_")
    return send_file(buf, mimetype="application/pdf", as_attachment=True,
                      download_name=f"{nombre_archivo}.pdf")


# ---------- COMPRAS A PROVEEDORES ----------
@app.route("/compras", methods=["GET", "POST"])
def compras():
    conn = get_connection()
    if request.method == "POST":
        id_proveedor = request.form.get("id_proveedor") or None
        id_cliente = request.form.get("id_cliente") or None  # vacío = compra para stock/inventario
        id_producto = request.form["id_producto"]
        cantidad = float(request.form.get("cantidad") or 0)
        costo_unitario = float(request.form.get("costo_unitario") or 0)
        total = cantidad * costo_unitario
        numero_factura = request.form.get("numero_factura")
        tarjeta_usada = request.form.get("tarjeta_usada")
        estado_pago = request.form.get("estado_pago") or "Paid"
        fecha = request.form.get("fecha") or date.today().isoformat()

        conn.execute("""INSERT INTO compras_proveedores
                         (id_proveedor, id_cliente, id_producto, cantidad, costo_unitario, total,
                          numero_factura, tarjeta_usada, estado_pago, fecha)
                         VALUES (?,?,?,?,?,?,?,?,?,?)""",
                     (id_proveedor, id_cliente, id_producto, cantidad, costo_unitario, total,
                      numero_factura, tarjeta_usada, estado_pago, fecha))
        # Esta compra entra al inventario: sube el stock del producto
        conn.execute("UPDATE productos SET stock = stock + ? WHERE id_producto=?", (cantidad, id_producto))
        conn.commit()
        return redirect(url_for("compras"))

    proveedores_list = conn.execute("SELECT * FROM proveedores ORDER BY nombre").fetchall()
    clientes_list = conn.execute("SELECT * FROM clientes ORDER BY nombre").fetchall()
    productos_list = conn.execute("SELECT * FROM productos ORDER BY nombre").fetchall()
    rows = conn.execute("""SELECT c.*, pr.nombre AS proveedor_nombre, cl.nombre AS cliente_nombre,
                                   p.nombre AS producto_nombre
                            FROM compras_proveedores c
                            LEFT JOIN proveedores pr ON c.id_proveedor = pr.id_proveedor
                            LEFT JOIN clientes cl ON c.id_cliente = cl.id_cliente
                            JOIN productos p ON c.id_producto = p.id_producto
                            ORDER BY c.fecha DESC, c.id_compra DESC""").fetchall()
    tarjetas_list = conn.execute("SELECT * FROM tarjetas ORDER BY nombre").fetchall()
    conn.close()
    return render_template("compras.html", rows=rows, proveedores=proveedores_list, hoy=date.today().isoformat(),
                           clientes=clientes_list, productos=productos_list, tarjetas=tarjetas_list)


@app.route("/compras/delete/<int:id_compra>", methods=["POST"])
def delete_compra(id_compra):
    conn = get_connection()
    compra = conn.execute("SELECT * FROM compras_proveedores WHERE id_compra=?", (id_compra,)).fetchone()
    if compra:
        # revertir el stock que había sumado esta compra
        conn.execute("UPDATE productos SET stock = stock - ? WHERE id_producto=?",
                     (compra["cantidad"], compra["id_producto"]))
        conn.execute("DELETE FROM compras_proveedores WHERE id_compra=?", (id_compra,))
        conn.commit()
    conn.close()
    return redirect(url_for("compras"))


# ---------- INVENTARIO ----------
@app.route("/inventario")
def inventario():
    conn = get_connection()
    rows = conn.execute("""SELECT p.*, pr.nombre AS proveedor_nombre FROM productos p
                            LEFT JOIN proveedores pr ON p.id_proveedor = pr.id_proveedor
                            ORDER BY p.stock ASC""").fetchall()
    conn.close()
    valor_total_inventario = sum((r["stock"] or 0) * (r["costo_unitario"] or 0) for r in rows)
    return render_template("inventario.html", rows=rows, valor_total_inventario=valor_total_inventario)


# ---------- REPORTES: PANEL CENTRAL ----------
@app.route("/reportes")
def reportes():
    return render_template("reportes_hub.html")


def _rango_fechas():
    """Lee ?desde=YYYY-MM-DD&hasta=YYYY-MM-DD de la URL; None si no se especifican (=todo)."""
    desde = request.args.get("desde") or None
    hasta = request.args.get("hasta") or None
    return desde, hasta


def _filtro_fecha_sql(columna, desde, hasta):
    condiciones, params = [], []
    if desde:
        condiciones.append(f"{columna} >= ?")
        params.append(desde)
    if hasta:
        condiciones.append(f"{columna} <= ?")
        params.append(hasta)
    return condiciones, params


# ---------- REPORTE 1: RESUMEN MENSUAL (ventas, compras y nómina por fecha, con corte) ----------
@app.route("/reportes/resumen-mensual")
def reporte_resumen_mensual():
    conn = get_connection()

    ventas_por_fecha = conn.execute("""
        SELECT fecha, SUM(total) AS total FROM ventas WHERE fecha IS NOT NULL GROUP BY fecha
    """).fetchall()
    compras_por_fecha = conn.execute("""
        SELECT fecha, SUM(total) AS total FROM compras_proveedores WHERE fecha IS NOT NULL GROUP BY fecha
    """).fetchall()
    nomina_por_fecha = conn.execute("""
        SELECT fecha_pago AS fecha, SUM(salario_neto) AS total FROM nomina WHERE fecha_pago IS NOT NULL GROUP BY fecha_pago
    """).fetchall()
    nomina_fija_mensual = conn.execute(
        "SELECT COALESCE(SUM(salario), 0) AS total FROM trabajadores"
    ).fetchone()["total"]
    conn.close()

    por_fecha = {}
    for row in ventas_por_fecha:
        por_fecha.setdefault(row["fecha"], {"ventas": 0, "compras": 0, "nomina": 0})
        por_fecha[row["fecha"]]["ventas"] = row["total"] or 0
    for row in compras_por_fecha:
        por_fecha.setdefault(row["fecha"], {"ventas": 0, "compras": 0, "nomina": 0})
        por_fecha[row["fecha"]]["compras"] = row["total"] or 0
    for row in nomina_por_fecha:
        por_fecha.setdefault(row["fecha"], {"ventas": 0, "compras": 0, "nomina": 0})
        por_fecha[row["fecha"]]["nomina"] = row["total"] or 0

    meses = {}
    for fecha, movimientos in por_fecha.items():
        mes = fecha[:7]
        meses.setdefault(mes, {"dias": [], "total_ventas": 0, "total_compras": 0, "total_nomina": 0})
        ganancia_bruta = movimientos["ventas"] - movimientos["compras"]
        ganancia_neta_dia = ganancia_bruta - movimientos["nomina"]
        meses[mes]["dias"].append({
            "fecha": fecha, "ventas": movimientos["ventas"], "compras": movimientos["compras"],
            "ganancia_bruta": ganancia_bruta, "nomina": movimientos["nomina"], "ganancia_neta": ganancia_neta_dia,
        })
        meses[mes]["total_ventas"] += movimientos["ventas"]
        meses[mes]["total_compras"] += movimientos["compras"]
        meses[mes]["total_nomina"] += movimientos["nomina"]

    reporte_meses = []
    for mes in sorted(meses.keys(), reverse=True):
        datos_mes = meses[mes]
        datos_mes["dias"].sort(key=lambda d: d["fecha"], reverse=True)
        total_ganancia_bruta = datos_mes["total_ventas"] - datos_mes["total_compras"]
        corte_ganancia_neta = total_ganancia_bruta - datos_mes["total_nomina"]
        reporte_meses.append({
            "mes": mes, "dias": datos_mes["dias"], "total_ventas": datos_mes["total_ventas"],
            "total_compras": datos_mes["total_compras"], "total_ganancia_bruta": total_ganancia_bruta,
            "total_nomina": datos_mes["total_nomina"], "corte_ganancia_neta": corte_ganancia_neta,
        })

    return render_template("reportes.html", meses=reporte_meses, nomina_fija_mensual=nomina_fija_mensual)


# ---------- REPORTE 2: TRANSACCIONES POR TARJETA ----------
@app.route("/reportes/tarjetas")
def reporte_tarjetas():
    conn = get_connection()
    desde, hasta = _rango_fechas()
    tarjeta_filtro = request.args.get("tarjeta") or ""

    condiciones, params = _filtro_fecha_sql("c.fecha", desde, hasta)
    if tarjeta_filtro:
        condiciones.append("c.tarjeta_usada = ?")
        params.append(tarjeta_filtro)
    where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""

    rows = conn.execute(f"""
        SELECT c.*, pr.nombre AS proveedor_nombre, p.nombre AS producto_nombre
        FROM compras_proveedores c
        LEFT JOIN proveedores pr ON c.id_proveedor = pr.id_proveedor
        JOIN productos p ON c.id_producto = p.id_producto
        {where}
        ORDER BY c.fecha DESC
    """, params).fetchall()

    tarjetas_list = conn.execute("SELECT * FROM tarjetas ORDER BY nombre").fetchall()
    conn.close()

    resumen_por_tarjeta = {}
    for r in rows:
        clave = r["tarjeta_usada"] or "Sin especificar"
        resumen_por_tarjeta.setdefault(clave, 0)
        resumen_por_tarjeta[clave] += r["total"]

    total_general = sum(r["total"] for r in rows)
    return render_template("reporte_tarjetas.html", rows=rows, tarjetas=tarjetas_list,
                           resumen=resumen_por_tarjeta, total_general=total_general,
                           desde=desde, hasta=hasta, tarjeta_filtro=tarjeta_filtro)


# ---------- REPORTE 3: PACIENTES x PRODUCTOS, POR FECHA ----------
@app.route("/reportes/pacientes-productos")
def reporte_pacientes_productos():
    conn = get_connection()
    desde, hasta = _rango_fechas()
    id_cliente_filtro = request.args.get("id_cliente") or ""

    condiciones, params = _filtro_fecha_sql("v.fecha", desde, hasta)
    if id_cliente_filtro:
        condiciones.append("v.id_cliente = ?")
        params.append(id_cliente_filtro)
    where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""

    rows = conn.execute(f"""
        SELECT v.fecha, c.nombre AS cliente_nombre, c.numero_record, p.nombre AS producto_nombre,
               d.cantidad, d.precio_unitario, (d.cantidad * d.precio_unitario) AS subtotal, v.estado_pago
        FROM detalle_ventas d
        JOIN ventas v ON d.id_venta = v.id_venta
        LEFT JOIN clientes c ON v.id_cliente = c.id_cliente
        JOIN productos p ON d.id_producto = p.id_producto
        {where}
        ORDER BY v.fecha DESC, c.nombre ASC
    """, params).fetchall()

    clientes_list = conn.execute("SELECT * FROM clientes ORDER BY nombre").fetchall()
    conn.close()
    return render_template("reporte_pacientes_productos.html", rows=rows, clientes=clientes_list,
                           desde=desde, hasta=hasta, id_cliente_filtro=id_cliente_filtro)


# ---------- REPORTE 4: PAGO DE NÓMINA POR FECHA ----------
@app.route("/reportes/nomina")
def reporte_nomina():
    conn = get_connection()
    desde, hasta = _rango_fechas()
    id_trabajador_filtro = request.args.get("id_trabajador") or ""

    condiciones, params = _filtro_fecha_sql("n.fecha_pago", desde, hasta)
    if id_trabajador_filtro:
        condiciones.append("n.id_trabajador = ?")
        params.append(id_trabajador_filtro)
    where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""

    rows = conn.execute(f"""
        SELECT n.*, t.nombre AS trabajador_nombre FROM nomina n
        JOIN trabajadores t ON n.id_trabajador = t.id_trabajador
        {where}
        ORDER BY n.fecha_pago DESC
    """, params).fetchall()

    trabajadores_list = conn.execute("SELECT * FROM trabajadores ORDER BY nombre").fetchall()
    conn.close()
    total_bruto = sum(r["salario_bruto"] for r in rows)
    total_deducciones = sum(r["deducciones"] for r in rows)
    total_neto = sum(r["salario_neto"] for r in rows)
    return render_template("reporte_nomina.html", rows=rows, trabajadores=trabajadores_list,
                           desde=desde, hasta=hasta, id_trabajador_filtro=id_trabajador_filtro,
                           total_bruto=total_bruto, total_deducciones=total_deducciones, total_neto=total_neto)


# ---------- REPORTE 5: GANANCIA NETA POR PRODUCTO VENDIDO ----------
@app.route("/reportes/ganancias-producto")
def reporte_ganancias_producto():
    conn = get_connection()
    desde, hasta = _rango_fechas()
    id_producto_filtro = request.args.get("id_producto") or ""

    condiciones, params = _filtro_fecha_sql("v.fecha", desde, hasta)
    if id_producto_filtro:
        condiciones.append("d.id_producto = ?")
        params.append(id_producto_filtro)
    where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""

    rows = conn.execute(f"""
        SELECT v.fecha, p.nombre AS producto_nombre, d.cantidad, d.precio_unitario,
               p.costo_unitario, (d.cantidad * d.precio_unitario) AS total_venta,
               (d.cantidad * p.costo_unitario) AS total_costo,
               (d.cantidad * (d.precio_unitario - p.costo_unitario)) AS ganancia
        FROM detalle_ventas d
        JOIN ventas v ON d.id_venta = v.id_venta
        JOIN productos p ON d.id_producto = p.id_producto
        {where}
        ORDER BY v.fecha DESC
    """, params).fetchall()

    productos_list = conn.execute("SELECT * FROM productos ORDER BY nombre").fetchall()
    conn.close()
    total_ventas = sum(r["total_venta"] for r in rows)
    total_costo = sum(r["total_costo"] for r in rows)
    total_ganancia = sum(r["ganancia"] for r in rows)
    return render_template("reporte_ganancias_producto.html", rows=rows, productos=productos_list,
                           desde=desde, hasta=hasta, id_producto_filtro=id_producto_filtro,
                           total_ventas=total_ventas, total_costo=total_costo, total_ganancia=total_ganancia)


# ---------- REPORTE 6: GASTO TOTAL Y GANANCIA TOTAL ----------
@app.route("/reportes/gastos-ganancias")
def reporte_gastos_ganancias():
    conn = get_connection()
    desde, hasta = _rango_fechas()

    cond_v, params_v = _filtro_fecha_sql("fecha", desde, hasta)
    where_v = ("WHERE " + " AND ".join(cond_v)) if cond_v else ""
    total_ventas = conn.execute(f"SELECT COALESCE(SUM(total),0) t FROM ventas {where_v}", params_v).fetchone()["t"]

    cond_c, params_c = _filtro_fecha_sql("fecha", desde, hasta)
    where_c = ("WHERE " + " AND ".join(cond_c)) if cond_c else ""
    total_compras = conn.execute(f"SELECT COALESCE(SUM(total),0) t FROM compras_proveedores {where_c}", params_c).fetchone()["t"]

    cond_n, params_n = _filtro_fecha_sql("fecha_pago", desde, hasta)
    where_n = ("WHERE " + " AND ".join(cond_n)) if cond_n else ""
    total_nomina = conn.execute(f"SELECT COALESCE(SUM(salario_neto),0) t FROM nomina {where_n}", params_n).fetchone()["t"]

    conn.close()
    gasto_total = total_compras + total_nomina
    ganancia_total = total_ventas - gasto_total
    return render_template("reporte_gastos_ganancias.html", total_ventas=total_ventas, total_compras=total_compras,
                           total_nomina=total_nomina, gasto_total=gasto_total, ganancia_total=ganancia_total,
                           desde=desde, hasta=hasta)


# ---------- REPORTE 7: INVOICES ----------
@app.route("/reportes/invoices")
def reporte_invoices():
    conn = get_connection()
    desde, hasta = _rango_fechas()
    id_cliente_filtro = request.args.get("id_cliente") or ""

    condiciones, params = _filtro_fecha_sql("v.fecha", desde, hasta)
    if id_cliente_filtro:
        condiciones.append("v.id_cliente = ?")
        params.append(id_cliente_filtro)
    where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""

    rows = conn.execute(f"""
        SELECT v.*, c.nombre AS cliente_nombre, c.numero_record, t.nombre AS trabajador_nombre
        FROM ventas v
        LEFT JOIN clientes c ON v.id_cliente = c.id_cliente
        LEFT JOIN trabajadores t ON v.id_trabajador = t.id_trabajador
        {where}
        ORDER BY v.fecha DESC, v.id_venta DESC
    """, params).fetchall()

    clientes_list = conn.execute("SELECT * FROM clientes ORDER BY nombre").fetchall()
    conn.close()
    total_facturado = sum(r["total"] for r in rows)
    return render_template("reporte_invoices.html", rows=rows, clientes=clientes_list,
                           desde=desde, hasta=hasta, id_cliente_filtro=id_cliente_filtro,
                           total_facturado=total_facturado)


@app.route("/ventas/<int:id_venta>/invoice")
def descargar_invoice(id_venta):
    conn = get_connection()
    venta = conn.execute("""
        SELECT v.*, c.nombre AS cliente_nombre, c.numero_record, t.nombre AS trabajador_nombre
        FROM ventas v
        LEFT JOIN clientes c ON v.id_cliente = c.id_cliente
        LEFT JOIN trabajadores t ON v.id_trabajador = t.id_trabajador
        WHERE v.id_venta = ?
    """, (id_venta,)).fetchone()
    if not venta:
        conn.close()
        return redirect(url_for("reporte_invoices"))

    detalle_rows = conn.execute("""
        SELECT d.*, p.nombre AS producto_nombre FROM detalle_ventas d
        JOIN productos p ON d.id_producto = p.id_producto
        WHERE d.id_venta = ?
    """, (id_venta,)).fetchall()
    conn.close()

    items = [{
        "nombre": d["producto_nombre"],
        "cantidad": d["cantidad"],
        "precio_unitario": d["precio_unitario"],
        "subtotal_linea": d["cantidad"] * d["precio_unitario"],
    } for d in detalle_rows]

    buf = plantillas.generar_invoice(
        id_venta=venta["id_venta"],
        fecha=venta["fecha"],
        paciente=venta["cliente_nombre"],
        numero_record=venta["numero_record"],
        vendedor=venta["trabajador_nombre"],
        items=items,
        subtotal=venta["subtotal"] or venta["total"],
        descuento_porcentaje=venta["descuento_porcentaje"] or 0,
        total=venta["total"],
        estado_pago=venta["estado_pago"],
        metodo_pago=venta["metodo_pago"],
        observaciones=venta["observaciones"],
    )
    return send_file(buf, mimetype="application/pdf", as_attachment=True,
                      download_name=f"invoice_{id_venta:06d}.pdf")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
