"""
Script rápido para crear/actualizar credenciales de acceso.

Usuario: alexander
Clave:   12345

Nota: NO usar estas credenciales en producción.
"""

from werkzeug.security import generate_password_hash

from app import app, db
from models import User


USERNAME = "alexander"
PASSWORD = "12345"


with app.app_context():
    user = User.query.filter_by(username=USERNAME).first()
    if user:
        user.password_hash = generate_password_hash(PASSWORD)
        user.status = 1
        if not user.role:
            user.role = "admin"
        db.session.commit()
        print(f"✅ Usuario actualizado: {USERNAME} (status=1)")
    else:
        nuevo = User(
            username=USERNAME,
            password_hash=generate_password_hash(PASSWORD),
            role="admin",
            status=1,
        )
        db.session.add(nuevo)
        db.session.commit()
        print(f"✅ Usuario creado: {USERNAME} (status=1)")

