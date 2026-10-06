from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Lue depuis les variables d'environnement (ou un fichier .env en dev local)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Base : PostgreSQL via docker-compose ; SQLite en secours pour un dev sans Docker
    database_url: str = "sqlite:///./sentinel-dev.db"

    # Broker MQTT
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_user: str = ""
    mqtt_password: str = ""
    mqtt_topic_prefix: str = "sentinel/g1"
    mqtt_client_id: str = "sx-api"

    # Sécurité API
    api_key: str = ""
    cors_origins: str = "http://localhost:5173,http://localhost"

    log_level: str = "INFO"

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def topic(self, suffix: str) -> str:
        return f"{self.mqtt_topic_prefix}/{suffix}"


settings = Settings()
