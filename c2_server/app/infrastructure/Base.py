from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Configuración de la base de datos
SQLALCHEMY_DATABASE_URL = "postgresql://c2_user:secret_password@db:5432/c2db"

# Crear base
Base = declarative_base()

# Crear motor de base de datos y sesiones
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

# Inicializar las tablas si no existen
def init_db():
    Base.metadata.create_all(bind=engine)

# Obtener una sesión
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()