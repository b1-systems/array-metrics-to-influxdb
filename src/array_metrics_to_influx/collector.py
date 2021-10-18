"""
Contains all collector classes. Each is a subclass of `BaseCollector` which
provides the most needed functionality.

When adding a new one you will have to implement `get_response` and depending
on the layout of the data also `response_to_influx_data` but if you're lucky
you use `influx_data_from_simple_response` with different parameters.

The docstring of the classes is used when
`array-metrics-to-influxdb-collectors` is called, see `print_collectors` for
more details. When adding new collectors make sure to add a template link to
the official REST API for further details. It should contain $ARRAY_URL to
allow easy substitution to create clickable links.
"""

# copyright: B1 Systems GmbH <info@b1-systems.de>, 2021
# license:   GPLv3+, http://www.gnu.org/licenses/gpl-3.0.html
# author:    Tilman Lüttje <luettje@b1-systems.de>

from time import time
from typing import Iterator, Optional, Union

from pypureclient.responses import ErrorResponse, ValidResponse

from array_metrics_to_influx.collector_base import (
    ArrayPerformanceCollectorMixin,
    BaseCollector,
    PerformanceCollectorMixin,
    SpaceCollectorMixin,
    VolumeCollectorMark,
    VolumeGroupCollectorMark,
)
from array_metrics_to_influx.influx import InfluxDataPoint


class ArraysPerformance(
    BaseCollector, ArrayPerformanceCollectorMixin, measurement="arrays_performance"
):
    """
    Performance data at the array level including latency, bandwidth, IOPS,
    average I/O size, and queue depth.

    See
    http://$ARRAY_URL/static/0/help/rest2.0/fa2.x-api-reference.html#tag/Arrays/paths/~1api~12.7~1arrays~1performance/get
    for more details.
    """

    RESOLUTIONS = (
        # see https://github.com/PureStorage-OpenConnect/py-pure-client/issues/17
        # 1_000,
        30_000,
        300_000,
        1_800_000,
        7_200_000,
        28_800_000,
        86_400_000,
    )

    def get_response(
        self, *, start_time: int, resolution: int, ids: Optional[list[str]] = None
    ) -> Union[ErrorResponse, ValidResponse]:
        return self.fa_client.get_arrays_performance(
            start_time=start_time, resolution=resolution
        )


class VolumesPerformance(
    BaseCollector,
    PerformanceCollectorMixin,
    VolumeCollectorMark,
    measurement="volumes_performance",
):
    """
    Real-time latency data, and average I/O sizes for each volume and as a
    total of all volumes across the entire array.

    See
    http://$ARRAY_URL/static/0/help/rest2.0/fa2.x-api-reference.html#tag/Volumes/paths/~1api~12.7~1volumes~1performance/get
    for more details.
    """

    def get_response(
        self, *, start_time: int, resolution: int, ids: Optional[list[str]] = None
    ) -> Union[ErrorResponse, ValidResponse]:
        return self.fa_client.get_volumes_performance(
            start_time=start_time, resolution=resolution, ids=ids, destroyed=False
        )


class VolumeGroupsPerformance(
    BaseCollector,
    PerformanceCollectorMixin,
    VolumeGroupCollectorMark,
    measurement="volume_groups_performance",
):
    """
    Real-time latency data, and average I/O sizes for each volume group and as
    a total of all volume groups across the entire array.

    See
    http://$ARRAY_URL/static/0/help/rest2.0/fa2.x-api-reference.html#tag/Volume-Groups/paths/~1api~12.7~1volume-groups~1performance/get
    for more details.
    """

    def get_response(
        self, *, start_time: int, resolution: int, ids: Optional[list[str]] = None
    ) -> Union[ErrorResponse, ValidResponse]:
        return self.fa_client.get_volume_groups_performance(
            start_time=start_time, resolution=resolution, ids=ids, destroyed=False
        )


