import time
import logging
import pytest

# Configure logging for tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Test configuration
ACCESS_TOKEN = "secret-token"
TEST_SESSION_ID = "test-session-123"

# Test headers
DEFAULT_HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "X-SESSION-ID": TEST_SESSION_ID,
    "Content-Type": "application/json",
}


@pytest.mark.integration
class TestShipyard:
    """Integration tests for Shipyard system"""

    def test_health_check(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ok"

    def test_unauthorized_access(self, client):
        """Test that unauthorized requests are rejected"""
        # Test without token
        response = client.post(
            "/ship", json={"ttl": 300}, headers={"X-SESSION-ID": TEST_SESSION_ID}
        )
        assert response.status_code == 403

        # Test with wrong token
        response = client.post(
            "/ship",
            json={"ttl": 300},
            headers={
                "Authorization": "Bearer wrong-token",
                "X-SESSION-ID": TEST_SESSION_ID,
            },
        )
        assert response.status_code == 401

    def test_ship_lifecycle(self, client):
        """Test complete ship lifecycle: create, get, delete"""
        # Create ship
        create_data = {
            "ttl": 600,
            "spec": {"cpus": 0.5, "memory": "256m"},
            "max_session_num": 1,
        }

        response = client.post("/ship", json=create_data, headers=DEFAULT_HEADERS)
        assert response.status_code == 201

        ship_data = response.json()
        print(ship_data)  # For debugging purposes
        ship_id = ship_data["id"]

        # Validate ship data
        assert ship_data["status"] == 1  # running
        assert ship_data["ttl"] == 600
        assert ship_data["max_session_num"] == 1
        assert ship_data["current_session_num"] == 1
        assert "created_at" in ship_data
        assert "updated_at" in ship_data

        # Get ship info
        response = client.get(f"/ship/{ship_id}", headers=DEFAULT_HEADERS)
        assert response.status_code == 200

        retrieved_ship = response.json()
        assert retrieved_ship["id"] == ship_id
        assert retrieved_ship["status"] == 1

        # Wait for ship to be fully ready (container should be running)
        time.sleep(5)

        # Get ship again to check if container_id is set
        response = client.get(f"/ship/{ship_id}", headers=DEFAULT_HEADERS)
        ship_info = response.json()
        logger.info(f"Ship info after startup: {ship_info}")

        # Delete ship
        response = client.delete(f"/ship/{ship_id}", headers=DEFAULT_HEADERS)
        assert response.status_code == 204

        # Verify ship is deleted
        response = client.get(f"/ship/{ship_id}", headers=DEFAULT_HEADERS)
        assert response.status_code == 404

    def test_ship_not_found(self, client):
        """Test getting non-existent ship"""
        fake_ship_id = "non-existent-ship-id"

        response = client.get(f"/ship/{fake_ship_id}", headers=DEFAULT_HEADERS)
        assert response.status_code == 404

        response = client.delete(f"/ship/{fake_ship_id}", headers=DEFAULT_HEADERS)
        assert response.status_code == 404

    def test_ship_operations(self, client):
        """Test ship operations (file system, shell, ipython)"""
        # Create a ship first
        create_data = {"ttl": 600}
        response = client.post("/ship", json=create_data, headers=DEFAULT_HEADERS)
        assert response.status_code == 201

        ship_data = response.json()
        ship_id = ship_data["id"]

        # Wait for ship to be ready
        time.sleep(10)

        # Test headers for operations
        op_headers = {
            **DEFAULT_HEADERS,
        }

        try:
            # Test file system operations
            self._test_filesystem_operations(client, ship_id, op_headers)

            # Test file upload operations
            self._test_file_upload_operations(client, ship_id, op_headers)

            # Test shell operations
            self._test_shell_operations(client, ship_id, op_headers)

            # Test IPython operations
            self._test_ipython_operations(client, ship_id, op_headers)

        finally:
            # Clean up
            client.delete(f"/ship/{ship_id}", headers=DEFAULT_HEADERS)

    def _test_filesystem_operations(self, client, ship_id: str, headers: dict):
        """Test file system operations"""
        # Create a file
        create_file_data = {
            "type": "fs/create_file",
            "payload": {"path": "test_file.txt", "content": "Hello, World!"},
        }

        response = client.post(
            f"/ship/{ship_id}/exec", json=create_file_data, headers=headers
        )
        print(response.json())  # For debugging purposes
        assert response.status_code == 200

        result = response.json()
        assert result["success"] is True

        # Read the file
        read_file_data = {"type": "fs/read_file", "payload": {"path": "test_file.txt"}}

        response = client.post(
            f"/ship/{ship_id}/exec", json=read_file_data, headers=headers
        )
        print(response.json())
        assert response.status_code == 200

        result = response.json()
        assert result["success"] is True
        assert result["data"]["content"] == "Hello, World!"

        # Write to the file
        write_file_data = {
            "type": "fs/write_file",
            "payload": {"path": "test_file.txt", "content": "Updated content!"},
        }

        response = client.post(
            f"/ship/{ship_id}/exec", json=write_file_data, headers=headers
        )
        print(response.json())
        assert response.status_code == 200

        # List directory
        list_dir_data = {"type": "fs/list_dir", "payload": {"path": "./"}}

        response = client.post(
            f"/ship/{ship_id}/exec", json=list_dir_data, headers=headers
        )
        print(response.json())
        assert response.status_code == 200

        result = response.json()
        assert result["success"] is True

        # Delete the file
        delete_file_data = {
            "type": "fs/delete_file",
            "payload": {"path": "test_file.txt"},
        }

        response = client.post(
            f"/ship/{ship_id}/exec", json=delete_file_data, headers=headers
        )
        print(response.json())
        assert response.status_code == 200

        result = response.json()
        assert result["success"] is True

    def _test_file_upload_operations(self, client, ship_id: str, headers: dict):
        """Test file upload operations"""
        import tempfile
        import os

        # Create test file content
        test_content = (
            b"Hello, this is a test file for upload!\nLine 2\nLine 3\nBinary data: \x00\x01\x02\x03"
        )

        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(test_content)
            temp_file_path = temp_file.name

        try:
            # Test 1: Upload file to relative path
            upload_headers = {
                "Authorization": headers["Authorization"],
                "X-SESSION-ID": headers["X-SESSION-ID"],
                "X-FILE-PATH": "uploads/test_file.txt",
            }

            with open(temp_file_path, "rb") as f:
                files = {"file": (f.name, f, "application/octet-stream")}
                response = client.post(
                    f"/ship/{ship_id}/upload",
                    files=files,
                    headers=upload_headers,
                )

            print(f"Upload test 1 response: {response.json()}")
            assert response.status_code == 200

            result = response.json()
            assert result["success"] is True
            assert "uploads/test_file.txt" in result["file_path"]

            # Test 2: Verify uploaded file can be read via filesystem API
            read_file_data = {
                "type": "fs/read_file",
                "payload": {"path": "uploads/test_file.txt"},
            }

            response = client.post(
                f"/ship/{ship_id}/exec", json=read_file_data, headers=headers
            )
            print(f"Read uploaded file response: {response.json()}")
            assert response.status_code == 200

            result = response.json()
            assert result["success"] is True
            # Note: Binary content might be encoded differently, so just check it exists
            assert "content" in result["data"]

            # Test 3: Upload binary file (image-like data)
            binary_content = bytes(range(256))  # 0-255 byte values

            with tempfile.NamedTemporaryFile(delete=False) as binary_file:
                binary_file.write(binary_content)
                binary_file_path = binary_file.name

            try:
                upload_headers["X-FILE-PATH"] = "uploads/binary_test.bin"

                with open(binary_file_path, "rb") as f:
                    files = {"file": (f.name, f, "application/octet-stream")}
                    response = client.post(
                        f"/ship/{ship_id}/upload",
                        files=files,
                        headers=upload_headers,
                    )

                print(f"Binary upload response: {response.json()}")
                assert response.status_code == 200

                result = response.json()
                assert result["success"] is True

            finally:
                os.unlink(binary_file_path)

            # Test 4: Test upload path security (should fail)
            upload_headers["X-FILE-PATH"] = "../../../etc/passwd"

            with open(temp_file_path, "rb") as f:
                files = {"file": (f.name, f, "application/octet-stream")}
                response = client.post(
                    f"/ship/{ship_id}/upload",
                    files=files,
                    headers=upload_headers,
                )

            print(f"Security test response: {response.json()}")
            # Should return error due to path validation
            assert response.status_code != 200

            result = response.json()
            assert "access" in result["detail"].lower() or "path" in result["detail"].lower()

        finally:
            os.unlink(temp_file_path)

    def _test_shell_operations(self, client, ship_id: str, headers: dict):
        """Test shell operations"""
        # Execute shell command
        shell_data = {
            "type": "shell/exec",
            "payload": {"command": "echo 'Hello from shell'", "timeout": 10},
        }

        response = client.post(
            f"/ship/{ship_id}/exec", json=shell_data, headers=headers
        )
        print(response.json())
        assert response.status_code == 200

        result = response.json()
        assert result["success"] is True
        assert "Hello from shell" in result["data"]["stdout"]
        assert result["data"]["return_code"] == 0

        # Test command that produces error
        shell_error_data = {
            "type": "shell/exec",
            "payload": {"command": "ls /nonexistent", "timeout": 10},
        }

        response = client.post(
            f"/ship/{ship_id}/exec", json=shell_error_data, headers=headers
        )
        print(response.json())
        assert response.status_code == 200

        result = response.json()
        assert (
            result["success"] is True
        )  # Command executed, but with non-zero exit code
        assert result["data"]["return_code"] != 0

    def _test_ipython_operations(self, client, ship_id: str, headers: dict):
        """Test IPython operations"""
        # Execute Python code
        ipython_data = {
            "type": "ipython/exec",
            "payload": {"code": "x = 5 + 3\nprint(f'Result: {x}')", "timeout": 10},
        }

        response = client.post(
            f"/ship/{ship_id}/exec", json=ipython_data, headers=headers
        )
        print(response.json())
        assert response.status_code == 200

        result = response.json()
        assert result["success"] is True
        assert "Result: 8" in result["data"]["output"]["text"]

        # Test code with import
        import_data = {
            "type": "ipython/exec",
            "payload": {
                "code": "import math\nresult = math.sqrt(16)\nprint(f'Square root of 16 is {result}')",
                "timeout": 10,
            },
        }

        response = client.post(
            f"/ship/{ship_id}/exec", json=import_data, headers=headers
        )
        print(response.json())
        assert response.status_code == 200

        result = response.json()
        assert result["success"] is True
        assert "Square root of 16 is 4.0" in result["data"]["output"]["text"]

    def test_ship_ttl_extension(self, client):
        """Test extending ship TTL"""
        # Create ship
        create_data = {"ttl": 300}
        response = client.post("/ship", json=create_data, headers=DEFAULT_HEADERS)
        assert response.status_code == 201

        ship_data = response.json()
        ship_id = ship_data["id"]
        original_ttl = ship_data["ttl"]

        try:
            # Extend TTL
            extend_data = {"ttl": 600}
            response = client.post(
                f"/ship/{ship_id}/extend-ttl", json=extend_data, headers=DEFAULT_HEADERS
            )
            assert response.status_code == 200

            updated_ship = response.json()
            assert updated_ship["ttl"] == 600
            assert updated_ship["ttl"] > original_ttl

        finally:
            # Clean up
            client.delete(f"/ship/{ship_id}", headers=DEFAULT_HEADERS)

    def test_ship_logs(self, client):
        """Test getting ship logs"""
        # Create ship
        create_data = {"ttl": 300}
        response = client.post("/ship", json=create_data, headers=DEFAULT_HEADERS)
        assert response.status_code == 201

        ship_data = response.json()
        ship_id = ship_data["id"]

        # Wait for ship to generate some logs
        time.sleep(5)

        try:
            # Get logs
            response = client.get(f"/ship/logs/{ship_id}", headers=DEFAULT_HEADERS)
            assert response.status_code == 200

            logs_data = response.json()
            assert "logs" in logs_data
            assert isinstance(logs_data["logs"], str)

        finally:
            # Clean up
            client.delete(f"/ship/{ship_id}", headers=DEFAULT_HEADERS)

    def test_multiple_sessions(self, client):
        """Test ship reuse with multiple sessions"""
        # Create ship with max_session_num = 2
        create_data = {"ttl": 600, "max_session_num": 2}
        response = client.post("/ship", json=create_data, headers=DEFAULT_HEADERS)
        assert response.status_code == 201

        ship_data = response.json()
        ship_id = ship_data["id"]
        assert ship_data["current_session_num"] == 1

        try:
            # Try to use ship with another session
            headers_session2 = {**DEFAULT_HEADERS, "X-SESSION-ID": "test-session-456"}

            response = client.post("/ship", json=create_data, headers=headers_session2)
            # Should reuse existing ship since max_session_num = 2
            assert response.status_code == 201

            reused_ship = response.json()
            # Should be the same ship or a new one depending on implementation
            logger.info(f"Original ship: {ship_id}, Reused ship: {reused_ship['id']}")

        finally:
            # Clean up
            client.delete(f"/ship/{ship_id}", headers=DEFAULT_HEADERS)

    def test_invalid_operations(self, client):
        """Test invalid operation requests"""
        # Create ship
        create_data = {"ttl": 300}
        response = client.post("/ship", json=create_data, headers=DEFAULT_HEADERS)
        assert response.status_code == 201

        ship_data = response.json()
        ship_id = ship_data["id"]

        try:
            # Test mismatched Ship ID in header and URL
            headers_wrong_id = {**DEFAULT_HEADERS}

            invalid_op_data = {
                "type": "shell/exec",
                "payload": {"command": "echo test"},
            }

            response = client.post(
                "/ship/wrong-ship-id/exec", json=invalid_op_data, headers=headers_wrong_id
            )
            print(response.json())
            assert response.status_code != 200

            # Test invalid operation type (should fail validation)
            invalid_type_data = {
                "type": "invalid/operation",
                "payload": {"command": "echo test"},
            }

            headers_correct = {**DEFAULT_HEADERS}

            response = client.post(
                f"/ship/{ship_id}/exec", json=invalid_type_data, headers=headers_correct
            )
            assert response.status_code != 200  # Validation error

        finally:
            # Clean up
            client.delete(f"/ship/{ship_id}", headers=DEFAULT_HEADERS)


if __name__ == "__main__":
    # For manual testing
    pytest.main([__file__, "-v", "-s"])
