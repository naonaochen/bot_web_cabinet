from __future__ import annotations

"""
RPA Test - Command Line Interface

Usage:
    python main.py                                    # Run full automation flow
    python main.py --config config/settings.yaml      # Use custom config
    python main.py --no-south-comm                    # Skip south communication step
    python main.py --close-browser                    # Close browser after completion
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from tasks.flow_task import run_flow
from core.utils import load_config, check_url_reachable


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="RPA Test - Automated Equipment Configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                                    # Run with default config
  python main.py --config custom.yaml               # Use custom config file
  python main.py --no-south-comm                    # Skip south communication
  python main.py --close-browser                    # Auto-close browser when done
  python main.py --no-network-check                 # Skip network precheck
        """
    )
    
    parser.add_argument(
        "--config",
        type=str,
        default="config/settings.yaml",
        help="Path to configuration file (default: config/settings.yaml)"
    )
    
    parser.add_argument(
        "--no-south-comm",
        action="store_true",
        help="Skip south communication configuration step"
    )
    
    parser.add_argument(
        "--close-browser",
        action="store_true",
        help="Close browser automatically after completion"
    )
    
    parser.add_argument(
        "--no-network-check",
        action="store_true",
        help="Skip network connectivity precheck"
    )
    
    parser.add_argument(
        "--upload-files",
        nargs="+",
        type=str,
        default=None,
        help="Override upload files from config (space-separated paths)"
    )
    
    parser.add_argument(
        "--apply-target",
        type=str,
        default=None,
        help="Override apply target file from config"
    )
    
    return parser.parse_args()


def main():
    """Main entry point for command line execution."""
    args = parse_arguments()
    
    print("=" * 60)
    print("RPA Test - Command Line Automation")
    print("=" * 60)
    
    # Load and validate configuration
    try:
        print(f"\nLoading configuration from: {args.config}")
        config = load_config(args.config)
        print("✓ Configuration loaded successfully")
    except Exception as e:
        print(f"✗ Failed to load configuration: {e}")
        sys.exit(1)
    
    # Network precheck
    if not args.no_network_check:
        app_url = config["app"]["url"]
        print(f"\nChecking network connectivity to: {app_url}")
        reachable, reason = check_url_reachable(app_url)
        
        if reachable:
            print(f"✓ Network check passed: {reason}")
        else:
            print(f"✗ Network check failed: {reason}")
            response = input("\nContinue anyway? (y/n): ").strip().lower()
            if response != 'y':
                print("Aborted by user.")
                sys.exit(0)
    
    # Display execution plan
    print("\n" + "=" * 60)
    print("Execution Plan:")
    print("=" * 60)
    
    upload_files = args.upload_files or config.get("flow", {}).get("upload_files", [])
    apply_target = args.apply_target or config.get("flow", {}).get("apply_target_file")
    include_south_comm = not args.no_south_comm
    
    print(f"  Upload Files:     {len(upload_files)} file(s)")
    for f in upload_files:
        print(f"    - {f}")
    
    print(f"  Apply Target:     {apply_target or 'None'}")
    print(f"  South Comm:       {'Enabled' if include_south_comm else 'Disabled'}")
    print(f"  Close Browser:    {'Yes' if args.close_browser else 'No (keep open)'}")
    print("=" * 60)
    
    # Show captcha instruction but don't wait for confirmation
    print("\n" + "=" * 60)
    print("IMPORTANT: Browser will open and you need to:")
    print("  1. Enter captcha code manually")
    print("  2. Click Login button")
    print("  3. Then automation continues automatically")
    print("=" * 60)
    print("\nStarting automation in 3 seconds...")
    import time
    time.sleep(3)
    
    # Execute automation flow
    print("\n" + "=" * 60)
    print("Starting Automation Flow...")
    print("=" * 60 + "\n")
    
    try:
        run_flow(
            *upload_files,
            apply_target_file=apply_target,
            config_path=args.config,
            report_path="logs/execution_report.json",
            include_south_communication=include_south_comm,
            precheck_network=False,  # Already checked above
            close_browser_at_end=args.close_browser,
            pause_at_end=not args.close_browser,
        )
        
        print("\n" + "=" * 60)
        print("✓ Automation completed successfully!")
        print("=" * 60)
        print(f"\nReport saved to: logs/execution_report.json")
        print(f"Screenshots: screenshots/")
        print(f"Traces: traces/")
        
    except KeyboardInterrupt:
        print("\n\n⚠ Automation interrupted by user (Ctrl+C)")
        sys.exit(130)
        
    except Exception as e:
        print("\n" + "=" * 60)
        print("✗ Automation failed!")
        print("=" * 60)
        print(f"\nError: {e}")
        print(f"\nCheck logs for details:")
        print(f"  - logs/rpa.log")
        print(f"  - logs/execution_report.json")
        print(f"  - screenshots/error_state_*.png")
        print(f"  - traces/trace_*.zip")
        sys.exit(1)


if __name__ == "__main__":
    main()