class NetworkInterfacesPerformance(
    BaseCollector,
    PerformanceCollectorMixin,
    measurement="network_interfaces_performance",
):
    """
    Network statistics, historical bandwidth and error reporting.

    See
    http://$ARRAY_URL/static/0/help/rest2.0/fa2.x-api-reference.html#tag/Network-Interfaces/paths/~1api~12.7~1network-interfaces~1performance/get
    for more details.
    """

    def get_response(
        self, *, start_time: int, resolution: int, ids: Optional[list[str]] = None
    ) -> Union[ErrorResponse, ValidResponse]:
        return self.fa_client.get_network_interfaces_performance(
            start_time=start_time, resolution=resolution
        )

    def response_to_influx_data(
        self, response: Union[ErrorResponse, ValidResponse]
    ) -> Iterator[InfluxDataPoint]:
        # We cannot use influx_data_from_simple_response here since the layout
        # of data differs:
        # - There is no `id` but an `interface_type` entry
        # - The relevant data are inside an entry named like the value of `interface_type`
        for item in response.items:
            item_dict = item.to_dict()
            tags = dict(host=self.host_tag)
            for tag_key in ["name", "interface_type"]:
                tags[tag_key] = item_dict.pop(tag_key)
            yield InfluxDataPoint(
                tags=tags,
                measurement=self.influx_measurement,
                time=item_dict.pop("time"),
                fields=item_dict[tags["interface_type"]],
            )


class HostsPerformance(
    BaseCollector, PerformanceCollectorMixin, measurement="hosts_performance"
):
    """
    Displays real-time and historical performance data, real-time latency data,
    and average I/O sizes across all volumes, displayed both by host and as a
    total across all hosts.

    See
    http://$ARRAY_URL/static/0/help/rest2.0/fa2.x-api-reference.html#tag/Hosts/paths/~1api~12.7~1hosts~1performance/get
    for more details.
    """

    def get_response(
        self, *, start_time: int, resolution: int, ids: Optional[list[str]] = None
    ) -> Union[ErrorResponse, ValidResponse]:
        # function does not take a `start_time` or `resolution` parameter
        return self.fa_client.get_hosts_performance()

    def response_to_influx_data(
        self, response: Union[ErrorResponse, ValidResponse]
    ) -> Iterator[InfluxDataPoint]:
        return self.influx_data_from_simple_response(
            response,
            # Override of default value since items of response do not contain
            # an `id` entry
            tag_keys=("name",),
        )


class VolumesSpace(
    BaseCollector, SpaceCollectorMixin, VolumeCollectorMark, measurement="volumes_space"
):
    """
    Provisioned (virtual) size and physical storage consumption data for each volume.

    See
    http://$ARRAY_URL/static/0/help/rest2.0/fa2.x-api-reference.html#tag/Volumes/paths/~1api~12.7~1volumes~1space/get
    for more details.
    """

    def get_response(
        self, *, start_time: int, resolution: int, ids: Optional[list[str]] = None
    ) -> Union[ErrorResponse, ValidResponse]:
        return self.fa_client.get_volumes_space(
            start_time=start_time, resolution=resolution, ids=ids, destroyed=False
        )

    def response_to_influx_data(
        self, response: Union[ErrorResponse, ValidResponse]
    ) -> Iterator[InfluxDataPoint]:
        return self.influx_data_from_simple_response(response, field_key="space")


class Controllers(BaseCollector, measurement="controllers"):
    """
    Name, mode, FlashArray model, Purity//FA software version, and status of
    each controller in the array.

    See
    http://$ARRAY_URL/static/0/help/rest2.0/fa2.x-api-reference.html#tag/Controllers/paths/~1api~12.7~1controllers/get
    for more details.
    """

    # We're only requesting current information, therefore no resolutions
    RESOLUTIONS = (None,)

    def get_response(
        self, *, start_time: int, resolution: int, ids: Optional[list[str]] = None
    ) -> Union[ErrorResponse, ValidResponse]:
        # neither `start_time` nor `resolution` makes any sense since we're not
        # requesting any historical data
        return self.fa_client.get_controllers()

    def response_to_influx_data(
        self, response: Union[ErrorResponse, ValidResponse]
    ) -> Iterator[InfluxDataPoint]:
        return self.influx_data_from_simple_response(
            # since these are no historical data they do not contain any
            # embedded timestamp
            response,
            tag_keys=("name", "type"),
            custom_timestamp=int(time() * 1000),
        )


