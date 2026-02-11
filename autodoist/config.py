"""
Configuration management via environment variables and CLI arguments.

Environment variables (primary for K8s/Docker):
  TODOIST_API_KEY    - Todoist API key (required)
  AUTODOIST_LABEL    - Label name for next actions
  AUTODOIST_DELAY    - Delay between syncs in seconds
  AUTODOIST_P_SUFFIX - Parallel suffix character
  AUTODOIST_S_SUFFIX - Sequential suffix character  
  AUTODOIST_HIDE_FUTURE - Days to hide future tasks
  AUTODOIST_ONETIME  - Run once and exit (any value = true)
  AUTODOIST_DEBUG    - Enable debug logging (any value = true)
  AUTODOIST_DB_PATH  - Path to SQLite database
"""

from __future__ import annotations
import argparse
import logging
import os
import sys
from dataclasses import dataclass
from typing import Optional, Sequence


@dataclass(frozen=True)
class Config:
    """Runtime configuration for Autodoist."""
    
    api_key: str
    label: Optional[str] = None
    delay: int = 5
    p_suffix: str = "="
    s_suffix: str = "-"
    hide_future: int = 0
    onetime: bool = False
    debug: bool = False
    inbox: Optional[str] = None  # 'parallel', 'sequential', or None
    db_path: str = "metadata.sqlite"
    
    def __post_init__(self) -> None:
        if not self.api_key:
            raise ValueError("API key is required")
    
    @classmethod
    def from_env_and_cli(cls, argv: Optional[Sequence[str]] = None) -> "Config":
        """
        Build config from environment variables with CLI overrides.
        
        Environment variables provide defaults, CLI arguments override them.
        """
        # Parse CLI arguments
        parser = _create_parser()
        args = parser.parse_args(argv)
        
        # Build config with CLI taking precedence over env vars
        api_key = args.api_key or os.environ.get('TODOIST_API_KEY', '')
        
        if not api_key:
            logging.error(
                "\n\nNo API key set. Run with '-a <YOUR_API_KEY>' or "
                "set the environment variable TODOIST_API_KEY.\n"
            )
            sys.exit(1)
        
        return cls(
            api_key=api_key,
            label=args.label or os.environ.get('AUTODOIST_LABEL'),
            delay=args.delay if args.delay != 5 else int(os.environ.get('AUTODOIST_DELAY', '5')),
            p_suffix=args.p_suffix if args.p_suffix != '=' else os.environ.get('AUTODOIST_P_SUFFIX', '='),
            s_suffix=args.s_suffix if args.s_suffix != '-' else os.environ.get('AUTODOIST_S_SUFFIX', '-'),
            hide_future=args.hide_future if args.hide_future != 0 else int(os.environ.get('AUTODOIST_HIDE_FUTURE', '0')),
            onetime=args.onetime or bool(os.environ.get('AUTODOIST_ONETIME')),
            debug=args.debug or bool(os.environ.get('AUTODOIST_DEBUG')),
            inbox=args.inbox,
            db_path=os.environ.get('AUTODOIST_DB_PATH', 'metadata.sqlite'),
        )


def _make_wide(formatter, w: int = 120, h: int = 36):
    """Return a wider HelpFormatter, if possible."""
    try:
        kwargs = {'width': w, 'max_help_position': h}
        formatter(None, **kwargs)
        return lambda prog: formatter(prog, **kwargs)
    except TypeError:
        return formatter


def _create_parser() -> argparse.ArgumentParser:
    """Create argument parser with all supported options."""
    parser = argparse.ArgumentParser(
        prog='autodoist',
        description='GTD automation for Todoist - automatic next action labeling',
        formatter_class=_make_wide(argparse.HelpFormatter, w=120, h=60)
    )
    
    parser.add_argument(
        '-a', '--api_key',
        help='Todoist API Key (or set TODOIST_API_KEY env var)',
        default=None,
        type=str
    )
    parser.add_argument(
        '-l', '--label',
        help='Enable next action labelling with this label name',
        type=str
    )
    parser.add_argument(
        '-d', '--delay',
        help='Delay in seconds between syncs (default: 5)',
        default=5,
        type=int
    )
    parser.add_argument(
        '-p', '--p_suffix',
        help='Suffix for parallel labeling (default: "=")',
        default='='
    )
    parser.add_argument(
        '-s', '--s_suffix',
        help='Suffix for sequential labeling (default: "-")',
        default='-'
    )
    parser.add_argument(
        '-hf', '--hide_future',
        help='Hide tasks with due dates beyond this many days',
        default=0,
        type=int
    )
    parser.add_argument(
        '--onetime',
        help='Run once and exit',
        action='store_true'
    )
    parser.add_argument(
        '--debug',
        help='Enable debug logging',
        action='store_true'
    )
    parser.add_argument(
        '--inbox',
        help='How to process the Inbox project',
        default=None,
        choices=['parallel', 'sequential']
    )
    
    return parser


def setup_logging(debug: bool = False) -> None:
    """
    Configure logging for Autodoist.
    
    Args:
        debug: If True, set level to DEBUG and include more detail
    """
    level = logging.DEBUG if debug else logging.INFO
    
    # Configure format
    fmt = '%(asctime)s %(levelname)-8s %(message)s'
    datefmt = '%Y-%m-%d %H:%M:%S'
    
    # Always log to stderr; debug also goes to file
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    
    if debug:
        # Add file handler for debug mode
        try:
            handlers.append(logging.FileHandler('autodoist_debug.log', 'w+', 'utf-8'))
        except (OSError, IOError):
            pass  # Skip file handler if we can't create it
    
    logging.basicConfig(
        level=level,
        format=fmt,
        datefmt=datefmt,
        handlers=handlers
    )
