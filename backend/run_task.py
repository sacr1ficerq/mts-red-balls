#!/usr/bin/env python3
"""
Console runner for Kaggle Solver tasks.
Runs tasks with full logging to console.
"""

import asyncio
import logging
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kaggle_solver.core.orchestrator import Orchestrator
from kaggle_solver.core.config import Config


def setup_logging():
    """Setup logging to output to console."""
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Create console handler with detailed format
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    
    # Detailed format for debugging
    formatter = logging.Formatter(
        '%(asctime)s | %(name)-30s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    
    root_logger.addHandler(console_handler)
    
    # Set specific log levels for noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.INFO)
    logging.getLogger("openai._base_client").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    return logging.getLogger(__name__)


async def run_task(query: str):
    """Run a task with the orchestrator."""
    logger = setup_logging()
    
    logger.info("=" * 60)
    logger.info("KAGGLE SOLVER CONSOLE RUNNER")
    logger.info("=" * 60)
    logger.info(f"Task: {query}")
    logger.info("=" * 60)
    
    # Load config
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    config = Config.load(config_path)
    
    # Create orchestrator
    orchestrator = Orchestrator(config)
    
    # Add event callback to print events
    def event_callback(event):
        event_type = event.get("type", "unknown")
        if event_type == "thought":
            logger.info(f"[THOUGHT] {event.get('content', '')[:200]}")
        elif event_type == "tool":
            logger.info(f"[TOOL] {event.get('tool', '')}: {event.get('input', '')[:100]}")
        elif event_type == "tool_result":
            result = event.get("result", "")
            if isinstance(result, str):
                result = result[:200]
            logger.info(f"[TOOL RESULT] {result}")
        elif event_type == "delegate":
            logger.info(f"[DELEGATE] {event.get('agent', '')}: {event.get('task', '')[:100]}")
        elif event_type == "plan":
            logger.info(f"[PLAN] {event.get('plan_id', '')}")
        elif event_type == "update_plan":
            logger.info(f"[UPDATE PLAN] {event.get('plan_id', '')}")
        elif event_type == "done":
            logger.info(f"[DONE] {event.get('result', '')[:200]}")
        elif event_type == "error":
            logger.error(f"[ERROR] {event.get('error', '')}")
    
    orchestrator.add_event_callback(event_callback)
    
    # Run the task
    try:
        session = await orchestrator.run(query)
        
        logger.info("=" * 60)
        logger.info("TASK COMPLETED")
        logger.info(f"Status: {session.status}")
        logger.info(f"Duration: {session.artifacts.get('total_time', 0):.2f}s")
        
        if session.status == "completed":
            result = session.artifacts.get("result", "")
            logger.info(f"Result: {result[:500] if result else 'None'}")
        else:
            error = session.artifacts.get("error", "Unknown error")
            logger.error(f"Error: {error}")
        
        logger.info("=" * 60)
        
        return session
    except Exception as e:
        logger.error(f"Failed to run task: {e}", exc_info=True)
        raise


def main():
    """Main entry point."""
    # Get query from command line - use as-is without adding Kaggle-specific prefix
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Help me with a task"
    
    # DEBUG MODE: Stop on first error to identify issues quickly
    DEBUG_STOP_ON_ERROR = False
    
    # Set environment variable so agents can check it
    if DEBUG_STOP_ON_ERROR:
        os.environ["DEBUG_STOP_ON_ERROR"] = "1"
    else:
        os.environ.pop("DEBUG_STOP_ON_ERROR", None)
    
    # Run async task with the user's query as-is
    asyncio.run(run_task(query))


if __name__ == "__main__":
    main()
