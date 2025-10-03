"""
RabbitMQ utilities for the Antenna application.

This module provides a simple interface for interacting with RabbitMQ
using the pika library.
"""

import json
import logging
import os
from collections.abc import Callable
from typing import Any

import pika
from django.conf import settings

logger = logging.getLogger(__name__)


class RabbitMQConnection:
    """
    A context manager for RabbitMQ connections.
    """

    def __init__(self, connection_url: str = ""):
        self.connection_url: str
        self.connection_url = connection_url or getattr(settings, "RABBITMQ_URL", "")
        if not self.connection_url:
            # Fallback to Django settings or environment variables
            host = getattr(settings, "RABBITMQ_HOST", os.getenv("RABBITMQ_HOST", "localhost"))
            port = getattr(settings, "RABBITMQ_PORT", int(os.getenv("RABBITMQ_PORT", "5672")))
            user = getattr(settings, "RABBITMQ_DJANGO_USER", os.getenv("RABBITMQ_DJANGO_USER", "guest"))
            password = getattr(settings, "RABBITMQ_DJANGO_PASS", os.getenv("RABBITMQ_DJANGO_PASS", "guest"))
            vhost = getattr(settings, "RABBITMQ_DEFAULT_VHOST", os.getenv("RABBITMQ_DEFAULT_VHOST", "/"))
            self.connection_url = f"amqp://{user}:{password}@{host}:{port}{vhost}"  # noqa: E231

        self.connection = None
        self.channel = None

    def __enter__(self):
        try:
            parameters = pika.URLParameters(self.connection_url)
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            return self.channel
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.connection and not self.connection.is_closed:
            self.connection.close()


class RabbitMQPublisher:
    """
    A simple publisher for RabbitMQ messages.
    """

    def __init__(self, connection_url: str | None = None):
        self.connection_url = connection_url

    def publish_message(
        self,
        queue_name: str,
        message: dict[str, Any],
        exchange: str = "",
        routing_key: str | None = None,
        durable: bool = True,
    ) -> bool:
        """
        Publish a message to a RabbitMQ queue.

        Args:
            queue_name: Name of the queue to publish to
            message: Message data (will be JSON serialized)
            exchange: Exchange name (default: '')
            routing_key: Routing key (default: queue_name)
            durable: Whether the queue should be durable

        Returns:
            bool: True if message was published successfully
        """
        if routing_key is None:
            routing_key = queue_name

        try:
            with RabbitMQConnection(self.connection_url) as channel:
                # Declare the queue
                channel.queue_declare(queue=queue_name, durable=durable)

                # Publish the message
                channel.basic_publish(
                    exchange=exchange,
                    routing_key=routing_key,
                    body=json.dumps(message),
                    properties=pika.BasicProperties(
                        delivery_mode=2 if durable else 1,  # Make message persistent if durable
                        content_type="application/json",
                    ),
                )

                logger.info(f"Published message to queue '{queue_name}': {message}")
                return True

        except Exception as e:
            logger.error(f"Failed to publish message to queue '{queue_name}': {e}")
            return False


class RabbitMQConsumer:
    """
    A simple consumer for RabbitMQ messages.
    """

    def __init__(self, connection_url: str | None = None):
        self.connection_url = connection_url

    def consume_messages(
        self, queue_name: str, callback: Callable[[dict[str, Any]], None], durable: bool = True, auto_ack: bool = False
    ):
        """
        Consume messages from a RabbitMQ queue.

        Args:
            queue_name: Name of the queue to consume from
            callback: Function to call for each message
            durable: Whether the queue should be durable
            auto_ack: Whether to automatically acknowledge messages
        """

        def message_callback(ch, method, properties, body):
            try:
                message = json.loads(body.decode("utf-8"))
                callback(message)

                if not auto_ack:
                    ch.basic_ack(delivery_tag=method.delivery_tag)

            except Exception as e:
                logger.error(f"Error processing message from queue '{queue_name}': {e}")
                if not auto_ack:
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

        try:
            with RabbitMQConnection(self.connection_url) as channel:
                # Declare the queue
                channel.queue_declare(queue=queue_name, durable=durable)

                # Set up the consumer
                channel.basic_consume(queue=queue_name, on_message_callback=message_callback, auto_ack=auto_ack)

                logger.info(f"Starting to consume messages from queue '{queue_name}'")
                channel.start_consuming()

        except KeyboardInterrupt:
            logger.info("Stopping consumer...")
            if "channel" in locals():
                channel.stop_consuming()
        except Exception as e:
            logger.error(f"Error consuming from queue '{queue_name}': {e}")
            raise


# Convenience functions
def publish_to_queue(queue_name: str, message: dict[str, Any], **kwargs) -> bool:
    """
    Convenience function to publish a message to a queue.
    """
    publisher = RabbitMQPublisher()
    return publisher.publish_message(queue_name, message, **kwargs)


def test_connection() -> bool:
    """
    Test the RabbitMQ connection.

    Returns:
        bool: True if connection is successful
    """
    try:
        with RabbitMQConnection() as _:
            logger.info("RabbitMQ connection test successful")
            return True
    except Exception as e:
        logger.error(f"RabbitMQ connection test failed: {e}")
        return False
