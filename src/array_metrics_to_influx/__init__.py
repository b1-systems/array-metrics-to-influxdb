# copyright: B1 Systems GmbH <info@b1-systems.de>, 2021
# license:   GPLv3+, http://www.gnu.org/licenses/gpl-3.0.html
# author:    Tilman Lüttje <luettje@b1-systems.de>

# initialize all collector classes for registration
from importlib.metadata import PackageNotFoundError, version

from .collector import *  # noqa: F401, F403

try:
    __version__ = version(__name__)
except PackageNotFoundError:
    __version__ = "unknown"


__author__ = "B1 Systems GmbH <info@b1-systems.de>"
__license__ = "GPLv3"
