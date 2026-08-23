from database import Base, engine
from consumer import start_consumer


Base.metadata.create_all(
    bind=engine
)


if __name__ == "__main__":

    start_consumer()
