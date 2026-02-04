# ====================================================
# 🧾 SISTEMA DE FACTURACIÓN ELECTRÓNICA – Flask + SQLAlchemy
# ====================================================
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename
from config import Config
from models import (
    db,
    User,
    Customer,
    Product,
    Stock,
    Invoice,
    InvoiceItem,
    Category,
    Sale,
    SaleItem
)
from sqlalchemy.orm import joinedload
from sqlalchemy import func
from datetime import date, datetime, timedelta  # para fecha en ventas_nueva
from decimal import Decimal  # para manejar cantidades en inventario
import os

# ====================================================
# 🧾 GENERAR PDF DE FACTURA
# ====================================================
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
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
# 💨 VENTA RÁPIDA (consumidor final)
# ====================================================
@app.route('/venta_final', methods=['GET', 'POST'])
@login_required
def ventas_listar():
    productos = Product.query.options(joinedload(Product.stock_items)).all()

    venta_creada = None
    venta_id = request.args.get('venta_id', '').strip()
    if venta_id:
        try:
            venta_creada = (
                Sale.query
                .options(joinedload(Sale.items).joinedload(SaleItem.product))
                .filter_by(id=int(venta_id))
                .first()
            )
        except ValueError:
            venta_creada = None

    if request.method == 'POST':
        items = []
        subtotal = Decimal('0.00')
        # Nota: en venta rápida el precio YA incluye IVA (no se suma aparte)
        iva_total = Decimal('0.00')

        for key in request.form:
            if not key.startswith('cantidad_'):
                continue

            try:
                product_id = int(key.split('_')[1])
            except Exception:
                continue

            try:
                cantidad = Decimal(str(request.form.get(key, 0)))
            except Exception:
                cantidad = Decimal('0')

            if cantidad <= 0:
                continue

            producto = Product.query.get(product_id)
            if not producto:
                continue

            precio_unitario = Decimal(str(producto.price))
            subtotal_item = precio_unitario * cantidad
            iva_item = Decimal('0.00')

            subtotal += subtotal_item
            iva_total += iva_item

            items.append({
                'product': producto,
                'quantity': cantidad,
                'price': precio_unitario,
                'subtotal': subtotal_item,
                'tax_total': iva_item
            })

        if not items:
            flash('Debes ingresar al menos una cantidad mayor a 0 📦', 'warning')
            return redirect(url_for('ventas_listar'))

        total = subtotal
        metodo_pago = request.form.get('paid_with', 'EFECTIVO').strip() or 'EFECTIVO'

        try:
            nueva_venta = Sale(
                user_id=current_user.id,
                customer_id=None,
                total=float(total),
                paid_with=metodo_pago
            )
            db.session.add(nueva_venta)
            db.session.flush()
            nueva_venta.sale_number = f"V-{nueva_venta.id:05d}"

            for item in items:
                # Bloqueo de stock para evitar condiciones de carrera
                stock = (
                    Stock.query
                    .filter_by(product_id=item['product'].id)
                    .with_for_update()
                    .first()
                )
                if not stock:
                    db.session.rollback()
                    flash(f'No hay inventario para {item["product"].name} ❌', 'danger')
                    return redirect(url_for('ventas_listar'))

                stock_actual = Decimal(str(stock.qty))
                if stock_actual < item['quantity']:
                    db.session.rollback()
                    flash(f'Stock insuficiente para {item["product"].name} ❌', 'danger')
                    return redirect(url_for('ventas_listar'))

                detalle = SaleItem(
                    sale_id=nueva_venta.id,
                    product_id=item['product'].id,
                    qty=float(item['quantity']),
                    price=float(item['price']),
                    tax=float(item['tax_total']),
                    subtotal=float(item['subtotal'])
                )
                db.session.add(detalle)

                stock.qty = float(stock_actual - item['quantity'])

            db.session.commit()
            flash(f'Venta rápida registrada ✅ Número: {nueva_venta.sale_number}', 'success')
            return redirect(url_for('ventas_listar', venta_id=nueva_venta.id))
        except Exception as e:
            db.session.rollback()
            flash('⚠️ No se pudo registrar la venta rápida.', 'danger')
            print(e)
            return redirect(url_for('ventas_listar'))

    return render_template(
        'venta_final.html',
        productos=productos,
        user=current_user,
        venta_creada=venta_creada
    )


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
                stock_actual = Decimal(str(stock.qty))
                nuevo_stock = stock_actual - item['quantity']
                if nuevo_stock < 0:
                    nuevo_stock = Decimal('0.00')
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

    try:
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
# 📦 MÓDULO DE PRODUCTOS (con categorías)
# ====================================================
@app.route('/productos')
@login_required
def productos_listar():
    productos = Product.query.options(
        joinedload(Product.stock_items),
        joinedload(Product.category)
    ).all()
    categorias = Category.query.order_by(Category.name).all()
    return render_template(
        'productos.html',
        productos=productos,
        categorias=categorias,
        user=current_user
    )


