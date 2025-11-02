# ====================================================
# 🧾 SISTEMA DE FACTURACIÓN ELECTRÓNICA – Flask + SQLAlchemy
# ====================================================
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename
from config import Config
from models import db, User, Customer, Product, Stock, Invoice, InvoiceItem
from sqlalchemy.orm import joinedload
from datetime import date  # para fecha en ventas_nueva
from decimal import Decimal  # para manejar cantidades en inventario
import os
# ====================================================
# 🧾 GENERAR PDF DE FACTURA
# ====================================================
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
from flask import make_response

# ====================================================
# ⚙️ CONFIGURACIÓN PRINCIPAL
# ====================================================
app = Flask(__name__)
app.config.from_object(Config)

# 📂 Carpeta para imágenes de los productos
UPLOAD_FOLDER = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    """Valida extensión de imagen"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ====================================================
# 🔐 BASE DE DATOS Y LOGIN
# ====================================================
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ====================================================
# 🧩 RUTAS PRINCIPALES
# ====================================================
@app.route('/')
def index():
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Inicio de sesión"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash('Inicio de sesión exitoso ✅', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Usuario o contraseña incorrectos ❌', 'danger')

    return render_template('login.html')


@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', user=current_user)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Has cerrado sesión correctamente 👋', 'info')
    return redirect(url_for('login'))


# ====================================================
# 💰 MÓDULO DE VENTAS / FACTURAS
# ====================================================
@app.route('/ventas')
@login_required
def ventas():
    """Listado de facturas"""
    facturas = Invoice.query.options(joinedload(Invoice.customer)).all()
    return render_template('ventas.html', facturas=facturas, user=current_user)


@app.route('/ventas/nueva', methods=['GET', 'POST'])
@login_required
def ventas_nueva():
    """Crea una nueva factura"""
    clientes = Customer.query.all()
    productos = Product.query.options(joinedload(Product.stock_items)).all()

    if request.method == 'POST':
        # 1. Cliente
        try:
            cliente_id = int(request.form.get('cliente', 0))
        except ValueError:
            flash('Cliente inválido ❌', 'danger')
            return redirect(url_for('ventas_nueva'))

        # 2. Items de la factura
        items = []
        subtotal = Decimal('0.00')
        iva_total = Decimal('0.00')

        for key in request.form:
            if key.startswith('producto_'):
                product_id = int(key.split('_')[1])

                # cantidad asociada al producto_X
                try:
                    cantidad = Decimal(str(request.form.get(f'cantidad_{product_id}', 0)))
                except Exception:
                    cantidad = Decimal('0')

                if cantidad <= 0:
                    continue

                producto = Product.query.get(product_id)
                if not producto:
                    continue

                # precio_unitario y tax pueden ser float, convierto a Decimal
                precio_unitario = Decimal(str(producto.price))
                subtotal_item = precio_unitario * cantidad
                iva_item = (Decimal(str(producto.tax)) / Decimal('100')) * subtotal_item

                subtotal += subtotal_item
                iva_total += iva_item

                items.append({
                    'product': producto,
                    'quantity': cantidad,
                    'price': precio_unitario,
                    'subtotal': subtotal_item
                })

        if not items:
            flash('Debes seleccionar al menos un producto 📦', 'warning')
            return redirect(url_for('ventas_nueva'))

        total = subtotal + iva_total

        # 3. Crear la factura principal
        nueva_factura = Invoice(
            code="TEMP",
            customer_id=cliente_id,
            user_id=current_user.id,
            subtotal=float(subtotal),      # guardamos como float en BD
            tax_total=float(iva_total),
            total=float(total)
        )
        db.session.add(nueva_factura)
        db.session.flush()  # genera ID temporalmente antes del commit

        # 4. Generar código final basado en ID
        nueva_factura.code = f"F-{nueva_factura.id:05d}"

        # 5. Insertar detalles (InvoiceItem) y descontar stock
        for item in items:
            detalle = InvoiceItem(
                invoice_id=nueva_factura.id,
                product_id=item['product'].id,
                quantity=float(item['quantity']),
                price=float(item['price']),
                subtotal=float(item['subtotal'])
            )
            db.session.add(detalle)

            # Descontar stock del producto vendido
            stock = Stock.query.filter_by(product_id=item['product'].id).first()
            if stock:
                # stock.qty puede ser Decimal. Lo convertimos y restamos en Decimal
                stock_actual = Decimal(str(stock.qty))
                nuevo_stock = stock_actual - item['quantity']
                if nuevo_stock < 0:
                    nuevo_stock = Decimal('0.00')
                # guardamos como float para no chocar con tipos
                stock.qty = float(nuevo_stock)

        # 6. Guardar todo
        db.session.commit()

        flash(f'Factura creada correctamente ✅ Código: {nueva_factura.code}', 'success')
        return redirect(url_for('ventas'))

    # GET → mostrar formulario
    return render_template(
        'ventas_nueva.html',
        clientes=clientes,
        productos=productos,
        user=current_user,
        date=date  # variable para {{ date.today() }} en la vista
    )


@app.route('/ventas/<int:id>')
@login_required
def ventas_detalle(id):
    """Detalle de una factura específica"""
    factura = (
        Invoice.query
        .options(
            joinedload(Invoice.customer),
            joinedload(Invoice.items).joinedload(InvoiceItem.product)
        )
        .filter_by(id=id)
        .first_or_404()
    )

    return render_template(
        'ventas_detalle.html',
        factura=factura,
        user=current_user
    )

@app.route('/ventas/eliminar/<int:id>', methods=['POST'])
@login_required
def ventas_eliminar(id):
    """Elimina una factura existente, junto con sus items"""
    factura = Invoice.query.get_or_404(id)

    # Protección: no permitir eliminar si ya está registrada oficialmente
    # (puedes quitar esta parte si no manejas estados de facturación)
    # if factura.estado == 'emitida':
    #     flash('❌ No se puede eliminar una factura ya emitida.', 'danger')
    #     return redirect(url_for('ventas'))

    try:
        # Al tener cascade="all, delete-orphan" en Invoice.items,
        # los InvoiceItem se eliminarán automáticamente.
        db.session.delete(factura)
        db.session.commit()
        flash(f'Factura {factura.code} eliminada correctamente 🗑️', 'success')
    except Exception as e:
        db.session.rollback()
        flash('⚠️ No se pudo eliminar la factura. Verifica que no esté bloqueada.', 'danger')
        print(e)

    return redirect(url_for('ventas'))



# ====================================================
# 👥 MÓDULO DE CLIENTES
# ====================================================
@app.route('/clientes')
@login_required
def clientes_listar():
    clientes = Customer.query.all()
    return render_template('clientes.html', clientes=clientes, user=current_user)


@app.route('/clientes/agregar', methods=['POST'])
@login_required
def clientes_agregar():
    nuevo = Customer(
        name=request.form.get('nombre', ''),
        dui=request.form.get('dui', ''),
        nit=request.form.get('nit', ''),
        email=request.form.get('email', ''),
        phone=request.form.get('telefono', ''),
        address=request.form.get('direccion', '')
    )
    db.session.add(nuevo)
    db.session.commit()
    flash('Cliente agregado correctamente ✅', 'success')
    return redirect(url_for('clientes_listar'))


@app.route('/clientes/editar/<int:id>', methods=['POST'])
@login_required
def clientes_editar(id):
    cliente = Customer.query.get_or_404(id)
    cliente.name = request.form.get('nombre', cliente.name)
    cliente.dui = request.form.get('dui', cliente.dui)
    cliente.nit = request.form.get('nit', cliente.nit)
    cliente.email = request.form.get('email', cliente.email)
    cliente.phone = request.form.get('telefono', cliente.phone)
    cliente.address = request.form.get('direccion', cliente.address)
    db.session.commit()
    flash('Cliente actualizado correctamente ✏️', 'info')
    return redirect(url_for('clientes_listar'))


@app.route('/clientes/eliminar/<int:id>')
@login_required
def clientes_eliminar(id):
    cliente = Customer.query.get_or_404(id)

    # Verificar si tiene facturas asociadas
    facturas = Invoice.query.filter_by(customer_id=id).count()
    if facturas > 0:
        flash('❌ No se puede eliminar este cliente porque tiene facturas asociadas.', 'danger')
        return redirect(url_for('clientes_listar'))

    db.session.delete(cliente)
    db.session.commit()
    flash('Cliente eliminado correctamente ✅', 'success')
    return redirect(url_for('clientes_listar'))



# ====================================================
# 📦 MÓDULO DE PRODUCTOS
# ====================================================
@app.route('/productos')
@login_required
def productos_listar():
    productos = Product.query.options(joinedload(Product.stock_items)).all()
    return render_template('productos.html', productos=productos, user=current_user)


@app.route('/productos/agregar', methods=['POST'])
@login_required
def productos_agregar():
    nombre = request.form.get('nombre', '')
    precio = float(request.form.get('precio', 0) or 0)
    costo = float(request.form.get('costo', 0) or 0)
    iva = float(request.form.get('iva', 0) or 0)
    cantidad = float(request.form.get('cantidad', 0) or 0)
    imagen = request.files.get('imagen')

    filename = None
    if imagen and allowed_file(imagen.filename):
        filename = secure_filename(imagen.filename)
        imagen.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    # Creamos el producto sin code aún
    nuevo = Product(
        name=nombre,
        price=precio,
        cost=costo,
        tax=iva,
        image_path=filename
    )
    db.session.add(nuevo)
    db.session.flush()  # obtiene nuevo.id

    # Generar code tipo P-00001
    nuevo.code = f"P-{nuevo.id:05d}"

    # Crear stock inicial
    stock = Stock(product_id=nuevo.id, qty=cantidad)
    db.session.add(stock)

    db.session.commit()

    flash(f'Producto agregado correctamente ✅ Código asignado: {nuevo.code}', 'success')
    return redirect(url_for('productos_listar'))


@app.route('/productos/editar/<int:id>', methods=['POST'])
@login_required
def productos_editar(id):
    producto = Product.query.get_or_404(id)
    producto.name = request.form.get('nombre', producto.name)
    producto.price = float(request.form.get('precio', producto.price))
    producto.cost = float(request.form.get('costo', producto.cost))
    producto.tax = float(request.form.get('iva', producto.tax))

    cantidad_raw = request.form.get('cantidad')
    imagen = request.files.get('imagen')

    if imagen and allowed_file(imagen.filename):
        filename = secure_filename(imagen.filename)
        imagen.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        producto.image_path = filename

    stock = Stock.query.filter_by(product_id=id).first()
    if not stock:
        stock = Stock(product_id=id, qty=0)
        db.session.add(stock)

    if cantidad_raw:
        try:
            stock.qty = float(cantidad_raw)
        except ValueError:
            pass

    db.session.commit()
    flash('Producto actualizado correctamente ✏️', 'info')
    return redirect(url_for('productos_listar'))


@app.route('/productos/eliminar/<int:id>')
@login_required
def productos_eliminar(id):
    producto = Product.query.get_or_404(id)

    # Verificar si el producto aparece en alguna factura
    tiene_facturas = InvoiceItem.query.filter_by(product_id=id).first()
    if tiene_facturas:
        flash('❌ No se puede eliminar el producto porque está vinculado a facturas.', 'danger')
        return redirect(url_for('productos_listar'))

    # Eliminar stock asociado
    stock = Stock.query.filter_by(product_id=id).first()
    if stock:
        db.session.delete(stock)

    db.session.delete(producto)
    db.session.commit()

    flash('Producto eliminado correctamente ✅', 'success')
    return redirect(url_for('productos_listar'))


# ====================================================
# 📊 REPORTES (pendiente)
# ====================================================
@app.route('/reportes')
@login_required
def reportes():
    return render_template('reportes.html', user=current_user)


@app.route('/ventas/<int:id>/pdf')
@login_required
def generar_factura_pdf(id):
    """Genera y descarga la factura en formato PDF"""
    factura = (
        Invoice.query
        .options(
            joinedload(Invoice.customer),
            joinedload(Invoice.items).joinedload(InvoiceItem.product)
        )
        .filter_by(id=id)
        .first_or_404()
    )

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        rightMargin=40, leftMargin=40,
        topMargin=60, bottomMargin=40
    )
    elements = []
    styles = getSampleStyleSheet()

    # === Encabezado ===
    titulo = Paragraph(f"<b>Factura N° {factura.code}</b>", styles['Title'])
    empresa = Paragraph("<b>DULCE VIDA - Sistema de Facturación</b>", styles['Heading3'])
    cliente_info = Paragraph(f"""
        <b>Cliente:</b> {factura.customer.name}<br/>
        <b>DUI:</b> {factura.customer.dui or 'N/A'}<br/>
        <b>Correo:</b> {factura.customer.email or 'N/A'}<br/>
        <b>Dirección:</b> {factura.customer.address or 'N/A'}<br/>
        <b>Fecha:</b> {factura.date.strftime('%d/%m/%Y %H:%M') if factura.date else '—'}<br/>
        <b>Vendedor:</b> {factura.user.username if factura.user else '—'}
    """, styles['Normal'])

    elements += [empresa, Spacer(1, 8), titulo, Spacer(1, 12), cliente_info, Spacer(1, 12)]

    # === Tabla de productos ===
    data = [["Producto", "Cantidad", "Precio Unitario ($)", "Subtotal ($)"]]
    for item in factura.items:
        data.append([
            item.product.name,
            f"{item.quantity:.2f}",
            f"{item.price:.2f}",
            f"{item.subtotal:.2f}"
        ])

    # Totales
    data.append(["", "", "Subtotal:", f"{factura.subtotal:.2f}"])
    data.append(["", "", "IVA (13%):", f"{factura.tax_total:.2f}"])
    data.append(["", "", "Total a Pagar:", f"{factura.total:.2f}"])

    table = Table(data, colWidths=[2.5*inch, 1*inch, 1.5*inch, 1.5*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 20))

    # === Firma ===
    elements.append(Spacer(1, 20))
    firma_texto = Paragraph(
        f"<b>Firma:</b> ____________________________<br/>"
        f"<i>{factura.user.username if factura.user else 'Usuario del sistema'}</i>",
        styles['Normal']
    )
    elements.append(firma_texto)

    elements.append(Spacer(1, 30))
    elements.append(Paragraph("Gracias por su compra 💙", styles['Italic']))

    doc.build(elements)

    pdf = buffer.getvalue()
    buffer.close()

    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=Factura_{factura.code}.pdf'

    return response


# ====================================================
# 🚀 MAIN
# ====================================================
if __name__ == '__main__':
    app.run(debug=True)

