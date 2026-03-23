import os
import asyncio
import json
import logging
import time
from typing import List, Dict, Optional, Callable, AsyncGenerator
from collections import deque

from openai import AsyncOpenAI, APIError, RateLimitError, APITimeoutError
from kaggle_solver import get_project_root
from kaggle_solver.constants import LLMConstants

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token bucket rate limiter for API requests."""

    def __init__(self, requests_per_minute: int = 8):
        self.requests_per_minute = requests_per_minute
        self.requests = deque()
        self._lock = None

    @property
    def lock(self):
        """Lazy initialization of asyncio.Lock to avoid event loop issues."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def acquire(self):
        """Wait until a request is allowed."""
        async with self.lock:
            now = time.time()
            # Remove requests older than 1 minute
            while self.requests and self.requests[0] < now - 60:
                self.requests.popleft()

            # If we've hit the limit, wait
            if len(self.requests) >= self.requests_per_minute:
                # Calculate how long to wait
                oldest_request = self.requests[0]
                wait_time = 60 - (now - oldest_request) + 0.1  # Add small buffer
                if wait_time > 0:
                    logger.info(f"Rate limit reached, waiting {wait_time:.1f}s...")
                    await asyncio.sleep(wait_time)
                    # Clean up old requests after waiting
                    now = time.time()
                    while self.requests and self.requests[0] < now - 60:
                        self.requests.popleft()

            # Record this request
            self.requests.append(now)


ENV_FILE = get_project_root() / ".env"
if ENV_FILE.exists():
    try:
        from dotenv import load_dotenv

        load_dotenv(ENV_FILE)
    except ImportError:
        pass


class LLMError(Exception):
    """Custom exception for LLM-related errors."""

    pass


