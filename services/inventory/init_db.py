from database import Base, engine
from models import Inventory


Base.metadata.create_all(
    bind=engine
)
