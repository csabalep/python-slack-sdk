import logging
import time
import unittest
from threading import Thread

from slack_sdk.socket_mode.request import SocketModeRequest

from slack_sdk.socket_mode.client import BaseSocketModeClient

from slack_sdk import WebClient
from slack_sdk.socket_mode import SocketModeClient
from tests.slack_sdk.socket_mode.mock_socket_mode_server import (
    start_socket_mode_server,
    socket_mode_envelopes,
)
from tests.slack_sdk.socket_mode.mock_web_api_server import (
    setup_mock_web_api_server,
    cleanup_mock_web_api_server,
)


class TestInteractionsBuiltin(unittest.TestCase):
    logger = logging.getLogger(__name__)

    def setUp(self):
        setup_mock_web_api_server(self)
        self.web_client = WebClient(
            token="xoxb-api_test", base_url="http://localhost:8888",
        )

    def tearDown(self):
        cleanup_mock_web_api_server(self)

    def test_interactions(self):
        t = Thread(target=start_socket_mode_server(3011))
        t.daemon = True
        t.start()

        received_messages = []
        received_socket_mode_requests = []

        def message_handler(message):
            self.logger.info(f"Raw Message: {message}")
            received_messages.append(message)

        def socket_mode_request_handler(
            client: BaseSocketModeClient, request: SocketModeRequest
        ):
            self.logger.info(f"Socket Mode Request: {request}")
            received_socket_mode_requests.append(request)

        client = SocketModeClient(
            app_token="xapp-A111-222-xyz",
            web_client=self.web_client,
            on_message_listeners=[message_handler],
            auto_reconnect_enabled=False,
            trace_enabled=True,
        )
        client.socket_mode_request_listeners.append(socket_mode_request_handler)

        try:
            time.sleep(2)  # wait for the server
            client.wss_uri = "ws://0.0.0.0:3011/link"
            client.connect()
            self.assertTrue(client.is_connected())
            time.sleep(2)  # wait for the message receiver

            client.send_message("foo")
            client.send_message("bar")
            client.send_message("baz")
            self.assertTrue(client.is_connected())

            expected = socket_mode_envelopes + ["foo", "bar", "baz"]
            expected.sort()

            count = 0
            while count < 10 and len(received_messages) < len(expected):
                time.sleep(0.2)
                count += 0.2

            received_messages.sort()
            self.assertEqual(received_messages, expected)

            self.assertEqual(
                len(socket_mode_envelopes), len(received_socket_mode_requests)
            )
        finally:
            client.close()
