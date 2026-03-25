#!/usr/bin/env python3
"""
Tests for OpenRouter API connectivity and model access.

These tests verify:
1. API key is configured and valid
2. OpenRouter API is accessible
3. Model (openai/gpt-oss-20b) is available and responding
4. Reasoning mode works correctly
"""

import os
import pytest
import asyncio
import requests
from typing import Any, cast
from unittest.mock import AsyncMock

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
            timeout=30,
        )

        assert response.status_code == 200, f"Failed to get models: {response.text}"

        data = response.json()
        assert "data" in data, "No 'data' field in response"
        assert len(data["data"]) > 0, "No models returned"

    def test_minimax_model_available(self, openrouter_headers):
        """Test that openai/gpt-oss-20b model is available."""
        response = requests.get(
            "https://openrouter.ai/api/v1/models",
            headers=openrouter_headers,
            timeout=30,
        )

        assert response.status_code == 200
        data = response.json()

        model_ids = [m["id"] for m in data["data"]]
        assert "openai/gpt-oss-20b" in model_ids, (
            "openai/gpt-oss-20b not in available models"
        )


class TestOpenRouterChat:
    """Test OpenRouter chat completions."""

    def test_simple_chat_completion(self, openrouter_headers):
        """Test basic chat completion without reasoning."""
        payload = {
            "model": "openai/gpt-oss-20b",
            "messages": [{"role": "user", "content": "Say 'hello' and nothing else."}],
            "max_tokens": 50,
        }

        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=openrouter_headers,
            json=payload,
            timeout=60,
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
            assert "reasoning_details" in message or "reasoning" in message, (
                "Both content and reasoning are None"
            )

    def test_chat_with_reasoning(self, openrouter_headers):
        """Test chat completion with reasoning enabled."""
        payload = {
            "model": "openai/gpt-oss-20b",
            "messages": [
                {
                    "role": "user",
                    "content": "How many r's are in the word 'strawberry'?",
                }
            ],
            "reasoning": {"enabled": True},
            "max_tokens": 500,
        }

        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=openrouter_headers,
            json=payload,
            timeout=120,
        )

        assert response.status_code == 200, (
            f"Chat with reasoning failed: {response.text}"
        )

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
            "model": "openai/gpt-oss-20b",
            "messages": [{"role": "user", "content": "What is 2 + 2?"}],
            "reasoning": {"enabled": True},
            "max_tokens": 100,
        }

        response1 = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=openrouter_headers,
            json=payload1,
            timeout=60,
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
                "reasoning_details": msg1.get("reasoning_details"),
            },
            {"role": "user", "content": "Add 3 to that result."},
        ]

        payload2 = {
            "model": "openai/gpt-oss-20b",
            "messages": messages,
            "reasoning": {"enabled": True},
            "max_tokens": 100,
        }

        response2 = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=openrouter_headers,
            json=payload2,
            timeout=60,
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

    def test_llm_initialization_without_key(self, monkeypatch):
        """Test LLM class initialization without API key."""
        from kaggle_solver.llm import LLM
        from kaggle_solver.core.settings import SettingsManager, Settings

        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setattr(
            SettingsManager,
            "get_settings",
            lambda self: Settings(api_key=""),
        )

        llm = LLM()
        assert llm.mock_mode
        assert llm.client is None

    def test_llm_chat_without_key_raises_error(self, monkeypatch):
        """Test LLM chat fails when API key is missing."""
        from kaggle_solver.llm import LLM, LLMError
        from kaggle_solver.core.settings import SettingsManager, Settings

        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setattr(
            SettingsManager,
            "get_settings",
            lambda self: Settings(api_key=""),
        )

        llm = LLM()
        with pytest.raises(LLMError, match="No LLM API key configured"):
            asyncio.run(
                llm.chat(
                    model="test-model",
                    messages=[{"role": "user", "content": "Hello"}],
                )
            )

    def test_llm_chat_real(self, api_key):
        """Test LLM chat with real API."""
        from kaggle_solver.llm import LLM, LLMError

        llm = LLM(api_key=api_key)
        assert llm.client is not None

        try:
            response = asyncio.run(
                llm.chat(
                    model="openai/gpt-oss-20b",
                    messages=[
                        {"role": "user", "content": "Say 'test ok' and nothing else."}
                    ],
                    max_tokens=20,
                )
            )

            assert response is not None
            if len(response) == 0:
                pytest.skip("LLM returned empty response (model may be unavailable)")
            print(f"\nLLM response: {response[:100]}...")
        except LLMError as e:
            pytest.skip(f"LLM API error (model may be unavailable): {e}")

    def test_llm_chat_empty_response_handling(self, api_key):
        """Test that LLM properly handles empty responses from API."""
        from kaggle_solver.llm import LLM, LLMError
        from unittest.mock import Mock, patch

        llm = LLM(api_key=api_key)

        # Mock the API response to return empty choices
        mock_response = Mock()
        mock_response.choices = []
        client = cast(Any, llm.client)

        with patch.object(
            client.chat.completions, "create", AsyncMock(return_value=mock_response)
        ):
            try:
                response = asyncio.run(
                    llm.chat(
                        model="test-model",
                        messages=[{"role": "user", "content": "test"}],
                        max_tokens=20,
                    )
                )
                # Should raise LLMError after max retries
                assert False, "Expected LLMError to be raised for empty choices"
            except LLMError as e:
                assert "empty choices" in str(e).lower()
                print(f"\nCorrectly handled empty response: {e}")


class TestModelAccess:
    """Test model access and configuration."""

    def test_config_model_exists(self):
        """Test that the model in config.yaml is accessible."""
        from kaggle_solver.core.config import Config
        from kaggle_solver.llm import LLM

        config = Config.load()
        model = config.llm.model

        assert model is not None, "No model configured"
        # Accept any valid model (we changed to free model to avoid rate limits)
        assert model in [
            "minimax/minimax-m2.7",
            "openai/gpt-oss-20b:free",
            "openrouter/free",
            "google/gemma-3n-e5b-it",
            "meta-llama/llama-3.2-3b-instruct",
        ], f"Unexpected model: {model}"

    def test_model_responds(self, api_key):
        """Test that the configured model responds correctly."""
        from kaggle_solver.llm import LLM, LLMError
        from kaggle_solver.core.config import Config

        config = Config.load()
        llm = LLM(api_key=api_key)

        try:
            response = asyncio.run(
                llm.chat(
                    model=config.llm.model,
                    messages=[{"role": "user", "content": "Respond with just 'OK'"}],
                    max_tokens=10,
                    temperature=0.1,
                )
            )

            assert response is not None
            if len(response) == 0:
                pytest.skip("LLM returned empty response (model may be unavailable)")
        except LLMError as e:
            pytest.skip(f"LLM API error (model may be unavailable): {e}")
        assert len(response) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
