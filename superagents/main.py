#!/usr/bin/env python3
"""
Entry point for superagents framework
"""
import asyncio
import sys
import os

# Add the parent directory to path so we can import as a package
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def main():
    """Start the superagents orchestrator"""
    # Import here after path is set
    from orchestrator import SuperagentOrchestrator
    
    orchestrator = SuperagentOrchestrator()
    await orchestrator.run_scheduler_loop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutting down superagents...")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
