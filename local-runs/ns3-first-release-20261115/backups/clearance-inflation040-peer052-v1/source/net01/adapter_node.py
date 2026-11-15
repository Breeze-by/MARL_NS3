"""Opt-in management of adapter-only SDK diagnostic callbacks; data QoS unchanged."""
from rclpy.node import Node
from rclpy.qos_event import PublisherEventCallbacks, SubscriptionEventCallbacks


class AdapterNode(Node):
    def create_publisher(self, *args, event_callbacks=None, **kwargs):
        if event_callbacks is None:
            event_callbacks = PublisherEventCallbacks(use_default_callbacks=False)
        return super().create_publisher(*args, event_callbacks=event_callbacks, **kwargs)

    def create_subscription(self, *args, event_callbacks=None, **kwargs):
        if event_callbacks is None:
            event_callbacks = SubscriptionEventCallbacks(use_default_callbacks=False)
        return super().create_subscription(*args, event_callbacks=event_callbacks, **kwargs)
