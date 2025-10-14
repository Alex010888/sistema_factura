class Config:
    SECRET_KEY = 'clave_secreta_super_segura'
    
    # Configuración de conexión a MySQL
    SQLALCHEMY_DATABASE_URI = 'mysql+mysqlconnector://root:1234@localhost/sistema_facturacion'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
