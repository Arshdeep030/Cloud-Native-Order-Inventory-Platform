import json
import pika

from app.messaging.rabbitmq import get_connection
from app.messaging.topology import ORDER_EXCHANGE, setup_order_exchange


def publish_order_created(event: dict):

    connection = get_connection()

    channel = connection.channel()

    setup_order_exchange(channel)

    channel.basic_publish(
        exchange=ORDER_EXCHANGE,
        routing_key="order.created",
        body=json.dumps(event),
        properties=pika.BasicProperties(
            delivery_mode=2
        )
    )

    connection.close()


def publish_event(exchange: str, routing_key: str, event: dict):

    connection = get_connection()

    channel = connection.channel()

    channel.exchange_declare(
        exchange=exchange,
        exchange_type="topic",
        durable=True
    )

    channel.basic_publish(
        exchange=exchange,
        routing_key=routing_key,
        body=json.dumps(event),
        properties=pika.BasicProperties(
            delivery_mode=2
        )
    )

    connection.close()
