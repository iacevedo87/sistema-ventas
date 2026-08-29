from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_connection, init_db
import plantillas
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "cambia-esta-clave-en-produccion")

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
        data = (request.form["nombre"], request.form.get("descripcion"),
                float(request.form.get("precio") or 0), int(request.form.get("stock") or 0),
                request.form.get("id_proveedor") or None)
        if edit_id:
            conn.execute("""UPDATE productos SET nombre=?, descripcion=?, precio=?, stock=?, id_proveedor=?
                             WHERE id_producto=?""", data + (edit_id,))
        else:
            conn.execute("""INSERT INTO productos (nombre, descripcion, precio, stock, id_proveedor)
                             VALUES (?,?,?,?,?)""", data)
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
    return render_template("productos.html", rows=rows, edit_row=edit_row, proveedores=proveedores_list)


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
            cant = int(cant)
            subtotal = prod["precio"] * cant
            total += subtotal
            detalles.append((pid, cant, prod["precio"]))

        if detalles:
            cur = conn.execute("INSERT INTO ventas (id_cliente, id_trabajador, total) VALUES (?,?,?)",
                                (id_cliente, id_trabajador, total))
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
