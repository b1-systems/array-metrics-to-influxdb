"""
Retrieve selected metrics from one or multiple Pure FlashArray instances and
write them to a InfluxDB. Different collectors are responsible for
different kind of data. They are written to the same database but with
different 'measurement' fields.
"""

# copyright: B1 Systems GmbH <info@b1-systems.de>, 2021
# license:   GPLv3+, http://www.gnu.org/licenses/gpl-3.0.html
# author:    Tilman Lüttje <luettje@b1-systems.de>

import logging
from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser, FileType
from datetime import datetime
from os import getenv, path
from pathlib import Path
from queue import Queue
from signal import SIGINT, SIGTERM, signal, strsignal
from sys import exit, stderr
from threading import Thread
from time import sleep, time
from types import FrameType
from typing import Final, Optional, TextIO, TypedDict, Union, cast

import structlog
from pydantic import ValidationError
from requests.exceptions import ConnectionError
from tomli import loads

from array_metrics_to_influx import __author__, __license__, __version__
from array_metrics_to_influx.collector_base import COLLECTORS_BY_MEASUREMENT_NAME
from array_metrics_to_influx.config import CollectorConfig, Config, FlasharrayConfig
from array_metrics_to_influx.errors import PureErrorResponse
from array_metrics_to_influx.influx import (
    InfluxDataQueue,
    WriterThreadSignal,
    create_influxdb_client,
    influxdb_writer,
)
from array_metrics_to_influx.pure import create_flasharray_client

# Once set to true the program will send the remaining points to the InfluxDB
# and exit afterwards
SHOULD_STOP = False
# Duration of sleep intervals of the collector threads
SLEEP_INTERVAL: Final[int] = 5


def ms_timestamp_or_iso_8601(value: str) -> int:

    if value.isdigit():
        return int(value)
    else:
        return int(datetime.fromisoformat(value).timestamp() * 1000)


class CommandLineArguments(TypedDict):
    "Helper class to type parsed command line arguments"
    log_level: Union[int, str]
    config: TextIO
    validate_config: bool
    json_log: bool
    retention_policy: Optional[str]
    initial_start_time: Optional[int]


def main(argv: Optional[list[str]] = None) -> int:

    xdg_config_home_str = getenv("XDG_CONFIG_HOME")
    if xdg_config_home_str and path.isabs(xdg_config_home_str):
        xdg_config_home = Path(xdg_config_home_str)
    else:
        xdg_config_home = Path.home() / ".config"

    parser = ArgumentParser(
        description=__doc__,
        formatter_class=ArgumentDefaultsHelpFormatter,
        epilog=f"v{__version__}, {__license__} @ {__author__}",
    )
    parser.set_defaults(log_level="INFO")
    verbosity_args = parser.add_mutually_exclusive_group()
    verbosity_args.add_argument(
        "-s",
        "--silent",
        action="store_const",
        dest="log_level",
        const=logging.WARNING,
        help="Switch to WARNING log level.",
    )
    verbosity_args.add_argument(
        "-d",
        "--debug",
        action="store_const",
        dest="log_level",
        const=logging.DEBUG,
        help="""Switch to DEBUG log level.""",
    )

    parser.add_argument(
        "-c",
        "--config",
        help="Configuration file to use. Default value honors $XDG_CONFIG_HOME.",
        type=FileType("r"),
        default=str(xdg_config_home / "array_metrics_to_influxdb.conf"),
    )
    parser.add_argument(
        "-v",
        "--validate-config",
        action="store_true",
        help="Only validate the structure (not the content) of the configuration file.",
    )
    parser.add_argument(
        "-j",
        "--json-log",
        action="store_true",
        help="Output log messages as single line JSON instead of plain text.",
    )
    parser.add_argument(
        "-r",
        "--retention-policy",
        help="""Existing retention policy to specify for all InfluxDB writes.
        Overrides the value from the config file.""",
        default=None,
    )
    parser.add_argument(
        "-i",
        "--initial-start-time",
        type=ms_timestamp_or_iso_8601,
        help="""Datetime to use for the first collection round. Defaults to one
        interval before the current time. Can be specified as UNIX timestamp in
        *milliseconds* or as ISO-8601 formatted string, e.g.
        2021-08-01[T00[:05[:23[.541[000]]]]] Should not be older than one year which is the
        maximum retention policy of pure product's performance metrics. Might
        be helpful if this application crashed and you want to collect the
        missing data from the downtime. Depending on the requested range the
        used resolution for the data might have to be increased. This happens
        dynamically if necessary.""",
    )

    args = cast(CommandLineArguments, vars(parser.parse_args(argv)))

    structlog_processors = [
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.format_exc_info,
        structlog.processors.TimeStamper("%Y-%m-%d %H:%M:%S"),
    ]
    if args["json_log"]:
        structlog_processors.append(structlog.processors.JSONRenderer(sort_keys=True))
    else:
        # we do not want any ANSI color codes inside our JSON messages
        structlog_processors.append(
            structlog.dev.ConsoleRenderer(),
        )
    structlog.configure(
        processors=structlog_processors,  # type: ignore
        # filter messages according to passed log_level (-s/-d)
        wrapper_class=structlog.make_filtering_bound_logger(
            # default value is the string "INFO" (since it is shown as default
            # inside the help-message) not the equivalent level
            args["log_level"]
            if isinstance(args["log_level"], int)
            else logging.INFO
        ),
    )

    logger = structlog.get_logger(thread="main")
    try:
        config = Config.parse_obj(loads(args["config"].read()))
    except ValidationError as exc:
        print(exc)
        return 1
    if args["validate_config"]:
        print("Config is structurally valid")
        return 0
    logger.debug("Running with arguments", **(args))
    logger.info("Running with config", **config.dict())

    influxdb_client = create_influxdb_client(config.influxdb)
    try:
        influxdb_version = influxdb_client.ping()
        logger.info(
            "Created InfluxDBClient and connected to InfluxDB",
            influxdb_version=influxdb_version,
        )
    except (ConnectionRefusedError, ConnectionError):
        logger.error(
            "Could not connect to InfluxDB, exiting.", influxdb=config.influxdb.host
        )
        return 1

    data_points_queue: InfluxDataQueue = Queue()

    influxdb_writer_thread = Thread(
        target=influxdb_writer,
        name="influxdb_writer",
        args=(influxdb_client, data_points_queue),
        kwargs=dict(
            retention_policy=args["retention_policy"]
            or config.influxdb.retention_policy,
            measurement_prefix=config.influxdb.measurement_prefix,
        ),
    )
    influxdb_writer_thread.start()

    collector_threads: list[Thread] = []

    # inner function allows easy access to our queue object
    def exit_handler(signum: int, _: Optional[FrameType]) -> None:
        global SHOULD_STOP
        logger.info("Received signal", signal=strsignal(signum))
        if signum in {SIGTERM, SIGINT}:
            # if we received the signal already once exit forcefully
            if SHOULD_STOP:
                logger.warning(
                    "Force-exiting, not all remaining data might have been transferred."
                )
                exit(1)
            SHOULD_STOP = True
            print("Sent the same signal again to exit forcefully.", file=stderr)
            logger.info("Stopping all collector threads.")
            for thread in collector_threads:
                # the threads honor `SHOULD_STOP` and will therefore stop once
                # it's been toggled
                thread.join()
            logger.info(
                "Sending remaining data points to InfluxDB.",
                remaining=data_points_queue.qsize(),
            )
            # finish all current entries inside the queue
            data_points_queue.join()
            # we cannot use `SHOULD_STOP` for the writer thread since it has to
            # continue working after the collector threads have already stopped
            data_points_queue.put(WriterThreadSignal.STOP)
            logger.info("Waiting for InfluxDBWriter thread to stop.")
            influxdb_writer_thread.join()

    signal(SIGTERM, exit_handler)
    signal(SIGINT, exit_handler)

    for flasharray_config in config.array:
        host_tag = flasharray_config.name or flasharray_config.host
        if flasharray_config.disable:
            logger.warning("disabled_array", host=host_tag)
            continue
        t = Thread(
            target=collect_thread,
            name=f"metrics_collector-{host_tag}",
            args=(
                flasharray_config,
                data_points_queue,
                config.collector,
            ),
            kwargs=dict(initial_start_time=args["initial_start_time"]),
        )
        t.start()
        collector_threads.append(t)
    logger.info("Started collector threads", number_of_threads=len(collector_threads))
    return 0


