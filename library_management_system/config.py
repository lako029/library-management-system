import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Environment = Literal["local", "production"]
ENVIRONMENTS_DIR = Path(__file__).with_name("environments")


@dataclass(frozen=True)
class Settings:
    environment: Environment
    app_title: str
    auto_create_schema: bool
    agent_model: str
    synopsis_embedding_model: str
    synopsis_embedding_dimensions: int


def get_settings() -> Settings:
    environment = os.getenv("APP_ENV", "local")
    if environment not in ("local", "production"):
        raise ValueError("APP_ENV must be either 'local' or 'production'.")

    settings_path = ENVIRONMENTS_DIR / f"{environment}.toml"
    with settings_path.open("rb") as config_file:
        values = tomllib.load(config_file)

    return Settings(
        environment=environment,
        app_title=values["app_title"],
        auto_create_schema=values["auto_create_schema"],
        agent_model=os.getenv("AGENT_MODEL", values["agent_model"]),
        synopsis_embedding_model=os.getenv(
            "SYNOPSIS_EMBEDDING_MODEL",
            values["synopsis_embedding_model"],
        ),
        synopsis_embedding_dimensions=int(
            os.getenv(
                "SYNOPSIS_EMBEDDING_DIMENSIONS",
                str(values["synopsis_embedding_dimensions"]),
            )
        ),
    )
