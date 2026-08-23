import pika


ORDER_EXCHANGE = "order-events"
INVENTORY_EXCHANGE = "inventory-events"
PAYMENT_EXCHANGE = "payment-events"


def setup_order_exchange(channel):

    channel.exchange_declare(
        exchange=ORDER_EXCHANGE,
        exchange_type="topic",
        durable=True
    )


def setup_inventory_exchange(channel):

    channel.exchange_declare(
        exchange=INVENTORY_EXCHANGE,
        exchange_type="topic",
        durable=True
    )


def setup_payment_exchange(channel):

    channel.exchange_declare(
        exchange=PAYMENT_EXCHANGE,
        exchange_type="topic",
        durable=True
    )
