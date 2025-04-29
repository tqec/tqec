from pathlib import Path
from platformdirs import user_data_path
from typing import Final

DEFAULT_DETECTOR_DATABASE_PATH: Final[Path] = (
    # Note the use of the "*_path" variant that returns directly a Path instance.
    # Operator "/" is overloaded by the Path class to be the correct path separator depending on the OS,
    # so the below line should be a valid path independently of the OS.
    user_data_path(appname="TQEC") / "my_detector_database.pkl"
)
