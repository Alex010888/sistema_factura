import os


class Config:
    """
    Configuración base.

    En Render (y en general en producción) se deben usar variables de entorno:
    - SECRET_KEY
    - DATABASE_URL (Render la inyecta si usas Postgres administrado)
    """

    # Seguridad
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-me')

    # Desactivar login temporalmente (Flask-Login lo soporta).
    # Por defecto queda DESACTIVADO; para reactivarlo usa:
    #   LOGIN_DISABLED=0
    LOGIN_DISABLED = (os.getenv('LOGIN_DISABLED', '1') or '1').strip().lower() in (
        '1', 'true', 'yes', 'y', 'on'
    )

    # Base de datos (preferencia: DATABASE_URL)
    _db_url = os.getenv('DATABASE_URL', '').strip()
    if _db_url.startswith('postgres://'):
        # SQLAlchemy requiere postgresql://
        _db_url = _db_url.replace('postgres://', 'postgresql://', 1)

    # Fallback para desarrollo local si no hay DATABASE_URL
    SQLALCHEMY_DATABASE_URI = _db_url or os.getenv(
        'SQLALCHEMY_DATABASE_URI',
        'sqlite:///facturacion.db'
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Recomendado en hosting (evita conexiones muertas en DB)
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': int(os.getenv('DB_POOL_RECYCLE', '280')),
    }
