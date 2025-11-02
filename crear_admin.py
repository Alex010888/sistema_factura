from app import app, db
from models import User
from werkzeug.security import generate_password_hash

with app.app_context():
    user = User.query.filter_by(username='admin').first()
    if user:
        user.password_hash = generate_password_hash('12345')
        db.session.commit()
        print("✅ Contraseña de admin actualizada correctamente (clave: 12345)")
    else:
        print("⚠️ No existe usuario admin.")

