from pathlib import Path
from platformdirs import user_data_path
from typing import Final

USER_DATA_PATH: Final[Path] = user_data_path(appname="TQEC")
DEFAULT_DETECTOR_DATABASE_PATH: Final[Path] = USER_DATA_PATH / "detector_database.pkl"

# Create the directories that are used in case they do not exist.
_DIRECTORIES_TO_CREATE: Final[list[Path]] = [USER_DATA_PATH]
for directory in _DIRECTORIES_TO_CREATE:
    if not directory.exists():
        directory.mkdir(parents=False)