@app.route('/productos/agregar', methods=['POST'])
@login_required
def productos_agregar():
    nombre = request.form.get('nombre', '')
    precio = float(request.form.get('precio', 0) or 0)
    costo = float(request.form.get('costo', 0) or 0)
    iva = float(request.form.get('iva', 0) or 0)
    cantidad = float(request.form.get('cantidad', 0) or 0)
    categoria_id = request.form.get('category_id')  # select de categorías
    imagen = request.files.get('imagen')

    filename = None
    if imagen and allowed_file(imagen.filename):
        filename = secure_filename(imagen.filename)
        imagen.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    nuevo = Product(
        name=nombre,
        price=precio,
        cost=costo,
        tax=iva,
        image_path=filename,
        category_id=int(categoria_id) if categoria_id else None
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
    categoria_id = request.form.get('category_id')
    producto.category_id = int(categoria_id) if categoria_id else None

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
    start_str = request.args.get('start_date', '').strip()
    end_str = request.args.get('end_date', '').strip()

    start_date = None
    end_date = None
    end_date_plus = None

    if start_str:
        try:
            start_date = datetime.strptime(start_str, '%Y-%m-%d')
        except ValueError:
            start_date = None

    if end_str:
        try:
            end_date = datetime.strptime(end_str, '%Y-%m-%d')
            end_date_plus = end_date + timedelta(days=1)
        except ValueError:
            end_date = None
            end_date_plus = None

    def apply_date_filters(query, date_field):
        if start_date:
            query = query.filter(date_field >= start_date)
        if end_date_plus:
            query = query.filter(date_field < end_date_plus)
        return query

    invoices_q = apply_date_filters(Invoice.query, Invoice.date)
    sales_q = apply_date_filters(Sale.query, Sale.created_at)

    invoice_total = invoices_q.with_entities(func.coalesce(func.sum(Invoice.total), 0)).scalar() or 0
    invoice_count = invoices_q.count()
    invoice_avg = (float(invoice_total) / invoice_count) if invoice_count else 0

    sale_total = sales_q.with_entities(func.coalesce(func.sum(Sale.total), 0)).scalar() or 0
    sale_count = sales_q.count()
    sale_avg = (float(sale_total) / sale_count) if sale_count else 0

    # Costo estimado (COGS) usando cost del producto * qty vendida
    invoice_cogs = (
        apply_date_filters(
            db.session.query(func.coalesce(func.sum(InvoiceItem.quantity * Product.cost), 0))
            .select_from(InvoiceItem)
            .join(Product, Product.id == InvoiceItem.product_id)
            .join(Invoice, Invoice.id == InvoiceItem.invoice_id),
            Invoice.date
        )
        .scalar() or 0
    )

    sale_cogs = (
        apply_date_filters(
            db.session.query(func.coalesce(func.sum(SaleItem.qty * Product.cost), 0))
            .select_from(SaleItem)
            .join(Product, Product.id == SaleItem.product_id)
            .join(Sale, Sale.id == SaleItem.sale_id),
            Sale.created_at
        )
        .scalar() or 0
    )

    gross_sales = float(invoice_total) + float(sale_total)
    cogs_total = float(invoice_cogs) + float(sale_cogs)
    gross_profit = gross_sales - cogs_total

    # Inventario (stock actual)
    inventory_qty = (
        db.session.query(func.coalesce(func.sum(Stock.qty), 0))
        .scalar() or 0
    )
    inventory_value_cost = (
        db.session.query(func.coalesce(func.sum(Stock.qty * Product.cost), 0))
        .select_from(Stock)
        .join(Product, Product.id == Stock.product_id)
        .scalar() or 0
    )

    low_stock_threshold = request.args.get('low_stock', '').strip()
    try:
        low_stock_threshold_val = Decimal(low_stock_threshold) if low_stock_threshold else Decimal('5')
    except Exception:
        low_stock_threshold_val = Decimal('5')

    low_stock = (
        Product.query
        .options(joinedload(Product.stock_items))
        .join(Stock, Stock.product_id == Product.id)
        .filter(Stock.qty <= low_stock_threshold_val)
        .order_by(Stock.qty.asc())
        .limit(10)
        .all()
    )

    top_invoice_products = (
        apply_date_filters(
            InvoiceItem.query.join(Product).join(Invoice),
            Invoice.date
        )
        .with_entities(
            Product.name.label('name'),
            func.sum(InvoiceItem.quantity).label('qty'),
            func.sum(InvoiceItem.subtotal).label('subtotal')
        )
        .group_by(Product.id)
        .order_by(func.sum(InvoiceItem.quantity).desc())
        .limit(5)
        .all()
    )

    top_sale_products = (
        apply_date_filters(
            SaleItem.query.join(Product).join(Sale),
            Sale.created_at
        )
        .with_entities(
            Product.name.label('name'),
            func.sum(SaleItem.qty).label('qty'),
            func.sum(SaleItem.subtotal).label('subtotal')
        )
        .group_by(Product.id)
        .order_by(func.sum(SaleItem.qty).desc())
        .limit(5)
        .all()
    )

    invoice_daily = (
        invoices_q
        .with_entities(
            func.date(Invoice.date).label('day'),
            func.sum(Invoice.total).label('total')
        )
        .group_by('day')
        .order_by('day')
        .all()
    )

    sale_daily = (
        sales_q
        .with_entities(
            func.date(Sale.created_at).label('day'),
            func.sum(Sale.total).label('total')
        )
        .group_by('day')
        .order_by('day')
        .all()
    )

    invoice_chart_labels = [d.day.strftime('%Y-%m-%d') for d in invoice_daily]
    invoice_chart_data = [float(d.total or 0) for d in invoice_daily]
    sale_chart_labels = [d.day.strftime('%Y-%m-%d') for d in sale_daily]
    sale_chart_data = [float(d.total or 0) for d in sale_daily]

    return render_template(
        'reportes.html',
        user=current_user,
        start_date=start_str,
        end_date=end_str,
        low_stock_threshold=str(low_stock_threshold_val),
        invoice_total=float(invoice_total),
        invoice_count=invoice_count,
        invoice_avg=float(invoice_avg),
        sale_total=float(sale_total),
        sale_count=sale_count,
        sale_avg=float(sale_avg),
        invoice_cogs=float(invoice_cogs),
        sale_cogs=float(sale_cogs),
        gross_sales=float(gross_sales),
        cogs_total=float(cogs_total),
        gross_profit=float(gross_profit),
        inventory_qty=float(inventory_qty),
        inventory_value_cost=float(inventory_value_cost),
        low_stock=low_stock,
        top_invoice_products=top_invoice_products,
        top_sale_products=top_sale_products,
        invoice_chart_labels=invoice_chart_labels,
        invoice_chart_data=invoice_chart_data,
        sale_chart_labels=sale_chart_labels,
        sale_chart_data=sale_chart_data
    )


# ====================================================
# 📄 GENERAR PDF DE VENTA RÁPIDA
# ====================================================
@app.route('/venta_final/<int:id>/pdf')
@login_required
def venta_rapida_pdf(id):
    venta = (
        Sale.query
        .options(
            joinedload(Sale.items).joinedload(SaleItem.product),
            joinedload(Sale.user)
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

    titulo = Paragraph(f"<b>Venta Rápida N° {venta.sale_number}</b>", styles['Title'])
    empresa = Paragraph("<b>DULCE VIDA - Panadería</b>", styles['Heading3'])
    venta_info = Paragraph(f"""
        <b>Cliente:</b> Consumidor final<br/>
        <b>Fecha:</b> {venta.created_at.strftime('%d/%m/%Y %H:%M') if venta.created_at else '—'}<br/>
        <b>Vendedor:</b> {venta.user.username if venta.user else '—'}<br/>
        <b>Método de pago:</b> {venta.paid_with}
    """, styles['Normal'])

    elements += [empresa, Spacer(1, 8), titulo, Spacer(1, 12), venta_info, Spacer(1, 12)]

    data = [["Producto", "Cantidad", "Precio Unitario ($)", "Subtotal ($)"]]
    subtotal = Decimal('0.00')
    iva_total = Decimal('0.00')

    for item in venta.items:
        subtotal += Decimal(str(item.subtotal or 0))
        iva_total += Decimal(str(item.tax or 0))
        data.append([
            item.product.name if item.product else 'Producto',
            f"{float(item.qty):.3f}",
            f"{float(item.price):.2f}",
            f"{float(item.subtotal):.2f}"
        ])

    total = subtotal + iva_total

    data.append(["", "", "Subtotal:", f"{subtotal:.2f}"])
    data.append(["", "", "IVA:", f"{iva_total:.2f}"])
    data.append(["", "", "Total a Pagar:", f"{total:.2f}"])

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
    elements.append(Paragraph("Gracias por su compra 💙", styles['Italic']))

    doc.build(elements)

    pdf = buffer.getvalue()
    buffer.close()

    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=Venta_{venta.sale_number}.pdf'
    return response


# ====================================================
# 📄 GENERAR PDF DE FACTURA
# ====================================================
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
