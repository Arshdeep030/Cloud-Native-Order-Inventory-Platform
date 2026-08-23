import pika

from app.config import settings


RABBITMQ_HOST = settings.rabbitmq_host
RABBITMQ_PORT = settings.rabbitmq_port


def get_connection():

    return pika.BlockingConnection(
        pika.ConnectionParameters(
            host=RABBITMQ_HOST,
            port=RABBITMQ_PORT
        )
    )
