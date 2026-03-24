#!/usr/bin/env python3
import asyncio
import sys
import os
import logging
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from kaggle_solver.core.orchestrator import Orchestrator
from kaggle_solver.core.config import Config
from kaggle_solver.exceptions import StopExecutionError

# Configure logging to console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

async def main():
    print("=" * 60)
    print("REAL SYSTEM RUN: TITANIC COMPETITION (STOP ON ERROR)")
    print("=" * 60)
    
    # Initialize orchestrator
    config = Config.load()
    orch = Orchestrator(config)
    
    # Define a callback that raises an exception on error
    def stop_on_error(event):
        etype = event.get('type')
        data = event.get('data', {})
        if etype == 'error' or (etype == 'tool' and not data.get('success', True)):
            print(f"\n[!!!] STOPPING ON ERROR: {event}\n")
            # We use StopExecutionError to stop the run
            raise StopExecutionError(f"System error detected: {data.get('error', 'Unknown error')}")

    orch.add_event_callback(stop_on_error)
    
    # Define the task
    query = "Participate in the Titanic competition on Kaggle. Download data, preprocess, train a model, and submit predictions."
    
    print(f"\n[TASK] {query}\n")
    
    # Run the task
    try:
        session = await orch.run(query)
        print(f"\n✓ Run completed with status: {session.status}")
    except Exception as e:
        print(f"\n[TERMINATED] Run stopped due to error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
