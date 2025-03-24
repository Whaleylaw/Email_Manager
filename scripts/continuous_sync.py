#!/usr/bin/env python3
import os
import time
import sys
import signal
import subprocess
from datetime import datetime

# Handle SIGTERM gracefully
def handle_sigterm(signum, frame):
    print("Received SIGTERM signal. Exiting...")
    sys.exit(0)

signal.signal(signal.SIGTERM, handle_sigterm)

# Script directory
script_dir = os.path.dirname(os.path.abspath(__file__))

def run_gmail_sync():
    """Run the Gmail sync script."""
    try:
        print(f"[{datetime.now().isoformat()}] Running Gmail sync...")
        
        # Run the script with Python
        result = subprocess.run(
            [sys.executable, os.path.join(script_dir, "gmail_sync.py")],
            capture_output=True,
            text=True
        )
        
        # Log output
        print(result.stdout)
        if result.stderr:
            print(f"Errors: {result.stderr}")
            
        print(f"[{datetime.now().isoformat()}] Gmail sync completed with exit code {result.returncode}")
        
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] Error running Gmail sync: {e}")

def main():
    # Interval in seconds (e.g., 15 minutes = 900 seconds)
    interval = 900
    
    print(f"Starting continuous sync with interval of {interval} seconds")
    print("Press Ctrl+C to exit")
    
    try:
        while True:
            run_gmail_sync()
            print(f"Waiting {interval} seconds until next sync...")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("Interrupted by user. Exiting...")
    except Exception as e:
        print(f"Error in continuous sync: {e}")

if __name__ == "__main__":
    main()