from pathlib import Path
import json

import ptunnel

DEFAULT_CONFIG = {
    "range": {
        "start": 30000,
        "end": 50000,
    },
    "password": "",
    "ssl": {
        "cert": "cert.pem",
        "key": "key.pem",
    },
    "keepalive": 12,
}

class Config:
    range: dict
    password: str
    ssl: dict
    keepalive: int

    def __init__(self, config: dict):
        self.range = config["range"]
        self.password = config["password"]
        self.ssl = config["ssl"]
        self.keepalive = config["keepalive"]

def load_config(configPath: Path):
    if not configPath.exists():
        raise FileNotFoundError(f"Config file not found: {configPath}")
    ptunnel.config = Config(json.loads(configPath.read_text()))
    return

def save_config():
    Path("config.json").write_text(json.dumps(DEFAULT_CONFIG, indent=4))
    return