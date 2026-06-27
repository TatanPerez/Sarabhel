"""Configuration settings for the C2 server.
All values are loaded from environment variables using pydantic.BaseSettings.
"""

from pydantic import Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # MQTT configuration
    mqtt_host: str = Field(..., env="MQTT_HOST")
    mqtt_port: int = Field(1883, env="MQTT_PORT")
    mqtt_user: str = Field(..., env="MQTT_USER")
    mqtt_password: str = Field(..., env="MQTT_PASSWORD")

    # PostgreSQL configuration
    db_host: str = Field(..., env="DB_HOST")
    db_port: int = Field(5432, env="DB_PORT")
    db_user: str = Field(..., env="DB_USER")
    db_password: str = Field(..., env="DB_PASSWORD")
    db_name: str = Field(..., env="DB_NAME")

    # C2 specific secrets
    c2_static_token: str = Field(..., env="C2_STATIC_TOKEN")
    c2_api_key: str = Field(..., env="C2_API_KEY")

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
