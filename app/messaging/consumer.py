import json

from app.messaging.rabbitmq import get_connection


def callback(
    channel,
    method,
    properties,
    body
):

    event = json.loads(body)

    print(
        f"Received event: {event}"
    )

    channel.basic_ack(
        delivery_tag=method.delivery_tag
    )


def start_consumer():

    connection = get_connection()

    channel = connection.channel()

    channel.queue_declare(
        queue="order-created",
        durable=True
    )

    channel.basic_consume(
        queue="order-created",
        on_message_callback=callback
    )

    print(
        "Waiting for OrderCreated events..."
    )

    channel.start_consuming()
