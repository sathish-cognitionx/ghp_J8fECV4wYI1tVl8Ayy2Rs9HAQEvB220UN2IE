from datetime import datetime, timedelta
import random
import abc

class TargetService(abc.ABC):

    @abc.abstractmethod
    def get_total_target(self, inputs: dict, from_date: datetime, to_date: datetime) -> float:
        pass

    

    @abc.abstractmethod
    def get_hourly_target(self, inputs: dict, from_date: datetime, to_date: datetime) -> dict:
        pass


class LiveTargetService(TargetService):

    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(LiveTargetService, cls).__new__(cls)
        return cls._instance

    def __init__(self):

        if self._initialized:
            return
        
        self._initialized = True

    def get_total_target(self, inputs: dict, from_date: datetime, to_date: datetime) -> float:
        return random.uniform(1000.0, 5000.0)

    def get_hourly_target(self, inputs: dict, from_date: datetime, to_date: datetime) -> dict:
        hourly_targets = {}
        current_time = from_date.replace(minute=0, second=0, microsecond=0)
        while current_time <= to_date:
            # Simulate a live data point
            hourly_targets[current_time] = random.uniform(50.0, 250.0)
            current_time += timedelta(hours=1)
        return hourly_targets
    


class ConfigTargetService(TargetService):

    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ConfigTargetService, cls).__new__(cls)
        return cls._instance

    def __init__(self):

        if self._initialized:
            return
        
        self._initialized = True

    def get_total_target(self, inputs: dict, from_date: datetime, to_date: datetime) -> float:
        return random.uniform(1000.0, 5000.0)

    def get_hourly_target(self, inputs: dict, from_date: datetime, to_date: datetime) -> dict:
        hourly_targets = {}
        current_time = from_date.replace(minute=0, second=0, microsecond=0)
        while current_time <= to_date:
            # Simulate a live data point
            hourly_targets[current_time] = random.uniform(50.0, 250.0)
            current_time += timedelta(hours=1)
        return hourly_targets
    

