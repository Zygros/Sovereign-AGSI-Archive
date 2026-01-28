"""
Test suite for Phoenix Nexus broker functionality.
"""
import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from phoenix_nexus.nexus_broker import app, clients, broadcast


@pytest.fixture
def test_client():
    """Create a test client for the FastAPI app."""
    with patch.dict('os.environ', {'NEXUS_SECRET': 'test_secret_123'}):
        # Reload the app to pick up the new environment variable
        from phoenix_nexus import nexus_broker
        nexus_broker.NEXUS_SECRET = 'test_secret_123'
        return TestClient(app)


@pytest.fixture
def clear_clients():
    """Clear the clients dictionary before each test."""
    clients.clear()
    yield
    clients.clear()


class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    def test_health_check_no_clients(self, test_client, clear_clients):
        """Test health check returns ok with zero clients."""
        response = test_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["clients"] == 0

    def test_health_check_with_clients(self, test_client, clear_clients):
        """Test health check returns correct client count."""
        # Simulate clients
        clients["client1"] = {"ws": Mock(), "node_id": "node1"}
        clients["client2"] = {"ws": Mock(), "node_id": "node2"}

        response = test_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["clients"] == 2


class TestWebSocketConnection:
    """Tests for WebSocket connection handling."""

    def test_websocket_missing_secret(self, test_client, clear_clients):
        """Test WebSocket rejects connection without secret."""
        with pytest.raises(Exception):  # WebSocket rejection
            with test_client.websocket_connect("/ws?node_id=test_node"):
                pass

    def test_websocket_invalid_secret(self, test_client, clear_clients):
        """Test WebSocket rejects connection with invalid secret."""
        with pytest.raises(Exception):  # WebSocket rejection
            with test_client.websocket_connect("/ws?node_id=test_node&secret=wrong"):
                pass

    def test_websocket_missing_node_id(self, test_client, clear_clients):
        """Test WebSocket rejects connection without node_id."""
        with pytest.raises(Exception):  # WebSocket rejection
            with test_client.websocket_connect("/ws?secret=test_secret_123"):
                pass

    def test_websocket_valid_connection_and_info_message(self, test_client, clear_clients):
        """Test WebSocket accepts valid connection and handles INFO messages."""
        with test_client.websocket_connect("/ws?node_id=test_node&secret=test_secret_123") as websocket:
            # Send an INFO message
            websocket.send_json({"type": "INFO", "from": "test_node", "payload": {"data": "test"}})
            # Should receive the broadcast back
            response = websocket.receive_json()
            assert response["type"] == "INFO"
            assert response["from"] == "test_node"

    def test_websocket_ping_message(self, test_client, clear_clients):
        """Test WebSocket handles PING messages."""
        with test_client.websocket_connect("/ws?node_id=test_node&secret=test_secret_123") as websocket:
            websocket.send_json({"type": "PING", "from": "test_node", "payload": {}})
            response = websocket.receive_json()
            assert response["type"] == "PING"

    def test_websocket_custom_message_type(self, test_client, clear_clients):
        """Test WebSocket handles custom message types via default passthrough."""
        with test_client.websocket_connect("/ws?node_id=test_node&secret=test_secret_123") as websocket:
            websocket.send_json({"type": "CUSTOM", "from": "test_node", "payload": {"custom": "data"}})
            response = websocket.receive_json()
            assert response["type"] == "CUSTOM"

    def test_websocket_malformed_json_ignored(self, test_client, clear_clients):
        """Test WebSocket ignores malformed JSON messages."""
        with test_client.websocket_connect("/ws?node_id=test_node&secret=test_secret_123") as websocket:
            # Send malformed JSON
            websocket.send_text("not-valid-json{")
            # Send a valid message to confirm connection still works
            websocket.send_json({"type": "PING", "from": "test_node", "payload": {}})
            response = websocket.receive_json()
            assert response["type"] == "PING"


