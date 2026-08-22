from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    name: str
    description: str
    price: float = Field(gt=0)
    quantity: int = Field(ge=0)


class ProductUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    price: float | None = Field(default=None, gt=0)
    quantity: int | None = Field(default=None, ge=0)


class ProductResponse(BaseModel):
    id: int
    name: str
    description: str
    price: float
    quantity: int

    class Config:
        from_attributes = True