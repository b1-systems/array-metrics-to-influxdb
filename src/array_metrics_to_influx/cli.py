"Contains all entrypoints configured in `pyproject.toml`"

# copyright: B1 Systems GmbH <info@b1-systems.de>, 2021
# license:   GPLv3+, http://www.gnu.org/licenses/gpl-3.0.html
# author:    Tilman Lüttje <luettje@b1-systems.de>

from argparse import ArgumentParser
from inspect import cleandoc
from string import Template
from textwrap import indent

from array_metrics_to_influx import __author__, __license__, __version__
from array_metrics_to_influx.collector_base import COLLECTORS_BY_MEASUREMENT_NAME
from array_metrics_to_influx.main import main


def array_metrics_to_influx() -> None:
    exit(main())


def array_metrics_to_influx_collectors() -> None:
    """
    Prints all available collectors with a short description.

    Optionally takes an URL to a Flasharray to provide clickable links to the
    official REST API where you can scroll down to the "200 OK" Response, in
    green, and expand the items section to learn more about all the metrics.
    """
    parser = ArgumentParser(
        description=array_metrics_to_influx_collectors.__doc__,
        epilog=f"v{__version__}, {__license__} @ {__author__}",
    )
    parser.add_argument(
        "-a",
        "--array-url",
        help="""By providing the base URL of an array every documentation
            link will point to it, for example `-a 192.168.150.160`""",
    )
    args = parser.parse_args()
    description_indent = "  "
    for measurement in sorted(COLLECTORS_BY_MEASUREMENT_NAME):

        # ANSI bold escape codes
        print("\033[1m", measurement, "\033[0m", sep="")
        collector_doc = cleandoc(
            COLLECTORS_BY_MEASUREMENT_NAME[measurement].__doc__
            or "No description available"
        )
        if args.array_url:
            collector_doc = Template(collector_doc).safe_substitute(
                dict(ARRAY_URL=args.array_url)
            )
        print(
            indent(
                collector_doc,
                description_indent,
            )
        )
        print()
    if not args.array_url:
        print("Hint: See `-h/--help` for a way to construct valid links.")
