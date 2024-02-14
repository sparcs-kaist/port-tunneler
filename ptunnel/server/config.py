import ptunnel

DEFAULT_CONFIG = {
    "range": {
        "start": 30000,
        "end": 50000,
    },
    "timeout": 60,
    "password": "",
    "ssl": {
        "cert": "cert.pem",
        "key": "key.pem",
    },
    "keepalive": 12,
}

class Config:
    host: str
    mgrport: int
    range: dict
    timeout: int
    password: str
    ssl: dict
    keepalive: int

    def __init__(self, config: dict):
        self.host = config["host"]
        self.mgrport = config["mgrport"]
        self.range = config["range"]
        self.timeout = config["timeout"]
        self.password = config["password"]
        self.ssl = config["ssl"]
        self.keepalive = config["keepalive"]
