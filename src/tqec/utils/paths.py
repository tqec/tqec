import os
from pathlib import Path
from typing import Final

from platformdirs import user_data_path

USER_DATA_PATH: Final[Path] = user_data_path(appname="TQEC")


# Get the detector database path.
# This path can be provided through the TQEC_DETECTOR_DATABASE_PATH environment variable, or it
# defaults to a user-controlled directory.
def _get_database_path() -> Path:
    if (env_db_path := os.getenv("TQEC_DETECTOR_DATABASE_PATH")) is not None:
        return Path(env_db_path)  # pragma: no cover
    else:
        return USER_DATA_PATH / "detector_database.pkl"


DEFAULT_DETECTOR_DATABASE_PATH: Final[Path] = _get_database_path()

PKG_DIR: Final[Path] = Path(__file__).parent.parent
GALLERY_DAE_DIR: Final[Path] = PKG_DIR / "gallery" / "dae"

# Create the directories that are used in case they do not exist.
_DIRECTORIES_TO_CREATE: Final[list[Path]] = [USER_DATA_PATH]
for directory in _DIRECTORIES_TO_CREATE:
    if not directory.exists():
        directory.mkdir(parents=True)
