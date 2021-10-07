# copyright: B1 Systems GmbH <info@b1-systems.de>, 2021
# license:   GPLv3+, http://www.gnu.org/licenses/gpl-3.0.html
# author:    Tilman Lüttje <luettje@b1-systems.de>

from pypureclient.responses import ErrorResponse


class PureErrorResponse(Exception):
    "Raised if a collect method returns an `ErrorResponse`"

    def __init__(self, response: ErrorResponse) -> None:
        self.response = response
        super().__init__()
