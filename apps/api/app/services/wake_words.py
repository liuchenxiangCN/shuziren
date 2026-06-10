from pathlib import Path

from app.models import WakeConfigResponse, WakeSettings
from app.services.yaml_loader import load_yaml_file


class WakeWordService:
    def __init__(self, config_path: str | Path) -> None:
        self.config_path = Path(config_path)

    def get_config(self) -> WakeConfigResponse:
        data = load_yaml_file(self.config_path)
        wake_words = data.get("wake_words", [])
        if not isinstance(wake_words, list):
            wake_words = []

        settings = data.get("settings", {})
        if not isinstance(settings, dict):
            settings = {}

        return WakeConfigResponse(
            version=str(data.get("version") or "0.1.0"),
            mode=str(data.get("mode") or "semantic"),
            wake_words=[word for word in (str(item).strip() for item in wake_words) if word],
            settings=WakeSettings(**settings),
        )
