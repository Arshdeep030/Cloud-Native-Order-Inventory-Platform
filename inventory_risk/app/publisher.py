import json
import logging
import uuid
from typing import Optional

try:
    import pika
except ImportError:
    pika = None

from inventory_risk.app.config import settings
from inventory_risk.app.schemas import (
    InventoryRiskEvent,
    RiskAssessmentResult,
    RiskLevel,
)

logger = logging.getLogger("inventory_risk_publisher")


class RabbitMQRiskPublisher:
    """
    Publishes inventory risk detection events to RabbitMQ topic exchange.
    """

    def __init__(
        self,
        rabbitmq_url: str = settings.rabbitmq_url,
        exchange: str = settings.rabbitmq_exchange,
    ):
        self.rabbitmq_url = rabbitmq_url
        self.exchange = exchange

    def publish_risk_event(
        self,
        assessment: RiskAssessmentResult,
        routing_key: str = "inventory.risk.detected",
    ) -> Optional[str]:
        """
        Constructs and publishes an InventoryRiskEvent message.
        Returns the generated event_id.
        """
        event_id = str(uuid.uuid4())
        event = InventoryRiskEvent(
            event_id=event_id,
            event_type="InventoryRiskDetected",
            product_id=assessment.product_id,
            current_inventory=assessment.current_inventory,
            forecasted_demand=assessment.forecasted_demand,
            forecast_horizon_days=assessment.forecast_horizon_days,
            risk_level=assessment.risk_level,
            coverage_ratio=assessment.coverage_ratio,
            recommended_reorder_quantity=assessment.recommended_reorder_quantity,
            model_name=assessment.model_name,
            model_version=assessment.model_version,
            feature_version=assessment.feature_version,
        )

        payload_str = event.model_dump_json()

        # Publish to RabbitMQ
        if pika:
            try:
                params = pika.URLParameters(self.rabbitmq_url)
                params.socket_timeout = 2.0
                connection = pika.BlockingConnection(params)
                channel = connection.channel()

                # Declare topic exchange idempotently
                channel.exchange_declare(
                    exchange=self.exchange,
                    exchange_type="topic",
                    durable=True,
                )

                channel.basic_publish(
                    exchange=self.exchange,
                    routing_key=routing_key,
                    body=payload_str.encode("utf-8"),
                    properties=pika.BasicProperties(
                        content_type="application/json",
                        delivery_mode=2,  # make message persistent
                        correlation_id=event_id,
                        headers={
                            "model_name": assessment.model_name,
                            "model_version": assessment.model_version,
                            "risk_level": assessment.risk_level.value,
                        },
                    ),
                )
                connection.close()
                logger.info(
                    f"✓ Published InventoryRiskEvent ({event_id}) -> Exchange: {self.exchange}, "
                    f"Routing Key: {routing_key} (Risk: {assessment.risk_level.value})"
                )
                return event_id
            except Exception as rmq_err:
                logger.warning(
                    f"RabbitMQ connection unavailable ({rmq_err}). Emitted mock risk event ({event_id}) locally."
                )
                return event_id
        else:
            logger.info(f"Pika not installed. Logged mock risk event ({event_id}).")
            return event_id
