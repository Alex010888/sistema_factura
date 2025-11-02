class Config:
    SECRET_KEY = 'clave_secreta_super_segura'
    
    # Configuración de conexión a MySQL
    SQLALCHEMY_DATABASE_URI = 'mysql+mysqlconnector://root:@localhost/facturacion_electronica'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
