class KaggleSolverError(Exception):
    """Base class for exceptions in this module."""
    pass

class StopExecutionError(KaggleSolverError):
    """Raised when execution should be stopped immediately."""
    pass