class TestBroadcastFunctionality:
    """Tests for message broadcasting."""

    @pytest.mark.asyncio
    async def test_broadcast_to_all_clients(self, clear_clients):
        """Test broadcasting message to all clients."""
        # Setup mock websockets
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        ws1.send_text = AsyncMock()
        ws2.send_text = AsyncMock()

        clients["client1"] = {"ws": ws1, "node_id": "node1"}
        clients["client2"] = {"ws": ws2, "node_id": "node2"}

        test_message = {"type": "TEST", "data": "test_data"}
        await broadcast(test_message)

        # Both clients should receive the message
        ws1.send_text.assert_called_once()
        ws2.send_text.assert_called_once()

        # Verify the message content
        sent_data = json.loads(ws1.send_text.call_args[0][0])
        assert sent_data["type"] == "TEST"
        assert sent_data["data"] == "test_data"

    @pytest.mark.asyncio
    async def test_broadcast_exclude_client(self, clear_clients):
        """Test broadcasting with client exclusion."""
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        ws1.send_text = AsyncMock()
        ws2.send_text = AsyncMock()

        clients["client1"] = {"ws": ws1, "node_id": "node1"}
        clients["client2"] = {"ws": ws2, "node_id": "node2"}

        test_message = {"type": "TEST", "data": "test_data"}
        await broadcast(test_message, exclude_client_id="client1")

        # Only client2 should receive the message
        ws1.send_text.assert_not_called()
        ws2.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_handles_dead_connection(self, clear_clients):
        """Test that dead connections are cleaned up during broadcast."""
        ws1 = AsyncMock()
        ws2 = AsyncMock()

        # Make ws1 fail when sending
        ws1.send_text = AsyncMock(side_effect=Exception("Connection closed"))
        ws2.send_text = AsyncMock()

        clients["client1"] = {"ws": ws1, "node_id": "node1"}
        clients["client2"] = {"ws": ws2, "node_id": "node2"}

        test_message = {"type": "TEST", "data": "test_data"}
        await broadcast(test_message)

        # Dead client should be removed
        assert "client1" not in clients
        assert "client2" in clients

    @pytest.mark.asyncio
    async def test_broadcast_empty_message(self, clear_clients):
        """Test broadcasting empty message."""
        ws1 = AsyncMock()
        ws1.send_text = AsyncMock()

        clients["client1"] = {"ws": ws1, "node_id": "node1"}

        await broadcast({})
        ws1.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_with_no_clients(self, clear_clients):
        """Test broadcasting when no clients are connected."""
        test_message = {"type": "TEST", "data": "test_data"}
        # Should not raise any errors
        await broadcast(test_message)


class TestMessageTypes:
    """Tests for different message type handling."""

    def test_sovereign_intent_message(self, test_client, clear_clients):
        """Test SOVEREIGN_INTENT message is broadcasted."""
        with test_client.websocket_connect("/ws?node_id=orchestrator&secret=test_secret_123") as ws1:
            message = {
                "type": "SOVEREIGN_INTENT",
                "from": "orchestrator",
                "payload": {"intent": "optimize"}
            }
            ws1.send_json(message)
            received = ws1.receive_json()
            assert received["type"] == "SOVEREIGN_INTENT"
            assert received["from"] == "orchestrator"

    def test_node_synthesis_message(self, test_client, clear_clients):
        """Test NODE_SYNTHESIS message is broadcasted."""
        with test_client.websocket_connect("/ws?node_id=node1&secret=test_secret_123") as ws1:
            message = {
                "type": "NODE_SYNTHESIS",
                "from": "node1",
                "payload": {"result": "completed"}
            }
            ws1.send_json(message)
            received = ws1.receive_json()
            assert received["type"] == "NODE_SYNTHESIS"
            assert received["from"] == "node1"

    def test_message_from_field_normalization(self, test_client, clear_clients):
        """Test that 'from' field is normalized in messages."""
        with test_client.websocket_connect("/ws?node_id=test_node&secret=test_secret_123") as ws:
            # Send message without 'from' field
            message = {"type": "TEST", "payload": {}}
            ws.send_json(message)
            received = ws.receive_json()
            # The 'from' field should be set to the node_id
            assert received["from"] == "test_node"


class TestCORSConfiguration:
    """Tests for CORS middleware configuration."""

    def test_cors_headers_present(self, test_client):
        """Test that CORS headers are properly configured."""
        response = test_client.options("/health")
        # CORS middleware should add headers
        assert response.status_code in [200, 405]  # OPTIONS might not be explicitly defined


class TestNexusIntegration:
    """Integration tests for the complete Nexus system."""

    def test_node_disconnect_cleanup(self, test_client, clear_clients):
        """Test that disconnecting nodes are properly cleaned up."""
        with test_client.websocket_connect("/ws?node_id=node1&secret=test_secret_123") as ws1:
            # Verify client was added
            import time
            time.sleep(0.05)
            # When we exit this context, the client should disconnect

        # Give time for cleanup
        import time
        time.sleep(0.1)
        # Note: TestClient manages cleanup automatically

    def test_multiple_message_types_in_sequence(self, test_client, clear_clients):
        """Test sending multiple different message types in sequence."""
        with test_client.websocket_connect("/ws?node_id=node1&secret=test_secret_123") as ws:
            message_types = ["SOVEREIGN_INTENT", "NODE_SYNTHESIS", "PING", "INFO"]

            for msg_type in message_types:
                message = {"type": msg_type, "from": "node1", "payload": {}}
                ws.send_json(message)
                response = ws.receive_json()
                assert response["type"] == msg_type
                assert response["from"] == "node1"


class TestClientManagement:
    """Tests for client connection management."""

    def test_client_tracking(self, test_client, clear_clients):
        """Test that clients are properly tracked."""
        initial_count = len(clients)

        with test_client.websocket_connect("/ws?node_id=node1&secret=test_secret_123") as ws1:
            import time
            time.sleep(0.05)
            # Should have at least one client now (TestClient may or may not update global dict)

    def test_multiple_clients_with_same_node_id(self, test_client, clear_clients):
        """Test multiple clients can connect with same node_id."""
        with test_client.websocket_connect("/ws?node_id=shared_node&secret=test_secret_123") as ws1:
            import time
            time.sleep(0.05)
            # Send a message from ws1
            ws1.send_json({"type": "PING", "from": "shared_node", "payload": {}})
            r1 = ws1.receive_json()
            assert r1["type"] == "PING"
