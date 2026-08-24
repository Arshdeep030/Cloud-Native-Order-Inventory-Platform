from contextlib import asynccontextmanager
import logging
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, status

from ml_service.app.model_loader import ModelLoader
from ml_service.app.predictor import RecursiveDemandPredictor
from ml_service.app.schemas import (
    ForecastRequest,
    ForecastResponse,
    HealthResponse,
    ModelInfoResponse,
)

logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "service": "ml-service", "logger": "%(name)s", "message": "%(message)s"}',
)
logger = logging.getLogger("ml_api")

# Global state instances
model_loader = ModelLoader()
predictor: Optional[RecursiveDemandPredictor] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global predictor
    logger.info("Initializing ML Demand Inference Service...")
    model = model_loader.load()
    predictor = RecursiveDemandPredictor(
        model=model,
        model_name=model_loader.model_name,
        model_version=model_loader.model_version,
        feature_version=model_loader.feature_version,
    )
    logger.info(
        f"✓ ML Inference Service ready. Serving model '{model_loader.model_name}' (Version: {model_loader.model_version})."
    )
    yield
    logger.info("Shutting down ML Demand Inference Service.")


app = FastAPI(
    title="Cloud-Native ML Demand Forecasting Service",
    description="Production-grade ML Demand Forecasting Service with time-series feature engineering and recursive multi-step forecasting.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Liveness and readiness health probe."""
    is_loaded = predictor is not None and predictor.model.is_fitted
    return HealthResponse(
        status="healthy" if is_loaded else "degraded",
        model_loaded=is_loaded,
        service="ml-inference-service",
    )


@app.get("/model/info", response_model=ModelInfoResponse, tags=["Model Info"])
async def get_model_info():
    """Returns active model metadata, feature contract, and version lineage."""
    info = model_loader.get_info()
    return ModelInfoResponse(**info)


@app.post(
    "/forecast",
    response_model=ForecastResponse,
    status_code=status.HTTP_200_OK,
    tags=["Forecasting"],
)
async def generate_forecast(request: ForecastRequest):
    """
    Generates multi-step recursive demand forecasts for a given product
    across the specified horizon (1 to 30 days).
    """
    if predictor is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ML forecasting model is not initialized.",
        )

    try:
        response = predictor.forecast(request)
        return response
    except Exception as exc:
        logger.error(f"Forecasting error for product {request.product_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Forecasting error: {str(exc)}",
        )


@app.get(
    "/forecast/{product_id}",
    response_model=ForecastResponse,
    tags=["Forecasting"],
)
async def get_product_forecast(
    product_id: int,
    days: int = Query(default=7, ge=1, le=30, description="Forecast horizon in days"),
    unit_price: float = Query(default=49.99, ge=0.0, description="Product price"),
):
    """Convenience GET endpoint for quick product demand forecasting."""
    req = ForecastRequest(
        product_id=product_id,
        forecast_horizon=days,
        unit_price=unit_price,
    )
    return await generate_forecast(req)
