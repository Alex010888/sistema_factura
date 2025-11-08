from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# ======================================================
# 🧍 Modelo de Usuarios
# ======================================================
class User(db.Model, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='empleado')
    status = db.Column(db.SmallInteger, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    sales = db.relationship('Sale', backref='user', lazy=True)
    invoices = db.relationship('Invoice', backref='user', lazy=True)

    # Métodos de seguridad
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


# ======================================================
# 👥 Modelo de Clientes
# ======================================================
class Customer(db.Model):
    __tablename__ = 'customers'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    dui = db.Column(db.String(15))
    nit = db.Column(db.String(20))
    email = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    address = db.Column(db.String(255))
    status = db.Column(db.SmallInteger, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    sales = db.relationship('Sale', backref='customer', lazy=True)
    invoices = db.relationship('Invoice', backref='customer', lazy=True)


# ======================================================
# 📦 Modelo de Productos
# ======================================================
class Product(db.Model):
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=True)
    name = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Float, nullable=False, default=0.0)
    cost = db.Column(db.Float, nullable=False, default=0.0)
    tax = db.Column(db.Float, nullable=False, default=13.0)
    image_path = db.Column(db.String(255))

    # Relaciones
    stock_items = db.relationship('Stock', backref='product', cascade="all, delete-orphan", lazy=True)
    invoice_items = db.relationship('InvoiceItem', backref='product', cascade="all, delete-orphan", lazy=True)
    sale_items = db.relationship('SaleItem', backref='product', cascade="all, delete-orphan", lazy=True)


# ======================================================
# 🏬 Modelo de Inventario (Stock)
# ======================================================
class Stock(db.Model):
    __tablename__ = 'stock'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    qty = db.Column(db.Numeric(12, 3), default=0)
    location_id = db.Column(db.Integer, default=1)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ======================================================
# 🧾 Modelo de Ventas (Factura POS)
# ======================================================
class Sale(db.Model):
    __tablename__ = 'sales'

    id = db.Column(db.Integer, primary_key=True)
    sale_number = db.Column(db.String(50), unique=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))

    # 💰 Totales y método de pago
    subtotal = db.Column(db.Numeric(12, 2), default=0)
    tax = db.Column(db.Numeric(12, 2), default=0)
    total = db.Column(db.Numeric(12, 2), default=0)
    paid_with = db.Column(db.String(50), default='EFECTIVO')
    cash_received = db.Column(db.Numeric(12, 2), default=0)
    change_amount = db.Column(db.Numeric(12, 2), default=0)

    # 💨 Bandera para identificar venta rápida
    is_fast_sale = db.Column(db.Boolean, default=False)

    # 🕒 Tiempos
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    items = db.relationship('SaleItem', backref='sale', cascade="all, delete-orphan", lazy=True)



# ======================================================
# 🧮 Modelo de Detalle de Ventas
# ======================================================
class SaleItem(db.Model):
    __tablename__ = 'sale_items'

    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    qty = db.Column(db.Numeric(12, 3), default=1)
    price = db.Column(db.Numeric(10, 2), default=0)
    tax = db.Column(db.Numeric(5, 2), default=0)
    subtotal = db.Column(db.Numeric(12, 2), default=0)


# ======================================================
# 🧾 Modelo de Factura Electrónica
# ======================================================
class Invoice(db.Model):
    __tablename__ = 'invoices'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    subtotal = db.Column(db.Float, nullable=False, default=0.0)
    tax_total = db.Column(db.Float, nullable=False, default=0.0)
    total = db.Column(db.Float, nullable=False, default=0.0)

    # ✅ Relación con los items (detalle)
    items = db.relationship('InvoiceItem', backref='invoice', cascade="all, delete-orphan", lazy=True)

    def __repr__(self):
        return f"<Factura {self.code} - Cliente {self.customer.name if self.customer else 'Sin cliente'}>"


# ======================================================
# 🧾 Detalle de Factura Electrónica
# ======================================================
class InvoiceItem(db.Model):
    __tablename__ = 'invoice_items'

    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    price = db.Column(db.Float, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)

    def __repr__(self):
        return f"<Item {self.product.name if self.product else 'Producto'} x {self.quantity}>"

        return f"<Item {self.product.name} x {self.quantity}>"
