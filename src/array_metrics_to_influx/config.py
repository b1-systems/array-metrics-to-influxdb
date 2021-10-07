# copyright: B1 Systems GmbH <info@b1-systems.de>, 2021
# license:   GPLv3+, http://www.gnu.org/licenses/gpl-3.0.html
# author:    Tilman Lüttje <luettje@b1-systems.de>

from collections import defaultdict
from typing import Any, Iterable, Optional

from pydantic import Field, FilePath, SecretStr, root_validator, validator
from pydantic.main import BaseModel
from pydantic.types import PositiveInt

from array_metrics_to_influx.collector_base import COLLECTORS_BY_MEASUREMENT_NAME

# Take a look at the provided `config_example.toml` file for a detailed
# explanation


class CollectorConfig(BaseModel):
    # We could restrict the number of possible values to currently allowed
    # values but they could change in the future and the client will throw
    # errors in case of invalid values so let's just make sure they are
    # positive
    resolution: PositiveInt


class InfluxDBConfig(BaseModel):
    host: str
    user: str
    password: SecretStr
    database: str
    port: int = 8086
    retention_policy: Optional[str] = None
    measurement_prefix: Optional[str] = None


def assert_existing_collectors(collectors: Iterable[str]) -> None:
    for collector in collectors:
        assert collector in COLLECTORS_BY_MEASUREMENT_NAME, " ".join(
            [
                f"`{collector}` is not a valid collector, has to be one of:",
                ", ".join(sorted(COLLECTORS_BY_MEASUREMENT_NAME)) + ".",
                "Call `array-metrics-to-influxdb-collectors` for more information",
            ]
        )


class FlasharrayConfig(BaseModel):
    host: str
    # You can either provide the path to a keyfile or embed it inside the
    # config file
    private_key: SecretStr = SecretStr("")
    private_key_file: Optional[FilePath] = None
    private_key_password: SecretStr
    user: str
    client_id: str
    key_id: str
    issuer: str
    name: Optional[str] = None
    metrics_interval: int = Field(30, ge=30)
    disable: bool = False
    collectors: list[str] = Field(sorted(COLLECTORS_BY_MEASUREMENT_NAME), min_items=1)

    @validator("collectors")
    def check_valid_collectors(cls, v: list[str]) -> list[str]:
        assert_existing_collectors(v)
        return sorted(v)

    @root_validator
    def path_or_key(cls, values: dict[str, Any]) -> dict[str, Any]:
        assert (
            bool(values.get("private_key")) + bool(values.get("private_key_file")) == 1
        ), "You have to provide either `private_key` or `private_key_file`"
        return values


class Config(BaseModel):
    influxdb: InfluxDBConfig
    array: list[FlasharrayConfig]
    collector: dict[str, CollectorConfig]

    class Config:
        allow_mutation = False

    @validator("array")
    def check_unique_host_and_name(
        cls, v: list[FlasharrayConfig]
    ) -> list[FlasharrayConfig]:
        config_by_host_and_name = defaultdict(list)
        for config in v:
            config_by_host_and_name[config.host].append(config)
            if name := config.name:
                config_by_host_and_name[name].append(config)
        for config in v:
            assert (
                len(config_by_host_and_name[config.host]) == 1
            ), f"Duplicate host and/or name: {config.host}"
            if name := config.name:
                assert (
                    len(config_by_host_and_name[name]) == 1
                ), f"Duplicate host and/or name: {name}"
        return v

    @validator("collector")
    def check_valid_collector(
        cls, v: dict[str, CollectorConfig]
    ) -> dict[str, CollectorConfig]:
        assert_existing_collectors(v)
        return v
