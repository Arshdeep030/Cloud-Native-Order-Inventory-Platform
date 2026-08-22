from fastapi import FastAPI

from app.database import engine, Base
from app.routers import products


Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Cloud Order Platform"
)


app.include_router(products.router)


@app.get("/")
def root():
    return {
        "message": "Cloud Order Platform API"
    }