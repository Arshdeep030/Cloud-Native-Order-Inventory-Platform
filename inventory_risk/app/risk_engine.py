import logging
import math
from typing import Optional

import httpx

from inventory_risk.app.config import settings
from inventory_risk.app.schemas import (
    RiskAssessmentRequest,
    RiskAssessmentResult,
    RiskLevel,
)

logger = logging.getLogger("inventory_risk_engine")


class InventoryRiskEngine:
    """
    Evaluates inventory risk position by comparing current physical stock
    against ML multi-day demand forecasts and safety stock constraints.
    """

    def __init__(
        self,
        high_risk_threshold: float = settings.high_risk_coverage_threshold,
        medium_risk_threshold: float = settings.medium_risk_coverage_threshold,
        ml_service_url: str = settings.ml_service_url,
    ):
        self.high_risk_threshold = high_risk_threshold
        self.medium_risk_threshold = medium_risk_threshold
        self.ml_service_url = ml_service_url

    def calculate_risk(
        self,
        product_id: int,
        current_inventory: int,
        forecasted_demand: float,
        forecast_horizon_days: int = 7,
        safety_stock: int = settings.default_safety_stock,
        model_name: str = "demand_forecasting_xgboost",
        model_version: str = "1",
        feature_version: str = "v1",
    ) -> RiskAssessmentResult:
        """
        Pure business rule evaluation for inventory risk classification.
        """
        inv_position = current_inventory - forecasted_demand
        # Safe coverage ratio to avoid divide by zero
        coverage_ratio = current_inventory / max(forecasted_demand, 0.01)

        # Recommended replenishment: target is (forecasted_demand + safety_stock)
        needed = (forecasted_demand + safety_stock) - current_inventory
        reorder_qty = max(0, int(math.ceil(needed)))

        # Risk Classification Logic
        if current_inventory == 0 or coverage_ratio < 0.25:
            risk_level = RiskLevel.CRITICAL
        elif coverage_ratio < self.high_risk_threshold or inv_position < 0:
            risk_level = RiskLevel.HIGH
        elif coverage_ratio < self.medium_risk_threshold or inv_position < safety_stock:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW

        logger.info(
            f"Risk Assessment for Product {product_id}: Inventory={current_inventory}, "
            f"Forecast={forecasted_demand:.1f} ({forecast_horizon_days}d), "
            f"Coverage={coverage_ratio:.2f}, Risk={risk_level.value}, Reorder={reorder_qty}"
        )

        return RiskAssessmentResult(
            product_id=product_id,
            current_inventory=current_inventory,
            forecasted_demand=round(forecasted_demand, 2),
            forecast_horizon_days=forecast_horizon_days,
            inventory_position=round(inv_position, 2),
            coverage_ratio=round(coverage_ratio, 3),
            risk_level=risk_level,
            recommended_reorder_quantity=reorder_qty,
            model_name=model_name,
            model_version=model_version,
            feature_version=feature_version,
        )

    async def assess(self, request: RiskAssessmentRequest) -> RiskAssessmentResult:
        """
        Performs full risk assessment, querying ML inference service if forecast is not provided.
        """
        safety_stock = request.safety_stock if request.safety_stock is not None else settings.default_safety_stock

        if request.forecasted_demand is not None:
            return self.calculate_risk(
                product_id=request.product_id,
                current_inventory=request.current_inventory,
                forecasted_demand=request.forecasted_demand,
                forecast_horizon_days=request.forecast_horizon_days,
                safety_stock=safety_stock,
            )

        # Query ML Inference Service
        model_name = "demand_forecasting_xgboost"
        model_version = "1"
        feature_version = "v1"
        forecast_val = 20.0  # fallback

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    f"{self.ml_service_url}/forecast",
                    json={
                        "product_id": request.product_id,
                        "forecast_horizon": request.forecast_horizon_days,
                        "unit_price": request.unit_price or 49.99,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    forecast_val = float(data.get("total_predicted_demand", 20.0))
                    model_name = data.get("model_name", model_name)
                    model_version = data.get("model_version", model_version)
                    feature_version = data.get("feature_version", feature_version)
                else:
                    logger.warning(
                        f"ML service returned status {resp.status_code}. Using heuristic forecast: {forecast_val}"
                    )
        except Exception as err:
            logger.warning(
                f"Could not reach ML service at {self.ml_service_url} ({err}). Using baseline forecast: {forecast_val}"
            )

        return self.calculate_risk(
            product_id=request.product_id,
            current_inventory=request.current_inventory,
            forecasted_demand=forecast_val,
            forecast_horizon_days=request.forecast_horizon_days,
            safety_stock=safety_stock,
            model_name=model_name,
            model_version=model_version,
            feature_version=feature_version,
        )