class LLM:
    """Async LLM client with retry logic, exponential backoff, and rate limiting."""

    MISSING_KEY_ERROR = "No LLM API key configured. Set OPENROUTER_API_KEY/OPENAI_API_KEY or save an API key in Settings."

    def __init__(self, api_key: Optional[str] = None, requests_per_minute: int = 8):
        # Try to get API key from multiple sources in order of priority:
        # 1. Explicitly passed api_key parameter
        # 2. SettingsManager (user settings)
        # 3. Environment variables
        if not api_key:
            # Try to get from SettingsManager
            try:
                from kaggle_solver.core.settings import SettingsManager

                settings = SettingsManager().get_settings()
                api_key = settings.api_key
            except Exception as e:
                logger.debug(f"Could not get API key from settings: {e}")

        self.api_key = (
            api_key or os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
        )
        if not self.api_key:
            logger.warning("No API key found for LLM. Requests will fail.")
            self.client = None
        else:
            self.client = AsyncOpenAI(
                base_url="https://openrouter.ai/api/v1", api_key=self.api_key
            )

        # Use constants from LLMConstants
        self.max_retries = LLMConstants.MAX_RETRIES
        self.retry_base_delay = LLMConstants.RETRY_DELAY
        self.retry_backoff = LLMConstants.RETRY_BACKOFF
        self.max_rate_limit_delay = LLMConstants.MAX_RATE_LIMIT_DELAY
        self.mock_mode = self.client is None

        # Initialize rate limiter
        self.rate_limiter = RateLimiter(requests_per_minute=requests_per_minute)
        logger.info(
            f"LLM initialized with rate limit: {requests_per_minute} requests/minute"
        )

    def _ensure_client(self) -> None:
        if self.client is not None:
            return

        api_key = None
        try:
            from kaggle_solver.core.settings import SettingsManager

            settings = SettingsManager().get_settings()
            api_key = settings.api_key
        except Exception as e:
            logger.debug(f"Could not refresh API key from settings: {e}")

        api_key = (
            api_key or os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
        )
        if not api_key:
            self.mock_mode = True
            raise LLMError(self.MISSING_KEY_ERROR)

        self.api_key = api_key
        self.client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1", api_key=self.api_key
        )
        self.mock_mode = False
        logger.info("LLM client initialized from latest API key settings")

    async def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: Optional[List[Dict]] = None,
        tool_choice: Optional[Dict] = None,
    ) -> str:
        logger.debug(
            "LLM request: model=%s temp=%s max_tokens=%s messages=%s tools=%s tool_choice=%s",
            model,
            temperature,
            max_tokens,
            len(messages),
            bool(tools),
            bool(tool_choice),
        )
        for index, message in enumerate(messages):
            role = message.get("role", "unknown")
            content = message.get("content", "")
            content_preview = content[:1500]
            logger.debug(
                "LLM message[%s] role=%s chars=%s content=%r",
                index,
                role,
                len(content),
                content_preview,
            )

        self._ensure_client()

        # Apply rate limiting before making API request
        await self.rate_limiter.acquire()

        for attempt in range(self.max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    tools=tools,
                    tool_choice=tool_choice,
                )

                # Check if response is valid and has choices
                if response is None:
                    logger.error(f"LLM API returned None response for model {model}")
                    if attempt < self.max_retries - 1:
                        delay = self.retry_base_delay * (self.retry_backoff**attempt)
                        logger.warning(f"Retrying in {delay}s...")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        raise LLMError(
                            f"LLM API returned None after {self.max_retries} attempts"
                        )

                if not hasattr(response, "choices") or response.choices is None:
                    logger.error(
                        f"LLM API returned response without choices for model {model}"
                    )
                    if attempt < self.max_retries - 1:
                        delay = self.retry_base_delay * (self.retry_backoff**attempt)
                        logger.warning(f"Retrying in {delay}s...")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        raise LLMError(
                            f"LLM API returned response without choices after {self.max_retries} attempts"
                        )

                if len(response.choices) == 0:
                    logger.error(f"LLM API returned empty choices for model {model}")
                    if attempt < self.max_retries - 1:
                        delay = self.retry_base_delay * (self.retry_backoff**attempt)
                        logger.warning(f"Retrying in {delay}s...")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        raise LLMError(
                            f"LLM API returned empty choices after {self.max_retries} attempts"
                        )

                msg = response.choices[0].message
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    content = msg.content or ""
                    if not content:
                        for tc in msg.tool_calls:
                            func = tc.function
                            tool_call_id = (
                                getattr(tc, "id", None) or f"call_{func.name}"
                            )
                            if func.arguments:
                                try:
                                    args = json.loads(func.arguments)
                                    logger.debug(
                                        "LLM tool-call response: tool=%s tool_call_id=%s args=%s",
                                        func.name,
                                        tool_call_id,
                                        args,
                                    )
                                    return json.dumps(
                                        {
                                            "action": "tool",
                                            "tool": func.name,
                                            "tool_call_id": tool_call_id,
                                            **args,
                                        }
                                    )
                                except:
                                    logger.debug(
                                        "LLM tool-call response (raw args): tool=%s tool_call_id=%s args=%r",
                                        func.name,
                                        tool_call_id,
                                        func.arguments,
                                    )
                                    return json.dumps(
                                        {
                                            "action": "tool",
                                            "tool": func.name,
                                            "tool_call_id": tool_call_id,
                                            "query": func.arguments,
                                        }
                                    )
                    logger.debug(
                        "LLM response content with tool calls: %r", content[:3000]
                    )
                    return content

                # Check if content is empty and log warning
                content = msg.content or ""
                if not content:
                    logger.warning(f"LLM API returned empty content for model {model}")
                else:
                    logger.debug("LLM response content: %r", content[:3000])

                return content
            except RateLimitError:
                # For rate limit errors, use exponential backoff with longer delays
                # Start with 10 seconds and increase exponentially, capped at max
                delay = min(10 * (2**attempt), self.max_rate_limit_delay)
                logger.warning(f"Rate limit hit, retrying in {delay}s...")
                await asyncio.sleep(delay)
                continue
            except APITimeoutError:
                delay = self.retry_base_delay * (self.retry_backoff**attempt)
                logger.warning(f"API timeout, retrying in {delay}s...")
                await asyncio.sleep(delay)
                continue
            except APIError as e:
                if attempt < self.max_retries - 1:
                    delay = self.retry_base_delay * (self.retry_backoff**attempt)
                    logger.warning(f"API error: {e}, retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    raise LLMError(
                        f"LLM API error after {self.max_retries} attempts: {e}"
                    )
        raise LLMError("Max retries exceeded")

    async def chat_streaming(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> AsyncGenerator[str, None]:
        """Async streaming chat completion."""
        self._ensure_client()

        # Apply rate limiting before making API request
        await self.rate_limiter.acquire()

        try:
            stream = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    if on_token:
                        on_token(token)
                    yield token
        except APIError as e:
            raise LLMError(f"LLM streaming error: {e}")

    async def generate(
        self, model: str, prompt: str, temperature: float = 0.7, max_tokens: int = 4096
    ) -> str:
        """Async generate method."""
        return await self.chat(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful AI assistant."},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def count_tokens(self, text: str) -> int:
        return len(text) // 4
