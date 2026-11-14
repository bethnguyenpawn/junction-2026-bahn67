"""Offline tests for the benchmark harness's practice-slot handling."""

import unittest
from unittest.mock import Mock, patch

import evaluate
from spread.client import SpreadError


class PracticeSlotRetry(unittest.TestCase):
    def test_retries_a_full_practice_pool(self):
        client = Mock()
        world = object()
        client.create.side_effect = [SpreadError(409, "practice pool full"), world]

        with patch.object(evaluate.time, "sleep") as sleep:
            self.assertIs(evaluate.create_practice_world(client, 8, "l8-test-a"), world)

        self.assertEqual(client.create.call_count, 2)
        sleep.assert_called_once_with(evaluate.SLOT_RETRY_SECONDS)

    def test_does_not_retry_other_conflicts(self):
        client = Mock()
        client.create.side_effect = SpreadError(401, "bad key")

        with patch.object(evaluate.time, "sleep") as sleep:
            with self.assertRaises(SpreadError):
                evaluate.create_practice_world(client, 8, "l8-test-a")

        client.create.assert_called_once_with(level=8, seed="l8-test-a")
        sleep.assert_not_called()

    def test_stops_waiting_after_the_slot_timeout(self):
        client = Mock()
        client.create.side_effect = SpreadError(409, "practice pool full")

        with patch.object(evaluate.time, "monotonic", side_effect=(0, evaluate.MAX_SLOT_WAIT_SECONDS)):
            with patch.object(evaluate.time, "sleep") as sleep:
                with self.assertRaisesRegex(TimeoutError, "l8-test-a"):
                    evaluate.create_practice_world(client, 8, "l8-test-a")

        client.create.assert_called_once_with(level=8, seed="l8-test-a")
        sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
