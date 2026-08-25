import logging
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, status

from inventory_risk.app.config import settings
from inventory_risk.app.publisher import RabbitMQRiskPublisher
from inventory_risk.app.risk_engine import InventoryRiskEngine
from inventory_risk.app.schemas import (
    EvaluateAndPublishResponse,
    RiskAssessmentRequest,
    RiskAssessmentResult,
    RiskLevel,
)

logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "service": "inventory-risk-service", "logger": "%(name)s", "message": "%(message)s"}',
)
logger = logging.getLogger("inventory_risk_api")

app = FastAPI(
    title="Cloud-Native Inventory Risk Engine",
    description="Operationalizes ML Demand Forecasts into inventory-risk decisions and event-driven stock-out alerts via RabbitMQ.",
    version="1.0.0",
)

risk_engine = InventoryRiskEngine()
publisher = RabbitMQRiskPublisher()


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": "inventory-risk-service",
        "ml_service_url": settings.ml_service_url,
        "exchange": settings.rabbitmq_exchange,
    }


@app.post(
    "/risk/assess",
    response_model=RiskAssessmentResult,
    status_code=status.HTTP_200_OK,
    tags=["Risk Assessment"],
)
async def assess_inventory_risk(request: RiskAssessmentRequest):
    """
    Evaluates inventory risk and calculates coverage ratio, inventory position,
    and recommended reorder quantity based on demand forecast.
    """
    try:
        result = await risk_engine.assess(request)
        return result
    except Exception as err:
        logger.error(f"Error assessing risk for product {request.product_id}: {err}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Risk assessment failure: {str(err)}",
        )


@app.post(
    "/risk/evaluate-and-publish",
    response_model=EvaluateAndPublishResponse,
    status_code=status.HTTP_200_OK,
    tags=["Risk Assessment & Events"],
)
async def evaluate_and_publish_risk(request: RiskAssessmentRequest):
    """
    Evaluates inventory risk and automatically publishes an `inventory.risk_detected`
    event to RabbitMQ when stock-out risk is HIGH or CRITICAL.
    """
    try:
        assessment = await risk_engine.assess(request)
        event_published = False
        event_id = None
        routing_key = "inventory.risk.detected"

        # Trigger event publication on actionable risk levels
        if assessment.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            event_id = publisher.publish_risk_event(assessment, routing_key=routing_key)
            event_published = True
            logger.info(
                f"Actionable risk ({assessment.risk_level.value}) triggered event {event_id} for product {request.product_id}."
            )

        return EvaluateAndPublishResponse(
            assessment=assessment,
            event_published=event_published,
            event_id=event_id,
            routing_key=routing_key if event_published else None,
        )
    except Exception as err:
        logger.error(
            f"Error evaluating and publishing risk for product {request.product_id}: {err}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Evaluation and publish failure: {str(err)}",
        )


@app.get(
    "/risk/products/{product_id}",
    response_model=RiskAssessmentResult,
    tags=["Risk Assessment"],
)
async def get_product_risk_quick(
    product_id: int,
    current_inventory: int = Query(default=20, ge=0, description="Current stock"),
    safety_stock: int = Query(default=15, ge=0, description="Safety stock"),
    days: int = Query(default=7, ge=1, le=30, description="Forecast horizon"),
    forecast: Optional[float] = Query(default=None, ge=0.0, description="Manual forecast override"),
):
    """Convenience GET endpoint for checking inventory risk."""
    req = RiskAssessmentRequest(
        product_id=product_id,
        current_inventory=current_inventory,
        safety_stock=safety_stock,
        forecast_horizon_days=days,
        forecasted_demand=forecast,
    )
    return await assess_inventory_risk(req)
