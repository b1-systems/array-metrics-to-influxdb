# Array Metrics to InfluxDB

This program is mainly a wrapper around the
[`py-pure-client`](https://pure-storage-py-pure-client.readthedocs-hosted.com)
and [`influxdb-python`](https://influxdb-python.readthedocs.io) with the goal of
transferring any number of metrics from one or more Pure products to an
InfluxDB. Right now only FlashArray products are supported but other ones such
as Pure1 and FlashBlade should not pose any problem since they are already
supported by the client.

Different so-called _collectors_ are responsible for different metrics. Use
`array-metrics-to-influxdb-collectors` to open the documentation of any
collector/metric of your choice to see which data are transferred. Entries such
as `name`, `id` or `interface_type` as well as the values of the config values
`name` (or `host`) will be stored as _tags_ inside the InfluxDB, the rest will
be stored as _fields_.

## Requirements

- Python 3.9 or higher which is available in current Debian and RHEL releases
- Credentials of an InfluxDB user with _write_ privileges
- API client credentials of one or more supported Pure products (see above)

## Installation/Setup

### Via `pip`

It is highly recommended to install the project and its dependencies to a
dedicated virtual environment (_venv_). Substitute `python3.9` with your version
of choice and `.venv` with your path of choice.

- `python3.9 -m venv .venv`
- `.venv/bin/pip install .`

After the successful installation the commands are available at `.venv/bin/`.
For easier handling it is recommended to simply activate the virtual environment
by running `source .venv/bin/activate`.

### Docker/Podman

Use the provided `Dockerfile` to build the container image.

## Usage

Two commands are available after the installation: The main entrypoint and a
helper program.

### `array-metrics-to-influxdb`

```shell
usage: array-metrics-to-influxdb [-h] [-s | -d] [-c CONFIG] [-v] [-j]
                                 [-r RETENTION_POLICY] [-i INITIAL_START_TIME]

Retrieve selected metrics from one or multiple Pure FlashArray instances and
write them to a InfluxDB. Different collectors are responsible for different
kind of data. They are written to the same database but with different
'measurement' fields.

optional arguments:
  -h, --help            show this help message and exit
  -s, --silent          Switch to WARNING log level. (default: INFO)
  -d, --debug           Switch to DEBUG log level. (default: INFO)
  -c CONFIG, --config CONFIG
                        Configuration file to use. Default value honors
                        $XDG_CONFIG_HOME. (default:
                        /home/luettje/.config/array_metrics_to_influxdb.conf)
  -v, --validate-config
                        Only validate the structure (not the content) of the
                        configuration file. (default: False)
  -j, --json-log        Output log messages as single line JSON instead of
                        plain text. (default: False)
  -r RETENTION_POLICY, --retention-policy RETENTION_POLICY
                        Existing retention policy to specify for all InfluxDB
                        writes. Overrides the value from the config file.
                        (default: None)
  -i INITIAL_START_TIME, --initial-start-time INITIAL_START_TIME
                        Datetime to use for the first collection round.
                        Defaults to one interval before the current time. Can
                        be specified as UNIX timestamp in *milliseconds* or as
                        ISO-8601 formatted string, e.g.
                        2021-08-01[T00[:05[:23[.541[000]]]]] Should not be
                        older than one year which is the maximum retention
                        policy of pure product's performance metrics. Might be
                        helpful if this application crashed and you want to
                        collect the missing data from the downtime. Depending
                        on the requested range the used resolution for the
                        data might have to be increased. This happens
                        dynamically if necessary. (default: None)

v1.0.0, GPLv3 @ B1 Systems GmbH <info@b1-systems.de>
```

If you're using the (self-build) container image you should mount the
configuration file to `/etc/pure_metrics_to_influxdb.conf`:

```bash
podman run -it --rm -v ./config.toml:/etc/pure_metrics_to_influxdb.conf array-metrics-to-influxdb
```

Alternatively use the `-c/--config` option to provide an alternative path:

```bash
podman run -it --rm -v ./config.toml:/config.toml array-metrics-to-influxdb -c /config.toml
```

### `array-metrics-to-influxdb-collectors`

```shell
usage: array-metrics-to-influxdb-collectors [-h] [-a ARRAY_URL]

Prints all available collectors with a short description. Optionally takes an
URL to a Flasharray to provide clickable links to the official REST API where
you can scroll down to the "200 OK" Response, in green, and expand the items
section to learn more about all the metrics.

optional arguments:
  -h, --help            show this help message and exit
  -a ARRAY_URL, --array-url ARRAY_URL
                        By providing the base URL of an array every
                        documentation link will point to it, for example `-a
                        192.168.150.160`

v1.0.0, GPLv3 @ B1 Systems GmbH <info@b1-systems.de>
```

## Configuration

Take a look at the provided example config file `config_example.toml`. It's
format is [`TOML`](https://toml.io/en/). Most entries should be self
explanatory.

The usage of `private_key`, to embed the private RSA key inside the config file,
might be useful you if you're running the application inside a container or are
using a config management tool. If the latter applies make sure to register the
`--validate-config` option as confirmation hook.

## Logging

If you're using a centralized log management system of any kind be sure to call
the application with `-j/--json-log` to output log messages as single line JSON
messages which are **much** easier to process.

## Performance

To make sure that one slow product, e.g. FlashArray, does not slow down the
whole application multiple threads are used. One thread per product is
responsible for retrieving the data and one thread is responsible for sending
the data to an InfluxDB. Communication happens via a queue.

## Development Setup

We are using [`poetry`](https://python-poetry.org) for package and dependency
management. Please make sure that it is available and issue `make setup`
afterwards. This will install the current project (including any development
dependencies) and setup [`pre-commit`](https://pre-commit.com) to make sure that
every one of your future commits follows our standards. Most maintenance tasks
are performed via our `Makefile`, you can get an overview over all tasks by
simply calling `make`.

Use `bin/dev_console.py` to start a preconfigured shell with preconfigured
clients, very useful to determine if you want to add another collector and have
to figure out the potentiell quirks of it.

The `docker-compose.yml` starts an InfluxDB and a Grafana instance, the
configuration for some very basic panels can be found in
`simple_grafana_dashboards.json`.
