from sqlmodel import Session, create_engine
from config.settings import app_settings

engine = create_engine(str(app_settings.SQLALCHEMY_DATABASE_URI))


def get_db():
    with Session(engine) as session:
        yield session
