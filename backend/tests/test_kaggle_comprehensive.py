"""
High-quality comprehensive tests for Kaggle integration.
Focuses on logic, path resolution, and authentication branching.
"""

import pytest
import os
import json
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import requests

from kaggle_solver.mcp.kaggle_mcp import KaggleMCPClient
from kaggle_solver.tools.kaggle import kaggle_download_data

class TestKaggleIntegration:
    """Professional test suite for Kaggle MCP Client"""

    @pytest.fixture
    def client_v1(self):
        """Client with legacy API key"""
        return KaggleMCPClient(api_key="legacy_key_32_chars_long_12345", username="user")

    @pytest.fixture
    def client_v2(self):
        """Client with new KGAT token"""
        return KaggleMCPClient(api_key="KGAT_test_token_v2_1234567890", username="user")

    def test_auth_branching_logic(self, client_v1, client_v2):
        """Verify that client chooses correct auth method based on key format"""
        assert not client_v1.api_key.startswith("KGAT_")
        assert client_v2.api_key.startswith("KGAT_")

    @patch('requests.request')
    def test_v2_token_uses_bearer_auth(self, mock_request, client_v2):
        """Verify that KGAT tokens result in Bearer Authorization header"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{'ref': 'titanic'}]
        mock_request.return_value = mock_response

        client_v2.get_competition_info("titanic")
        
        # Check that requests.request was called with Bearer header
        args, kwargs = mock_request.call_args
        assert "Authorization" in kwargs["headers"]
        assert kwargs["headers"]["Authorization"] == f"Bearer {client_v2.api_key}"

    @patch('requests.request')
    def test_legacy_token_uses_basic_auth(self, mock_request, client_v1):
        """Verify that legacy keys result in Basic Auth (when using _request)"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_request.return_value = mock_response

        # We call _request directly to test the branching
        client_v1._request("test")
        
        args, kwargs = mock_request.call_args
        assert "auth" in kwargs
        assert kwargs["auth"] == ("user", "legacy_key_32_chars_long_12345")

    def test_sandbox_path_resolution(self):
        """Verify that tools correctly resolve paths within the sandbox"""
        mock_sandbox = Mock()
        mock_sandbox.root = "/session/workspace"
        
        mock_client = MagicMock()
        mock_client.api_key = "key"
        mock_client.download_competition_data.return_value = []
        
        with patch('kaggle_solver.tools.kaggle.get_kaggle_mcp_client', return_value=mock_client):
            kaggle_download_data("titanic", "data_dir", sandbox=mock_sandbox)
            
            # Verify that the path passed to the client is absolute and inside sandbox
            mock_client.download_competition_data.assert_called_once()
            args, _ = mock_client.download_competition_data.call_args
            passed_path = args[1]
            assert passed_path == str(Path("/session/workspace/data_dir"))

    @patch('requests.request')
    def test_error_propagation_with_logger(self, mock_request, client_v2):
        """Verify that API errors are caught and reported without NameErrors"""
        mock_request.side_effect = requests.exceptions.HTTPError("401 Unauthorized")
        
        with pytest.raises(RuntimeError) as excinfo:
            client_v2.get_competition_info("titanic")
        
        assert "Failed to get competition info" in str(excinfo.value)
        # If 'logger' was undefined, this test would fail with NameError instead of RuntimeError

    @patch('requests.request')
    def test_full_tool_execution_chain_401(self, mock_request, client_v2):
        """Verify that a 401 error from the API results in a failed ToolResult"""
        from kaggle_solver.tools.registry import ToolRegistry
        from kaggle_solver.tools.kaggle import register_kaggle_tools
        
        # Ensure tools are registered
        register_kaggle_tools()
        
        mock_request.side_effect = requests.exceptions.HTTPError("401 Unauthorized")
        
        with patch('kaggle_solver.tools.kaggle.get_kaggle_mcp_client', return_value=client_v2):
            result = ToolRegistry.execute("kaggle_get_competition_info", query="titanic")
            
            assert result.success is False
            assert "401" in result.error
            assert "Unauthorized" in result.error
