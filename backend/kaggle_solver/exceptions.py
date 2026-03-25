"""Custom exceptions for the multi-agent system."""


class AgentError(Exception):
    """Base exception for agent errors."""
    pass


class LLMError(AgentError):
    """Raised when LLM communication fails."""
    pass


class ToolError(AgentError):
    """Raised when tool execution fails."""
    pass


class SandboxError(AgentError):
    """Base exception for sandbox errors."""
    pass


class PathTraversalError(SandboxError):
    """Raised when path traversal attempt is detected."""
    pass


class IsDirectoryError(SandboxError):
    """Raised when path is a directory but file operation expected."""
    pass


class CommandNotAllowedError(SandboxError):
    """Raised when command is not in allowed list."""
    pass


class SessionError(AgentError):
    """Base exception for session errors."""
    pass


class SessionNotFoundError(SessionError):
    """Raised when session is not found."""
    pass


class ConfigurationError(AgentError):
    """Raised when configuration is invalid."""
    pass
