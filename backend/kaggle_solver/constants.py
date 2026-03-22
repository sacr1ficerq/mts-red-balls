"""
Centralized constants for the multi-agent system.

This module contains all configuration constants to eliminate hardcoding
and improve maintainability.
"""

from enum import Enum


class AgentType(str, Enum):
    """Agent type enumeration."""
    COORDINATOR = "Coordinator"
    CODE = "CodeAgent"
    SEARCH = "SearchAgent"
    CRITIC = "CriticAgent"


class ToolType(str, Enum):
    """Tool type enumeration."""
    CONSOLE = "console"
    FILES = "files"
    SEARCH = "search"
    RAG = "rag"


class AgentAction(str, Enum):
    """Agent action types."""
    TOOL = "tool"
    DELEGATE = "delegate"
    DONE = "done"
    PLAN = "plan"
    UPDATE_PLAN = "update_plan"
    OPTIONS = "options"
    ERROR = "error"


class AgentConstants:
    """Agent behavior constants.
    
    These values control agent behavior and limits.
    """
    
    # Maximum number of context events to subscribe to
    # Prevents context window overflow while maintaining relevance
    MAX_CONTEXT_EVENTS = 10
    
    # Maximum consecutive plan actions before forcing delegation
    # Prevents infinite planning loops
    MAX_CONSECUTIVE_PLANS = 2
    
    # Maximum tokens for LLM output
    # Based on model limits and response quality tradeoff
    MAX_OUTPUT_TOKENS = 8192
    
    # Approximate tokens per character (rough estimate)
    # Used for token counting when exact tokenizer unavailable
    CHARS_PER_TOKEN = 4
    
    # Maximum iterations for agent execution
    MAX_ITERATIONS = 10
    
    # Agent to tools mapping for sub-agent creation
    AGENT_TOOLS = {
        AgentType.SEARCH.value: ["search"],
        AgentType.CODE.value: ["console", "files"],
        AgentType.CRITIC.value: ["message"],
        AgentType.COORDINATOR.value: ["delegate", "tool"],
    }
    
    # Agent to prompt file mapping
    AGENT_PROMPTS = {
        AgentType.COORDINATOR.value: "prompts/coordinator.yaml",
        AgentType.CODE.value: "prompts/code.yaml",
        AgentType.SEARCH.value: "prompts/search.yaml",
        AgentType.CRITIC.value: "prompts/critic.yaml",
    }
    
    # Tools schema for function calling
    TOOLS_SCHEMA = {
        "console": {
            "type": "function",
            "function": {
                "name": "console",
                "description": "Run shell commands in sandbox",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Command to run"}
                    },
                    "required": ["query"]
                }
            }
        },
        "files": {
            "type": "function",
            "function": {
                "name": "files",
                "description": "File operations: read, write, edit",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "op": {"type": "string", "enum": ["read", "write", "edit"]},
                        "path": {"type": "string"},
                        "content": {"type": "string"}
                    },
                    "required": ["op", "path"]
                }
            }
        },
        "search": {
            "type": "function",
            "function": {
                "name": "search",
                "description": "Web search",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"}
                    },
                    "required": ["query"]
                }
            }
        }
    }


class SandboxConstants:
    """Sandbox execution constants."""
    
    # Size constants (in bytes)
    ONE_KB = 1024
    ONE_MB = 1024 * 1024
    ONE_GB = 1024 * 1024 * 1024
    
    # Allowed commands for execution
    ALLOWED_COMMANDS = {"python", "python3", "pip", "ls", "cat", "head", "mkdir", "rm", "cp", "mv", "echo", "date"}
    
    # Blocked shell patterns
    BLOCKED_PATTERNS = [
        "&&", "||", ";", "|", "&", ">", ">>", "<", "`", "$(", "$(",
        "wget", "curl", "nc", "netcat", "telnet", "ssh", "ftp",
        "chmod", "chown", "su", "sudo", "eval", "exec",
    ]
    
    # Maximum file size for reading (in bytes)
    MAX_FILE_SIZE = 10 * ONE_MB  # 10 MB
    
    # Maximum file size for writing (in bytes)
    MAX_WRITE_FILE_SIZE = 100 * ONE_MB  # 100 MB
    
    # Maximum command output size (in bytes)
    MAX_OUTPUT_SIZE = ONE_MB  # 1 MB
    
    # Command execution timeout (in seconds)
    COMMAND_TIMEOUT = 60
    
    # Preinstall timeout (in seconds)
    PREINSTALL_TIMEOUT = 180


class ServerConstants:
    """Server configuration constants."""
    
    # Default host and port
    DEFAULT_HOST = "0.0.0.0"
    DEFAULT_PORT = 8000
    
    # Rate limiting
    RATE_LIMIT_REQUESTS = 100
    RATE_LIMIT_PERIOD = 60  # seconds
    
    # CORS settings (should be overridden in production)
    CORS_ORIGINS = ["*"]
    
    # Session management
    MAX_SESSIONS = 1000
    SESSION_TIMEOUT = 3600  # 1 hour
    
    # Event storage
    MAX_EVENTS_IN_MEMORY = 1000
    MAX_EVENTS_PER_SESSION = 100


class LLMConstants:
    """LLM configuration constants."""
    
    # Default model
    DEFAULT_MODEL = "minimax/minimax-m2.7"
    
    # Retry configuration
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0  # seconds
    RETRY_BACKOFF = 2.0  # exponential backoff multiplier
    
    # Temperature settings
    DEFAULT_TEMPERATURE = 0.7
    MAX_TEMPERATURE = 1.0
    MIN_TEMPERATURE = 0.0
    
    # Token limits
    MAX_TOKENS = 8192
    MIN_TOKENS = 1


class ToolConstants:
    """Tool execution constants."""
    
    # Tool names
    TOOL_CONSOLE = ToolType.CONSOLE.value
    TOOL_FILES = ToolType.FILES.value
    TOOL_SEARCH = ToolType.SEARCH.value
    TOOL_RAG = ToolType.RAG.value
    
    # Tools requiring LLM
    TOOLS_REQUIRING_LLM = {TOOL_SEARCH, TOOL_RAG}
    
    # Tools requiring sandbox
    TOOLS_REQUIRING_SANDBOX = {TOOL_CONSOLE, TOOL_FILES}
    
    # Maximum tool execution time (in seconds)
    MAX_TOOL_EXECUTION_TIME = 120
    
    # Maximum tool calls per session
    MAX_TOOL_CALLS_PER_SESSION = 100
    
    # Tool result size limit (in characters)
    MAX_TOOL_RESULT_SIZE = 100000


class StateConstants:
    """State management constants."""
    
    # Session data directory
    SESSIONS_DIR = "data"
    SESSIONS_FILE = "sessions.json"
    EVENTS_FILE = "events.json"
    
    # Auto-save interval (in seconds)
    AUTO_SAVE_INTERVAL = 30
    
    # Maximum sessions to keep in memory
    MAX_IN_MEMORY_SESSIONS = 100
    
    # Event storage limits
    MAX_EVENTS_IN_MEMORY = 1000
    MAX_EVENTS_PER_SESSION = 100
    MAX_MESSAGES = 500


class LoggingConstants:
    """Logging configuration constants."""
    
    # Log levels
    LOG_LEVEL = "INFO"
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Log file paths
    LOG_DIR = "logs"
    SERVER_LOG_FILE = "server.log"
    AGENT_LOG_FILE = "agent.log"
    ERROR_LOG_FILE = "error.log"
