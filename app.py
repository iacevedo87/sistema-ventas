from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_connection, init_db
import plantillas
import os

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
            conn.execute("UPDATE clientes SET nombre=?, telefono=?, email=?, direccion=? WHERE id_cliente=?",
                         data + (edit_id,))
        else:
            conn.execute("INSERT INTO clientes (nombre, telefono, email, direccion) VALUES (?,?,?,?)", data)
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
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads", "clientes")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@app.route("/clientes/<int:id_cliente>/documentos", methods=["GET", "POST"])
def documentos_cliente(id_cliente):
    conn = get_connection()
    cliente = conn.execute("SELECT * FROM clientes WHERE id_cliente=?", (id_cliente,)).fetchone()
    if not cliente:
        conn.close()
        return redirect(url_for("clientes"))

    if request.method == "POST":
        archivo = request.files.get("archivo")
        if archivo and archivo.filename:
            from werkzeug.utils import secure_filename
            nombre_seguro = secure_filename(archivo.filename)
            carpeta_cliente = os.path.join(UPLOAD_FOLDER, str(id_cliente))
            os.makedirs(carpeta_cliente, exist_ok=True)
            ruta_disco = os.path.join(carpeta_cliente, nombre_seguro)
            archivo.save(ruta_disco)
            ruta_relativa = f"{id_cliente}/{nombre_seguro}"
            conn.execute("""INSERT INTO documentos_clientes (id_cliente, nombre_archivo, ruta_archivo)
                             VALUES (?,?,?)""", (id_cliente, archivo.filename, ruta_relativa))
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
CATEGORIAS_PRODUCTO = ["MEDICATION", "SUPPLY", "TRANSPORTATION", "SERVICE", "OTHER"]


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
                request.form.get("id_proveedor") or None)
        if edit_id:
            conn.execute("""UPDATE productos SET nombre=?, descripcion=?, categoria=?, precio=?,
                             costo_unitario=?, volumen_ml=?, stock=?, id_proveedor=?
                             WHERE id_producto=?""", data + (edit_id,))
        else:
            conn.execute("""INSERT INTO productos
                             (nombre, descripcion, categoria, precio, costo_unitario, volumen_ml, stock, id_proveedor)
                             VALUES (?,?,?,?,?,?,?,?)""", data)
        conn.commit()
        return redirect(url_for("productos"))
    edit_row = None
    if request.args.get("edit"):
        edit_row = conn.execute("SELECT * FROM productos WHERE id_producto=?", (request.args["edit"],)).fetchone()
    proveedores_list = conn.execute("SELECT * FROM proveedores ORDER BY nombre").fetchall()
    rows = conn.execute("""SELECT p.*, pr.nombre AS proveedor_nombre FROM productos p
                            LEFT JOIN proveedores pr ON p.id_proveedor = pr.id_proveedor
                            ORDER BY p.id_producto DESC""").fetchall()
    conn.close()
    return render_template("productos.html", rows=rows, edit_row=edit_row, proveedores=proveedores_list,
                           categorias=CATEGORIAS_PRODUCTO)


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
        productos_ids = request.form.getlist("id_producto[]")
        cantidades = request.form.getlist("cantidad[]")

        detalles = []
        total = 0.0
        for pid, cant in zip(productos_ids, cantidades):
            if not pid or not cant:
                continue
            prod = conn.execute("SELECT precio FROM productos WHERE id_producto=?", (pid,)).fetchone()
            if not prod:
                continue
            cant = float(cant)
            subtotal = prod["precio"] * cant
            total += subtotal
            detalles.append((pid, cant, prod["precio"]))

        if detalles:
            cur = conn.execute(
                "INSERT INTO ventas (id_cliente, id_trabajador, total, estado_pago, metodo_pago) VALUES (?,?,?,?,?)",
                (id_cliente, id_trabajador, total, estado_pago, metodo_pago))
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
                                   ORDER BY v.id_venta DESC""").fetchall()
    detalles_por_venta = {}
    for v in ventas_rows:
        dets = conn.execute("""SELECT d.*, p.nombre AS producto_nombre FROM detalle_ventas d
                                JOIN productos p ON d.id_producto = p.id_producto
                                WHERE d.id_venta=?""", (v["id_venta"],)).fetchall()
        detalles_por_venta[v["id_venta"]] = dets
    conn.close()
    return render_template("ventas.html", clientes=clientes_list, trabajadores=trabajadores_list,
                           productos=productos_list, ventas=ventas_rows, detalles=detalles_por_venta)


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

        conn.execute("""INSERT INTO compras_proveedores
                         (id_proveedor, id_cliente, id_producto, cantidad, costo_unitario, total,
                          numero_factura, tarjeta_usada, estado_pago)
                         VALUES (?,?,?,?,?,?,?,?,?)""",
                     (id_proveedor, id_cliente, id_producto, cantidad, costo_unitario, total,
                      numero_factura, tarjeta_usada, estado_pago))
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
                            ORDER BY c.id_compra DESC""").fetchall()
    conn.close()
    return render_template("compras.html", rows=rows, proveedores=proveedores_list,
                           clientes=clientes_list, productos=productos_list)


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


# ---------- REPORTES: VENTAS POR MES Y GANANCIA NETA ----------
@app.route("/reportes")
def reportes():
    conn = get_connection()

    ventas_por_mes = conn.execute("""
        SELECT strftime('%Y-%m', fecha) AS mes, SUM(total) AS total_ventas
        FROM ventas
        GROUP BY mes
    """).fetchall()

    nomina_por_mes = conn.execute("""
        SELECT strftime('%Y-%m', fecha_pago) AS mes, SUM(salario_neto) AS total_nomina
        FROM nomina
        GROUP BY mes
    """).fetchall()

    # Nómina fija mensual: suma del salario de todos los trabajadores activos
    nomina_fija_mensual = conn.execute(
        "SELECT COALESCE(SUM(salario), 0) AS total FROM trabajadores"
    ).fetchone()["total"]

    conn.close()

    datos = {}
    for row in ventas_por_mes:
        if row["mes"]:
            datos[row["mes"]] = {"ventas": row["total_ventas"] or 0, "nomina": 0}
    for row in nomina_por_mes:
        if row["mes"]:
            datos.setdefault(row["mes"], {"ventas": 0, "nomina": 0})
            datos[row["mes"]]["nomina"] = row["total_nomina"] or 0

    meses = []
    for mes in sorted(datos.keys(), reverse=True):
        ventas = datos[mes]["ventas"]
        nomina_pagada = datos[mes]["nomina"]
        ganancia = ventas - nomina_pagada
        meses.append({
            "mes": mes,
            "ventas": ventas,
            "nomina_pagada": nomina_pagada,
            "ganancia": ganancia,
        })

    return render_template("reportes.html", meses=meses, nomina_fija_mensual=nomina_fija_mensual)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
