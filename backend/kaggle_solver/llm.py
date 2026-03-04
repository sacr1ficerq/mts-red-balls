import os
import time
import json
import logging
from typing import List, Dict, Optional, Callable, Generator

from openai import OpenAI, APIError, RateLimitError, APITimeoutError
from kaggle_solver import get_project_root

logger = logging.getLogger(__name__)

ENV_FILE = get_project_root() / ".env"
if ENV_FILE.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(ENV_FILE)
    except ImportError:
        pass


class LLMError(Exception):
    pass


class LLM:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning("No API key found for LLM. Using mock mode.")
            self.client = None
        else:
            self.client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=self.api_key)
        self.max_retries = 3
        self.retry_base_delay = 1.0
        self.mock_mode = self.client is None

    def chat(self, model: str, messages: List[Dict[str, str]], temperature: float = 0.7,
             max_tokens: int = 4096, tools: Optional[List[Dict]] = None,
             tool_choice: Optional[Dict] = None) -> str:
        if self.mock_mode:
            last_msg = messages[-1]["content"] if messages else ""
            return f'{{"action": "done", "result": "Mock response to: {last_msg[:100]}..."}}'
        
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=model, messages=messages, temperature=temperature,
                    max_tokens=max_tokens, tools=tools, tool_choice=tool_choice
                )
                msg = response.choices[0].message
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    content = msg.content or ""
                    if not content:
                        for tc in msg.tool_calls:
                            func = tc.function
                            tool_call_id = getattr(tc, 'id', None) or f"call_{func.name}"
                            if func.arguments:
                                try:
                                    args = json.loads(func.arguments)
                                    return json.dumps({"action": "tool", "tool": func.name, "tool_call_id": tool_call_id, **args})
                                except:
                                    return json.dumps({"action": "tool", "tool": func.name, "tool_call_id": tool_call_id, "query": func.arguments})
                    return content
                return msg.content or ""
            except RateLimitError:
                delay = self.retry_base_delay * (2 ** attempt)
                logger.warning(f"Rate limit hit, retrying in {delay}s...")
                time.sleep(delay)
                continue
            except APITimeoutError:
                delay = self.retry_base_delay * (2 ** attempt)
                logger.warning(f"API timeout, retrying in {delay}s...")
                time.sleep(delay)
                continue
            except APIError as e:
                if attempt < self.max_retries - 1:
                    delay = self.retry_base_delay * (2 ** attempt)
                    logger.warning(f"API error: {e}, retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    raise LLMError(f"LLM API error after {self.max_retries} attempts: {e}")
        raise LLMError("Max retries exceeded")

    def chat_streaming(self, model: str, messages: List[Dict[str, str]], temperature: float = 0.7,
                      max_tokens: int = 4096, on_token: Optional[Callable[[str], None]] = None) -> Generator[str, None, None]:
        try:
            stream = self.client.chat.completions.create(
                model=model, messages=messages, temperature=temperature,
                max_tokens=max_tokens, stream=True
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    if on_token:
                        on_token(token)
                    yield token
        except APIError as e:
            raise LLMError(f"LLM streaming error: {e}")

    def generate(self, model: str, prompt: str, temperature: float = 0.7, max_tokens: int = 4096) -> str:
        return self.chat(model=model, messages=[
            {"role": "system", "content": "You are a helpful AI assistant."},
            {"role": "user", "content": prompt}
        ], temperature=temperature, max_tokens=max_tokens)

    def count_tokens(self, text: str) -> int:
        return len(text) // 4
