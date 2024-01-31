from dataclasses import dataclass
from datetime import datetime
from common import get_now


@dataclass
class Message:
    time: datetime
    message: str

    def __init__(self, message):
        self.time = get_now()
        self.message = message
