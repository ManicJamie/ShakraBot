import os.path

from pydantic import BaseModel


class GlobalConfig(BaseModel):
    live_channel_id: str | None = None

    @staticmethod
    def persist():
        with open(_CONFIG_PATH, "w") as f:
            f.write(CONFIG.model_dump_json(indent=4))

CONFIG: GlobalConfig = GlobalConfig()

_CONFIG_PATH = "./config.json"

def load():
    global CONFIG
    if os.path.exists(_CONFIG_PATH):
        with open(_CONFIG_PATH) as f:
            CONFIG = GlobalConfig.model_validate_json(f.read())
