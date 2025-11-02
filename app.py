# ====================================================
# 🧾 SISTEMA DE FACTURACIÓN ELECTRÓNICA – Flask + SQLAlchemy
# ====================================================
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename
from config import Config
from models import db, User, Customer, Product, Stock
from sqlalchemy.orm import joinedload
import os

# ====================================================
# ⚙️ CONFIGURACIÓN PRINCIPAL
# ====================================================
app = Flask(__name__)
app.config.from_object(Config)

# Carpeta donde se guardarán las imágenes de los productos
UPLOAD_FOLDER = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Crear carpeta si no existe
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Función para validar extensiones de archivo
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ====================================================
# 🔐 INICIALIZACIÓN DE BASE DE DATOS Y LOGIN
# ====================================================
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    """Carga el usuario actual desde la base de datos"""
    return User.query.get(int(user_id))


# ====================================================
# 🧩 RUTAS PRINCIPALES
# ====================================================
@app.route('/')
def index():
    """Redirige automáticamente al login"""
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Pantalla de inicio de sesión"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
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
    """Panel principal"""
    return render_template('dashboard.html', user=current_user)


@app.route('/ventas')
@login_required
def ventas():
    """Vista del módulo de ventas"""
    return render_template('ventas.html', user=current_user)


@app.route('/reportes')
@login_required
def reportes():
    """Vista de reportes (pendiente)"""
    return render_template('reportes.html', user=current_user)


@app.route('/logout')
@login_required
def logout():
    """Cierra la sesión actual"""
    logout_user()
    flash('Has cerrado sesión correctamente 👋', 'info')
    return redirect(url_for('login'))


# ====================================================
# 👥 MÓDULO DE CLIENTES (CRUD)
# ====================================================

@app.route('/clientes')
@login_required
def clientes_listar():
    """Lista todos los clientes registrados"""
    clientes = Customer.query.all()
    return render_template('clientes.html', clientes=clientes, user=current_user)


@app.route('/clientes/agregar', methods=['POST'])
@login_required
def clientes_agregar():
    """Agrega un nuevo cliente"""
    nuevo = Customer(
        name=request.form['nombre'],
        dui=request.form['dui'],
        nit=request.form['nit'],
        email=request.form['email'],
        phone=request.form['telefono'],
        address=request.form['direccion']
    )
    db.session.add(nuevo)
    db.session.commit()
    flash('Cliente agregado correctamente ✅', 'success')
    return redirect(url_for('clientes_listar'))


@app.route('/clientes/editar/<int:id>', methods=['POST'])
@login_required
def clientes_editar(id):
    """Edita la información de un cliente"""
    cliente = Customer.query.get_or_404(id)
    cliente.name = request.form['nombre']
    cliente.dui = request.form['dui']
    cliente.nit = request.form['nit']
    cliente.email = request.form['email']
    cliente.phone = request.form['telefono']
    cliente.address = request.form['direccion']
    db.session.commit()
    flash('Cliente actualizado correctamente ✏️', 'info')
    return redirect(url_for('clientes_listar'))


@app.route('/clientes/eliminar/<int:id>')
@login_required
def clientes_eliminar(id):
    """Elimina un cliente existente"""
    cliente = Customer.query.get_or_404(id)
    db.session.delete(cliente)
    db.session.commit()
    flash('Cliente eliminado correctamente ❌', 'danger')
    return redirect(url_for('clientes_listar'))


# ====================================================
# 📦 MÓDULO DE PRODUCTOS (CRUD + IMAGEN + STOCK)
# ====================================================
@app.route('/productos')
@login_required
def productos_listar():
    """Lista todos los productos junto con su stock actual"""
    productos = db.session.query(Product).options(joinedload(Product.stock_items)).all()
    return render_template('productos.html', productos=productos, user=current_user)


@app.route('/productos/agregar', methods=['POST'])
@login_required
def productos_agregar():
    """Agrega un nuevo producto con imagen y stock"""
    codigo = request.form['codigo']
    nombre = request.form['nombre']
    precio = request.form['precio']
    costo = request.form['costo']
    iva = request.form['iva']
    cantidad = request.form['cantidad']
    imagen = request.files.get('imagen')

    # Evitar códigos duplicados
    if Product.query.filter_by(code=codigo).first():
        flash(f'⚠️ El código "{codigo}" ya está registrado.', 'warning')
        return redirect(url_for('productos_listar'))

    # Guardar imagen si existe
    filename = None
    if imagen and allowed_file(imagen.filename):
        filename = secure_filename(imagen.filename)
        imagen.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    # Crear producto
    nuevo = Product(code=codigo, name=nombre, price=precio, cost=costo, tax=iva, image_path=filename)
    db.session.add(nuevo)
    db.session.flush()  # para obtener el ID

    # Stock inicial
    stock = Stock(product_id=nuevo.id, qty=cantidad)
    db.session.add(stock)
    db.session.commit()

    flash('Producto agregado correctamente ✅', 'success')
    return redirect(url_for('productos_listar'))


@app.route('/productos/editar/<int:id>', methods=['POST'])
@login_required
def productos_editar(id):
    """Edita un producto y su stock actual"""
    producto = Product.query.get_or_404(id)
    producto.code = request.form['codigo']
    producto.name = request.form['nombre']
    producto.price = request.form['precio']
    producto.cost = request.form['costo']
    producto.tax = request.form['iva']

    imagen = request.files.get('imagen')
    if imagen and allowed_file(imagen.filename):
        filename = secure_filename(imagen.filename)
        imagen.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        producto.image_path = filename

    stock = Stock.query.filter_by(product_id=id).first()
    if stock:
        stock.qty = request.form['cantidad']

    db.session.commit()
    flash('Producto actualizado correctamente ✏️', 'info')
    return redirect(url_for('productos_listar'))


@app.route('/productos/eliminar/<int:id>')
@login_required
def productos_eliminar(id):
    """Elimina el producto y su stock asociado"""
    producto = Product.query.get_or_404(id)
    stock = Stock.query.filter_by(product_id=id).first()
    if stock:
        db.session.delete(stock)
    db.session.delete(producto)
    db.session.commit()
    flash('Producto eliminado correctamente ❌', 'danger')
    return redirect(url_for('productos_listar'))


# ====================================================
# 🚀 EJECUCIÓN PRINCIPAL
# ====================================================
if __name__ == '__main__':
    app.run(debug=True)
