import typing

import pydantic


class ConfigurableStageParam(pydantic.BaseModel):
    """A configurable parameter of a stage of a pipeline or job."""

    name: str
    key: str
    category: str
    value: typing.Any


class ConfigurableStage(pydantic.BaseModel):
    """A configurable stage of a pipeline or job."""

    key: str
    name: str
    params: list[ConfigurableStageParam] = []


def default_stage() -> ConfigurableStage:
    return ConfigurableStage(
        key="default",
        name="Default Stage",
        params=[
            ConfigurableStageParam(
                name="Placeholder",
                key="default",
                category="placeholder",
                value=0,
            )
        ],
    )


def default_stages() -> list[ConfigurableStage]:
    return [default_stage()]