class PodsPerformanceReplicationByArray(
    BaseCollector,
    PerformanceCollectorMixin,
    measurement="pods_performance_replication_by_array",
):
    """
    Pod replication performance data, organized by array. The data returned is
    the real-time and historical performance data for each replication type at
    the pod level. Values include continuous, periodic, resync, and sync.

    See
    http://$ARRAY_URL/static/0/help/rest2.0/fa2.x-api-reference.html#tag/Pods/paths/~1api~12.7~1pods~1performance~1replication~1by-array/get
    for more details.
    """

    def get_response(
        self, *, start_time: int, resolution: int, ids: Optional[list[str]] = None
    ) -> Union[ErrorResponse, ValidResponse]:
        # Another quirk, the function does not return any data if any
        # `start_time` is passed
        # https://github.com/PureStorage-OpenConnect/py-pure-client/issues/19
        return self.fa_client.get_pods_performance_replication_by_array(
            resolution=resolution
        )

    def response_to_influx_data(
        self, response: Union[ErrorResponse, ValidResponse]
    ) -> Iterator[InfluxDataPoint]:
        for item in response.items:
            item_dict = item.to_dict()
            tags = {}
            for entity in ["array", "pod"]:
                for value in ["id", "name"]:
                    tags[f"{entity}_{value}"] = item_dict[entity][value]
            tags["host"] = self.host_tag
            fields = {}
            # take a look at the item structure inside the official API documentation
            # (see link above) to understand the following lines
            for value in ["continuous", "periodic", "resync", "sync"]:
                for direction in ["from_remote", "to_remote", "total"]:
                    fields[f"{value}_{direction}_bytes_per_sec"] = item_dict[
                        f"{value}_bytes_per_sec"
                    ][f"{direction}_bytes_per_sec"]

            yield InfluxDataPoint(
                tags=tags,
                measurement=self.influx_measurement,
                time=item_dict.pop("time"),
                fields=fields,
            )


class ArraysSpace(BaseCollector, SpaceCollectorMixin, measurement="arrays_space"):
    """
    Real-time and historical array space information including unique volume
    and snapshot space, shared space, data reduction, provisioned capacity,
    usable capacity, and parity.

    See
    http://$ARRAY_URL/static/0/help/rest2.0/fa2.x-api-reference.html#tag/Arrays/paths/~1api~12.7~1arrays~1space/get
    for more details.
    """

    def get_response(
        self, *, start_time: int, resolution: int, ids: Optional[list[str]] = None
    ) -> Union[ErrorResponse, ValidResponse]:
        return self.fa_client.get_arrays_space(
            start_time=start_time, resolution=resolution
        )

    def response_to_influx_data(
        self, response: Union[ErrorResponse, ValidResponse]
    ) -> Iterator[InfluxDataPoint]:
        # This time the items contain one nested entry besides two flat ones
        for item in response.items:
            item_dict = item.to_dict()
            tags = dict(host=self.host_tag)
            for tag_key in ("id", "name"):
                tags[tag_key] = item_dict.pop(tag_key)
            fields = item_dict["space"]
            for value in ["capacity", "parity"]:
                try:
                    fields[value] = item_dict[value]
                except KeyError:
                    continue
            yield InfluxDataPoint(
                tags=tags,
                measurement=self.influx_measurement,
                time=item_dict.pop("time"),
                fields=fields,
            )
