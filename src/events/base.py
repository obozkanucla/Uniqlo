from abc import ABC, abstractmethod

class EventDetector(ABC):
    event_type: str

    @abstractmethod
    def detect(self, conn, catalog: str):
        """
        Returns a list of:
        (event_time, catalog, event_type, event_value)
        """
        pass