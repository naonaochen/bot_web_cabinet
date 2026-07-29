from __future__ import annotations

"""
RPA Test - Graphical User Interface

Launch the RPA Control Form with interactive controls.

Usage:
    python gui.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from gui_app import App


def main():
    """Main entry point for GUI execution."""
    print("Starting RPA Control Form...")
    print("The application window will appear shortly.")
    
    try:
        app = App()
        app.mainloop()
    except KeyboardInterrupt:
        print("\nApplication interrupted by user (Ctrl+C)")
        sys.exit(130)
    except Exception as e:
        print(f"\nError starting application: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
