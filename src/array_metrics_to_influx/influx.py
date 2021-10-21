# copyright: B1 Systems GmbH <info@b1-systems.de>, 2021
# license:   GPLv3+, http://www.gnu.org/licenses/gpl-3.0.html
# author:    Tilman Lüttje <luettje@b1-systems.de>

from __future__ import annotations

from enum import Enum, auto
from queue import Queue
from typing import TYPE_CHECKING, Dict, Optional, TypedDict, Union

from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBClientError, InfluxDBServerError
from requests.exceptions import ConnectionError
from structlog import getLogger

# prevents circular imports at runtime
if TYPE_CHECKING:
    from array_metrics_to_influx.config import InfluxDBConfig


class InfluxDataPoint(TypedDict):
    measurement: str
    tags: Dict[str, str]
    time: int
    fields: Dict[str, Union[int, float, str, bool]]


def create_influxdb_client(config: InfluxDBConfig) -> InfluxDBClient:
    return InfluxDBClient(
        host=config.host,
        port=config.port,
        ssl=config.ssl,
        username=config.user,
        password=config.password.get_secret_value(),
        database=config.database,
    )


class WriterThreadSignal(Enum):
    """
    Signals to send to the InfluxDB writer thread.
    """

    STOP = auto()


InfluxDataQueue = Queue[Union[list[InfluxDataPoint], WriterThreadSignal]]


def influxdb_writer(
    client: InfluxDBClient,
    queue: InfluxDataQueue,
    *,
    retention_policy: Optional[str] = None,
    measurement_prefix: Optional[str] = None,
    batch_size: Optional[int] = None,
) -> None:
    """
    Intended to be used as thread target to offload writing/sending the data
    points to the InfluxDB.

    Receives list of points to transfer via the passed queue instance.

    Communication such as the message to finish up is also done via the same
    queue.
    """
    logger = getLogger(thread="influxdb_writer", batch_size=batch_size or "unlimited")
    logger.info("InfluxDB write thread started")
    measurement_prefix = measurement_prefix or ""
    while True:
        item = queue.get()
        if isinstance(item, WriterThreadSignal):
            if item == WriterThreadSignal.STOP:
                logger.info("STOP signal received, stopping thread now.")
                queue.task_done()
                break
        elif not item:
            # list of data points might be empty if the collection interval is
            # set to a low value
            pass
        else:
            logger.debug(
                "Sending points to InfluxDB",
                no_of_points=len(item),
                measurement=item[0]["measurement"],
                retention_policy=retention_policy,
            )
            try:
                client.write_points(
                    item,
                    time_precision="ms",
                    retention_policy=retention_policy,
                    batch_size=batch_size,
                )
            # for now every item for which one of the exceptions below occurs
            # is lost
            except InfluxDBClientError:
                logger.exception("client_error")
            except InfluxDBServerError:
                logger.exception("server_error")
            except ConnectionError:
                logger.exception("connection_error")
            except Exception:
                logger.exception("unknown_exception")
        queue.task_done()
