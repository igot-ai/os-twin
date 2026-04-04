import dotenv
from rich.console import Console

from deepagents_cli._version import __version__
from deepagents_cli.project_utils import (
    get_server_project_context as _get_server_project_context,
)

logger = logging.getLogger(__name__)


def _find_dotenv_from_start_path(start_path: Path) -> Path | None:
    """Find the nearest `.env` file from an explicit start path upward.

    Args:
        start_path: Directory to start searching from.

    Returns:
        Path to the nearest `.env` file, or `None` if not found.
    """
    current = start_path.expanduser().resolve()
    for parent in [current, *list(current.parents)]:
        candidate = parent / ".env"
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            logger.warning("Could not inspect .env candidate %s", candidate)
            return None
    return None


def _load_dotenv(*, start_path: Path | None = None, override: bool = False) -> bool:
    """Load environment variables, optionally anchored to an explicit path.

    Args:
