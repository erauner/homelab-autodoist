"""
Autodoist entry point.

Run with: python -m autodoist [options]
"""

from __future__ import annotations
import logging
import sys
import time
from typing import Optional, Sequence

from .config import Config, setup_logging
from .db import open_db
from .api import TodoistClient
from .labeling import run_labeling_pass


def main(argv: Optional[Sequence[str]] = None) -> int:
    """
    Main entry point for Autodoist.
    
    Args:
        argv: Command line arguments (defaults to sys.argv)
        
    Returns:
        Exit code (0 for success)
    """
    # Parse configuration
    try:
        config = Config.from_env_and_cli(argv)
    except SystemExit:
        return 1
    except Exception as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1
    
    # Set up logging
    setup_logging(config.debug)
    
    # Log enabled modes
    modes = []
    if config.label:
        modes.append("Next action labelling: Enabled")
    else:
        modes.append("Next action labelling: Disabled")
    if config.doing_now_label:
        modes.append(f"Doing-now singleton: Enabled ({config.doing_now_label})")
    else:
        modes.append("Doing-now singleton: Disabled")
    
    logging.info("Running with the following configuration:\n  %s", "\n  ".join(modes))
    
    if not config.label and not config.doing_now_label:
        logging.info("No functionality enabled. Use -l <LABEL> and/or --doing-now-label <LABEL>.")
        return 0
    
    # Initialize API client
    logging.debug("Connecting to Todoist API...")
    try:
        client = TodoistClient(config.api_key)
        client.initial_sync()
    except Exception as e:
        logging.error("Could not connect to Todoist: %s", e)
        return 1
    
    # Ensure required labels exist
    labels_to_ensure = {x for x in (config.label, config.doing_now_label) if x}
    for label_name in labels_to_ensure:
        try:
            client.ensure_label_exists(label_name)
        except Exception as e:
            logging.error("Could not create label '%s': %s", label_name, e)
            return 1
    
    # Initialize database
    try:
        db = open_db(config.db_path)
    except Exception as e:
        logging.error("Could not initialize database: %s", e)
        return 1
    
    logging.info("SQLite DB initialized at: %s", config.db_path)
    
    # Main loop
    try:
        while True:
            start_time = time.time()
            
            # Run labeling pass
            label_changes = run_labeling_pass(client, db, config)

            # Flush queued changes
            if client.pending_changes > 0:
                try:
                    num_changes = client.flush_queue()
                    logging.info(
                        "%d change%s committed to Todoist (%d label update%s).",
                        num_changes, "" if num_changes == 1 else "s",
                        label_changes, "" if label_changes == 1 else "s"
                    )
                except Exception as e:
                    logging.error("Error syncing changes: %s", e)
            else:
                logging.debug("No changes in queue, skipping sync.")
            
            # Exit if one-time mode
            if config.onetime:
                break
            
            # Calculate sleep time
            elapsed = time.time() - start_time
            sleep_time = max(0, config.delay - elapsed)
            
            if sleep_time > 0:
                logging.debug("Sleeping for %.1f seconds", sleep_time)
                time.sleep(sleep_time)
            else:
                logging.debug(
                    "Computation time %.1fs exceeded delay %ds, skipping sleep",
                    elapsed, config.delay
                )
    
    except KeyboardInterrupt:
        logging.info("\nInterrupted by user")
    finally:
        db.close()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
