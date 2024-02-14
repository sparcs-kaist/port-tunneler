import logging
from prompt_toolkit import print_formatted_text

class PromptHandler(logging.StreamHandler):
    def emit(self, record):
        msg = self.format(record)
        print_formatted_text(msg)

logger = logging.getLogger("ptunnel")
logger.setLevel(logging.INFO)
handler = PromptHandler()
handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
handler.setLevel(logging.INFO)
logger.addHandler(handler)

import ptunnel.client
import ptunnel.server

config: ptunnel.server.Config = None