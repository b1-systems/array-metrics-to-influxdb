# copyright: B1 Systems GmbH <info@b1-systems.de>, 2021
# license:   GPLv3+, http://www.gnu.org/licenses/gpl-3.0.html
# author:    Tilman Lüttje <luettje@b1-systems.de>

from abc import ABC, abstractmethod
from datetime import timedelta
from time import time
from typing import ClassVar, Final, Iterator, Optional, Type, Union

import structlog

# this type annotation isn't necessarily correct but it's the version that i
# have been using in development.
# Feel free to bump it (by e.g. changing FA_2_7 to FA_2_8) to the version that
# you're using in development or the one that will be used in production.
from pypureclient.flasharray.FA_2_7.client import Client as FlasharrayClient
from pypureclient.responses import ErrorResponse, ValidResponse

from array_metrics_to_influx.errors import PureErrorResponse
from array_metrics_to_influx.influx import InfluxDataPoint

# Given a past point in time this table tells you which minimal resolution has
# to be used against the REST API in order to retrieve any data

METRIC_RESOLUTION_TO_RETENTION_TIME = {
    1_000: timedelta(hours=3),
    30_000: timedelta(hours=3),
    300_000: timedelta(hours=24),
    1_800_000: timedelta(days=7),
    7_200_000: timedelta(days=30),
    28_800_000: timedelta(days=90),
    # Infinite retention policy, 100 years should be enough
    86_400_000: timedelta(days=365) * 100,
}

COLLECTORS_BY_MEASUREMENT_NAME: Final[dict[str, Type["BaseCollector"]]] = {}


class BaseCollector(ABC):

    measurement: ClassVar[str]

    RESOLUTIONS: ClassVar[Union[tuple[int, ...], tuple[None]]]

    def __init__(
        self,
        host_tag: str,
        fa_client: FlasharrayClient,
        min_resolution: Optional[int] = None,
        measurement_prefix: str = "",
    ) -> None:
        self.host_tag = host_tag
        self.fa_client = fa_client
        self.min_resolution: Optional[int]
        if min_resolution:
            type(self).validate_resolution(min_resolution)
            self.min_resolution = min_resolution
        else:
            self.min_resolution = type(self).RESOLUTIONS[0]
        self.influx_measurement = measurement_prefix + self.measurement
        self.logger = structlog.get_logger(
            host=host_tag,
            min_resolution=self.min_resolution,
            measurement=self.measurement,
            rest_api_version=fa_client.get_rest_version(),
        )
        self.logger.debug("collector_created")

    def __init_subclass__(cls, /, measurement: str) -> None:
        if existing_collector := COLLECTORS_BY_MEASUREMENT_NAME.get(measurement):
            # this case can happen during development with live reload
            if existing_collector is not cls:
                raise ValueError(
                    f"Measurement name {measurement} is already taken by {existing_collector}"
                )
        cls.measurement = measurement
        COLLECTORS_BY_MEASUREMENT_NAME[measurement] = cls

    @classmethod
    def validate_resolution(cls, min_resolution: int) -> None:
        if min_resolution not in cls.RESOLUTIONS:
            raise ValueError(f"min_resolution has to be one of {cls.RESOLUTIONS}")

    @abstractmethod
    def get_response(
        self, *, start_time: int, resolution: int
    ) -> Union[ErrorResponse, ValidResponse]:
        ...

    def influx_data(self, start_time: int) -> Iterator[InfluxDataPoint]:
        start_time_delta = timedelta(milliseconds=int(time() * 1000) - start_time)
        min_resolution = self.min_resolution
        for resolution, retention_time in METRIC_RESOLUTION_TO_RETENTION_TIME.items():
            # no need to check against a lower resolution than requested/configured
            if self.min_resolution and resolution < self.min_resolution:
                continue
            if start_time_delta <= retention_time:
                min_resolution = resolution
                break
        # only log about chosen resolution if it differs from the default one
        # happens primary if past metrics are collected subsequently
        if any(self.RESOLUTIONS) and min_resolution != self.min_resolution:
            self.logger.info(
                "Choose different resolution due to start_time",
                resolution=min_resolution,
                start_time_delta=str(start_time_delta),
            )
        assert (
            min_resolution
        ), "minimal resolution cannot be None, are 100 years not enough?"
        response = self.get_response(start_time=start_time, resolution=min_resolution)
        if isinstance(response, ErrorResponse):
            raise PureErrorResponse(response)
        return self.response_to_influx_data(response)

    def response_to_influx_data(
        self, response: Union[ErrorResponse, ValidResponse]
    ) -> Iterator[InfluxDataPoint]:
        return self.influx_data_from_simple_response(response)

    def influx_data_from_simple_response(
        self,
        response: Union[ErrorResponse, ValidResponse],
        *,
        tag_keys: tuple[str, ...] = ("id", "name"),
        field_key: Optional[str] = None,
        custom_timestamp: Optional[int] = None,
    ) -> Iterator[InfluxDataPoint]:
        """Helper function covering the most basic case of transforming flasharray
        metrics to influxdb entries.

        Care has to be taken if other fields or tags should be used or if the
        `items` property of the response is not flat.

        :param response: The response from the client (from the Flasharray).
        :param host_tag: Identifier of Flasharray which will be written to the
            `host` tag of every data point.
        :param tag_keys: Keys which should be stored as tags instead of fields
            inside the InfluxDB.
        :param field_key: Optional key to access the field values of any item.
        :param custom_timestamp: Timestamp to use for the data points, useful in
            case they do not contain any.
        """
        if isinstance(response, ErrorResponse):
            raise PureErrorResponse(response)
        for item in response.items:
            item_dict = item.to_dict()
            tags = dict(host=self.host_tag)
            for tag_key in tag_keys:
                tags[tag_key] = item_dict.pop(tag_key)
            yield InfluxDataPoint(
                measurement=self.influx_measurement,
                tags=tags,
                time=custom_timestamp or item_dict.pop("time"),
                fields=item_dict[field_key] if field_key else item_dict,
            )


class ArrayPerformanceCollectorMixin:

    RESOLUTIONS: ClassVar[Union[tuple[int, ...], tuple[None]]] = (
        1_000,
        30_000,
        300_000,
        1_800_000,
        7_200_000,
        28_800_000,
        86_400_000,
    )


class PerformanceCollectorMixin:

    RESOLUTIONS: ClassVar[Union[tuple[int, ...], tuple[None]]] = (
        30_000,
        300_000,
        1_800_000,
        7_200_000,
        28_800_000,
        86_400_000,
    )


class SpaceCollectorMixin:
    RESOLUTIONS: ClassVar[Union[tuple[int, ...], tuple[None]]] = (
        300_000,
        1_800_000,
        7_200_000,
        28_800_000,
        86_400_000,
    )