def collect_thread(
    config: FlasharrayConfig,
    queue: InfluxDataQueue,
    collectors_config: dict[str, CollectorConfig],
    *,
    initial_start_time: Optional[int],
) -> None:
    """Continuously collects the configured metrics from a FlashArray and puts
    them into the queue for the influxdb_writer_thread.

    Expected to be used as thread target which will finish once `SHOULD_STOP`
    is set to True.
    """
    host_tag = config.name or config.host
    logger = structlog.get_logger(thread=f"metrics_collector-{host_tag}", host=host_tag)
    fa_client = create_flasharray_client(config)
    logger.info(
        "Created FlasharrayClient", rest_api_version=fa_client.get_rest_version()
    )

    collectors = []
    for measurement in config.collectors:
        resolution: Optional[int] = None
        if collector_config := collectors_config.get(measurement):
            resolution = collector_config.resolution
        collector = COLLECTORS_BY_MEASUREMENT_NAME[measurement](
            host_tag=host_tag,
            fa_client=fa_client,
            min_resolution=resolution,
        )
        collectors.append(collector)

    # During the first run, how far should we look back
    end_time_ms = initial_start_time or ((int(time()) - config.metrics_interval) * 1000)
    while not SHOULD_STOP:
        start_time_ms = int(time() * 1000)
        logger = logger.bind(start_time=end_time_ms)
        for collector in collectors:
            try:
                influx_data_points = list(collector.influx_data(start_time=end_time_ms))
                logger.debug(
                    "Collected data points",
                    measurement=collector.measurement,
                    number_of_points=len(influx_data_points),
                )

            except PureErrorResponse as exc:
                logger.exception(
                    "collector_exception",
                    errors=exc.response.errors,
                    response_headers=exc.response.headers,
                )
                continue
            except Exception:
                logger.exception("unhandled_exception")
                continue
            queue.put(influx_data_points)
        end_time_ms = int(time() * 1000)
        duration_ms = end_time_ms - start_time_ms
        sleep_time = config.metrics_interval - (duration_ms / 1000)
        logger.debug(
            "Collected all metrics",
            seconds=round(duration_ms / 1000, 2),
            seconds_until_next_run=round(sleep_time, 2),
        )
        if sleep_time < 0:
            logger.warning(
                "Collecting took longer than configured interval",
                duration=round(duration_ms / 1000, 2),
                interval=config.metrics_interval,
            )
            continue
        # Break down sleep time into smaller parts to allow a quick program
        # exit if requested
        # Without it the exit of the program might take as long as
        # `config.metrics_interval`
        if sleep_time <= 5:
            sleep(sleep_time)
        else:
            while 0 < sleep_time:
                if SHOULD_STOP:
                    break
                sleep(sleep_time if sleep_time < SLEEP_INTERVAL else SLEEP_INTERVAL)
                sleep_time -= SLEEP_INTERVAL

    logger.info("Finishing collecting")


if __name__ == "__main__":
    main()
