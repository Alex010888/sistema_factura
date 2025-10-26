from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from config import Config
from models import db, User

app = Flask(__name__)
app.config.from_object(Config)

# Inicializar la base de datos
db.init_app(app)

# ✅ Inicializar login manager
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# -------------------------------
# RUTAS
# -------------------------------
@app.route('/')
def inicio():
    return "Sistema de Facturación Híbrido - Flask conectado a MySQL correctamente"

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash('Inicio de sesión exitoso', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Credenciales incorrectas', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Sesión cerrada correctamente', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    return f"Bienvenido {current_user.username}, tu rol es: {current_user.role}"

# -------------------------------
# EJECUCIÓN DEL SERVIDOR
# -------------------------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Crea las tablas si no existen
    app.run(debug=True)
