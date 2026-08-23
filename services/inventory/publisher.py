import json
import os
import pika


RABBITMQ_HOST = os.getenv(
    "RABBITMQ_HOST",
    "localhost"
)


def publish_inventory_event(
    routing_key: str,
    event: dict
):

    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host=RABBITMQ_HOST
        )
    )

    channel = connection.channel()

    channel.exchange_declare(
        exchange="inventory-events",
        exchange_type="topic",
        durable=True
    )

    channel.basic_publish(
        exchange="inventory-events",
        routing_key=routing_key,
        body=json.dumps(event),
        properties=pika.BasicProperties(
            delivery_mode=2
        )
    )

    connection.close()
