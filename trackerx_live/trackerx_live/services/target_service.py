from datetime import datetime, timedelta
import random
import abc
import math
import frappe

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
        """
        Returns the sum of 'target' from Hourly Target based on filters and date range using SQL.
        """
        conditions = ["`from_time` <= %(to_date)s", "`to_time` >= %(from_date)s"]
        values = {"from_date": from_date, "to_date": to_date}

        # Optional filters
        for key in ["physical_cell", "operation", "workstation"]:
            if key in inputs and inputs[key]:
                conditions.append(f"`{key}` = %({key})s")
                values[key] = inputs[key]

        where_clause = " AND ".join(conditions)

        query = f"""
            SELECT SUM(target) as total_target
            FROM `tabHourly Target`
            WHERE {where_clause}
        """

        result = frappe.db.sql(query, values, as_dict=True)

        return result[0]["total_target"] or 0.0

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
        return math.ceil(random.uniform(1000.0, 5000.0))

    def get_hourly_target(self, inputs: dict, from_date: datetime, to_date: datetime) -> dict:
        hourly_targets = {}
        current_time = from_date.replace(minute=0, second=0, microsecond=0)
        while current_time <= to_date:
            # Simulate a live data point
            hourly_targets[current_time] = random.uniform(50.0, 250.0)
            current_time += timedelta(hours=1)
        return hourly_targets
    

