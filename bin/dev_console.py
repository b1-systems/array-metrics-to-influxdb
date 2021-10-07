#!/usr/bin/env python3

"""
Launches an IPython instance with preloaded and configured client instances.
"""
from argparse import ArgumentParser, FileType
from textwrap import wrap

from IPython import start_ipython
from pydantic import ValidationError
from tomli import load

from array_metrics_to_influx.collector_base import COLLECTORS_BY_MEASUREMENT_NAME
from array_metrics_to_influx.config import Config
from array_metrics_to_influx.influx import create_influxdb_client
from array_metrics_to_influx.pure import create_flasharray_client


def main() -> int:

    parser = ArgumentParser(description=__doc__)

    parser.add_argument(
        "-c",
        "--config",
        help="Configuration file to use. Default value honors $XDG_CONFIG_HOME.",
        type=FileType("r"),
    )
    parser.add_argument(
        "array_host_or_name",
        help="`name` or `host` config entry of the array to connect to.",
    )
    args = parser.parse_args()

    try:
        config = Config.parse_obj(load(args.config))
    except ValidationError as exc:
        print(exc)
        return 1
    array_by_host_or_name = {}
    for array in config.array:
        array_by_host_or_name[array.host] = array
        if array.name:
            array_by_host_or_name[array.name] = array
    try:
        fa_client = create_flasharray_client(
            array_by_host_or_name[args.array_host_or_name]
        )
    except KeyError:
        print(f"Unknown array `{args.array_host_or_name}`. Aborting")
        return 1
    i_client = create_influxdb_client(config.influxdb)
    for line in wrap(
        "`fa_client` (FlashArray client), `i_client` (InfluxDBClient) and COLLECTORS_BY_MEASUREMENT_NAME are available."
    ):
        print(line)
    print()
    start_ipython(
        argv=[],
        user_ns=dict(
            config=config,
            fa_client=fa_client,
            i_client=i_client,
            COLLECTORS_BY_MEASUREMENT_NAME=COLLECTORS_BY_MEASUREMENT_NAME,
        ),
    )

    return 0


if __name__ == "__main__":
    exit(main())
