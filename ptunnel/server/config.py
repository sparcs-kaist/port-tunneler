from pathlib import Path
import json

import ptunnel

DEFAULT_CONFIG = {
    "tunneldns": "hackaton.sparcs.net",
    "range": {
        "start": 30000,
        "end": 50000,
    },
    "password": "",
    "adminpassword": "",
    "ssl": {
        "cert": "cert.pem",
        "key": "key.pem",
    },
    "keepalive": 12,
}

class Config:
    tunneldns: str
    range: dict
    password: str
    adminpassword: str
    ssl: dict
    keepalive: int

    def __init__(self, config: dict):
        self.tunneldns = config["tunneldns"]
        self.range = config["range"]
        self.password = config["password"]
        self.adminpassword = config["adminpassword"]
        self.ssl = config["ssl"]
        self.keepalive = config["keepalive"]

        if not self.password:
            raise ValueError("Password not set.")
        if not self.adminpassword:
            raise ValueError("Admin password not set.")

def load_config(configPath: Path):
    if not configPath.exists():
        raise FileNotFoundError(f"Config file not found: {configPath}")
    ptunnel.config = Config(json.loads(configPath.read_text()))
    return

def save_config():
    Path("config.json").write_text(json.dumps(DEFAULT_CONFIG, indent=4))
    return