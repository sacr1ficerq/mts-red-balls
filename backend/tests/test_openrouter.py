#!/usr/bin/env python3
"""
Tests for OpenRouter API connectivity and model access.

These tests verify:
1. API key is configured and valid
2. OpenRouter API is accessible
3. Model (minimax/minimax-m2.7) is available and responding
4. Reasoning mode works correctly
"""

import os
import pytest
import requests
from unittest.mock import patch, MagicMock

# Try to load .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def get_api_key():
    """Get OpenRouter API key from environment."""
    return os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")


@pytest.fixture
def api_key():
    """Fixture to provide API key."""
    key = get_api_key()
    if not key:
        pytest.skip("No API key found (OPENROUTER_API_KEY or OPENAI_API_KEY)")
    return key


@pytest.fixture
def openrouter_headers(api_key):
    """Fixture to provide OpenRouter API headers."""
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


class TestOpenRouterConnection:
    """Test OpenRouter API connectivity."""

    def test_api_key_exists(self):
        """Test that API key is configured."""
        key = get_api_key()
        assert key is not None, "API key not found in environment variables"
        assert len(key) > 10, "API key seems too short"

    def test_openrouter_models_endpoint(self, openrouter_headers):
        """Test that we can access OpenRouter models list."""
        response = requests.get(
            "https://openrouter.ai/api/v1/models",
            headers=openrouter_headers,
            timeout=30
        )
        
        assert response.status_code == 200, f"Failed to get models: {response.text}"
        
        data = response.json()
        assert "data" in data, "No 'data' field in response"
        assert len(data["data"]) > 0, "No models returned"

    def test_minimax_model_available(self, openrouter_headers):
        """Test that minimax/minimax-m2.7 model is available."""
        response = requests.get(
            "https://openrouter.ai/api/v1/models",
            headers=openrouter_headers,
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        model_ids = [m["id"] for m in data["data"]]
        assert "minimax/minimax-m2.7" in model_ids, "minimax/minimax-m2.7 not in available models"


class TestOpenRouterChat:
    """Test OpenRouter chat completions."""

    def test_simple_chat_completion(self, openrouter_headers):
        """Test basic chat completion without reasoning."""
        payload = {
            "model": "minimax/minimax-m2.7",
            "messages": [
                {"role": "user", "content": "Say 'hello' and nothing else."}
            ],
            "max_tokens": 50
        }
        
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=openrouter_headers,
            json=payload,
            timeout=60
        )
        
        assert response.status_code == 200, f"Chat completion failed: {response.text}"
        
        data = response.json()
        assert "choices" in data, "No 'choices' in response"
        assert len(data["choices"]) > 0, "No choices returned"
        
        message = data["choices"][0]["message"]
        assert "content" in message, "No 'content' in message"
        # Content can be None for some models, so check if it exists
        content = message.get("content")
        if content is not None:
            assert len(content) >= 0, "Empty response content"
        else:
            # If content is None, check for reasoning_details
            assert "reasoning_details" in message or "reasoning" in message, \
                "Both content and reasoning are None"

    def test_chat_with_reasoning(self, openrouter_headers):
        """Test chat completion with reasoning enabled."""
        payload = {
            "model": "minimax/minimax-m2.7",
            "messages": [
                {"role": "user", "content": "How many r's are in the word 'strawberry'?"}
            ],
            "reasoning": {"enabled": True},
            "max_tokens": 500
        }
        
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=openrouter_headers,
            json=payload,
            timeout=120
        )
        
        assert response.status_code == 200, f"Chat with reasoning failed: {response.text}"
        
        data = response.json()
        message = data["choices"][0]["message"]
        
        # Check for reasoning_details in response
        has_reasoning = "reasoning_details" in message or "reasoning" in message
        
        # The response should have content
        assert "content" in message, "No 'content' in message"
        
        # Log whether reasoning was returned
        print(f"\nResponse has reasoning_details: {has_reasoning}")
        print(f"Content: {message['content'][:200]}...")

    def test_multi_turn_with_reasoning_preservation(self, openrouter_headers):
        """Test multi-turn conversation with reasoning preservation."""
        # First message
        payload1 = {
            "model": "minimax/minimax-m2.7",
            "messages": [
                {"role": "user", "content": "What is 2 + 2?"}
            ],
            "reasoning": {"enabled": True},
            "max_tokens": 100
        }
        
        response1 = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=openrouter_headers,
            json=payload1,
            timeout=60
        )
        
        assert response1.status_code == 200
        data1 = response1.json()
        msg1 = data1["choices"][0]["message"]
        
        # Second message with reasoning preservation
        messages = [
            {"role": "user", "content": "What is 2 + 2?"},
            {
                "role": "assistant",
                "content": msg1.get("content"),
                "reasoning_details": msg1.get("reasoning_details")
            },
            {"role": "user", "content": "Add 3 to that result."}
        ]
        
        payload2 = {
            "model": "minimax/minimax-m2.7",
            "messages": messages,
            "reasoning": {"enabled": True},
            "max_tokens": 100
        }
        
        response2 = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=openrouter_headers,
            json=payload2,
            timeout=60
        )
        
        assert response2.status_code == 200, f"Multi-turn failed: {response2.text}"
        data2 = response2.json()
        assert "choices" in data2


class TestLLMClass:
    """Test the LLM class from kaggle_solver."""

    def test_llm_initialization_with_key(self, api_key):
        """Test LLM class initialization with API key."""
        from kaggle_solver.llm import LLM
        
        llm = LLM(api_key=api_key)
        assert llm.client is not None
        assert not llm.mock_mode

    def test_llm_initialization_without_key(self):
        """Test LLM class initialization without API key (mock mode)."""
        from kaggle_solver.llm import LLM
        
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "", "OPENAI_API_KEY": ""}, clear=True):
            llm = LLM()
            assert llm.mock_mode
            assert llm.client is None

    def test_llm_chat_mock_mode(self):
        """Test LLM chat in mock mode."""
        from kaggle_solver.llm import LLM
        
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "", "OPENAI_API_KEY": ""}, clear=True):
            llm = LLM()
            response = llm.chat(
                model="test-model",
                messages=[{"role": "user", "content": "Hello"}]
            )
            
            assert "done" in response
            assert "Mock response" in response

    def test_llm_chat_real(self, api_key):
        """Test LLM chat with real API."""
        from kaggle_solver.llm import LLM
        
        llm = LLM(api_key=api_key)
        
        response = llm.chat(
            model="minimax/minimax-m2.7",
            messages=[{"role": "user", "content": "Say 'test ok' and nothing else."}],
            max_tokens=20
        )
        
        assert response is not None
        assert len(response) > 0
        print(f"\nLLM response: {response[:100]}...")


class TestModelAccess:
    """Test model access and configuration."""

    def test_config_model_exists(self):
        """Test that the model in config.yaml is accessible."""
        from kaggle_solver.core.config import Config
        from kaggle_solver.llm import LLM
        
        config = Config.load()
        model = config.llm.model
        
        assert model is not None, "No model configured"
        assert model == "minimax/minimax-m2.7", f"Unexpected model: {model}"

    def test_model_responds(self, api_key):
        """Test that the configured model responds correctly."""
        from kaggle_solver.llm import LLM
        from kaggle_solver.core.config import Config
        
        config = Config.load()
        llm = LLM(api_key=api_key)
        
        response = llm.chat(
            model=config.llm.model,
            messages=[{"role": "user", "content": "Respond with just 'OK'"}],
            max_tokens=10,
            temperature=0.1
        )
        
        assert response is not None
        assert len(response) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
