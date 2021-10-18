"""
Contains all functions related to pure products and their python sdk "pypureclient".
"""

# copyright: B1 Systems GmbH <info@b1-systems.de>, 2021
# license:   GPLv3+, http://www.gnu.org/licenses/gpl-3.0.html
# author:    Tilman Lüttje <luettje@b1-systems.de>

from __future__ import annotations

from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING

from pypureclient.flasharray import Client

# this type annotation isn't necessarily correct but it's the version that i
# have been using in development.
# Feel free to bump it (by e.g. changing FA_2_7 to FA_2_8) to the version that
# you're using in development or the one that will be used in production.
from pypureclient.flasharray.FA_2_7.client import Client as FlasharrayClient

# prevents circular imports at runtime
if TYPE_CHECKING:

    from array_metrics_to_influx.config import FlasharrayConfig


def create_flasharray_client(config: FlasharrayConfig) -> FlasharrayClient:
    client: FlasharrayClient
    if config.private_key_file:
        client = Client(
            config.host,
            private_key_file=str(config.private_key_file),
            private_key_password=config.private_key_password.get_secret_value(),
            username=config.user,
            client_id=config.client_id,
            key_id=config.key_id,
            issuer=config.issuer,
        )
    else:
        with NamedTemporaryFile("w") as tmp_key_file:
            tmp_key_file.write(config.private_key.get_secret_value().strip())
            tmp_key_file.seek(0)
            client = Client(
                config.host,
                private_key_file=tmp_key_file.name,
                private_key_password=config.private_key_password.get_secret_value(),
                username=config.user,
                client_id=config.client_id,
                key_id=config.key_id,
                issuer=config.issuer,
            )
    return client


def get_volume_ids(client: FlasharrayClient) -> list[str]:
    return [item.id for item in client.get_volumes().items if not item.destroyed]


def get_volume_group_ids(client: FlasharrayClient) -> list[str]:
    return [item.id for item in client.get_volume_groups().items if not item.destroyed]
