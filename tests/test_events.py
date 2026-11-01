"""
Tests for Guardian Shield EventBus.
"""

import unittest
from core.events import (
    BaseEvent,
    EventBus,
    NotificationDismissedEvent,
    ShieldActivatedEvent,
    ShieldRequestedEvent,
    ThreatDetectedEvent,
    ThreatLevel,
    ToastAlertTriggeredEvent,
)


class TestEventBus(unittest.TestCase):

    def setUp(self):
        self.bus = EventBus()
        self.bus.clear()

    def test_publish_and_subscribe(self):
        received = []

        def handler(evt: ToastAlertTriggeredEvent):
            received.append(evt)

        self.bus.subscribe(ToastAlertTriggeredEvent, handler)

        event = ToastAlertTriggeredEvent(threat_score=0.75, peeper_count=1)
        self.bus.publish(event)

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].threat_score, 0.75)
        self.assertEqual(received[0].peeper_count, 1)

    def test_unsubscribe(self):
        received = []

        def handler(evt: ShieldRequestedEvent):
            received.append(evt)

        self.bus.subscribe(ShieldRequestedEvent, handler)
        self.bus.unsubscribe(ShieldRequestedEvent, handler)

        self.bus.publish(ShieldRequestedEvent(source="test"))
        self.assertEqual(len(received), 0)

    def test_polymorphic_base_subscription(self):
        received = []

        def base_handler(evt: BaseEvent):
            received.append(evt)

        self.bus.subscribe(BaseEvent, base_handler)

        self.bus.publish(ShieldActivatedEvent(style="blur"))
        self.bus.publish(NotificationDismissedEvent(reason="timeout"))

        self.assertEqual(len(received), 2)


if __name__ == "__main__":
    unittest.main()
