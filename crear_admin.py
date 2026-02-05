import os

from app import app, db
from models import User
from werkzeug.security import generate_password_hash

with app.app_context():
    username = (os.getenv('ADMIN_USERNAME', 'admin') or 'admin').strip()
    password = os.getenv('ADMIN_PASSWORD', '12345')

    user = User.query.filter_by(username=username).first()
    if user:
        user.password_hash = generate_password_hash(password)
        user.role = user.role or 'admin'
        db.session.commit()
        print(f"✅ Contraseña de {username} actualizada correctamente.")
    else:
        nuevo = User(
            username=username,
            password_hash=generate_password_hash(password),
            role='admin',
            status=1
        )
        db.session.add(nuevo)
        db.session.commit()
        print(f"✅ Usuario admin creado: {username}")

