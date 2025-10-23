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

    @abc.abstractmethod
    def get_defective_unit_limit(self, inputs: dict, from_date: datetime, to_date: datetime) -> dict:
        pass

    @abc.abstractmethod
    def get_defects_limit(self, inputs: dict, from_date: datetime, to_date: datetime) -> dict:
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
        """
        Returns hour-wise target for the given filters and date range.
        Distributes each record's target evenly across the hours it covers.
        """
        conditions = ["`from_time` <= %(to_date)s", "`to_time` >= %(from_date)s"]
        values = {"from_date": from_date, "to_date": to_date}

        # Add optional filters
        for key in ["physical_cell", "operation", "workstation"]:
            if key in inputs and inputs[key]:
                conditions.append(f"`{key}` = %({key})s")
                values[key] = inputs[key]

        where_clause = " AND ".join(conditions)

        query = f"""
            SELECT from_time, to_time, target
            FROM `tabHourly Target`
            WHERE {where_clause}
        """
        results = frappe.db.sql(query, values, as_dict=True)

        # Prepare hourly buckets
        hourly_targets = {}
        current_time = from_date.replace(minute=0, second=0, microsecond=0)
        while current_time <= to_date:
            hourly_targets[current_time] = 0.0
            current_time += timedelta(hours=1)

        # Distribute each target across hours it spans
        for row in results:
            start = max(from_date, row["from_time"])
            end = min(to_date, row["to_time"])

            if end <= start:
                continue

            # Calculate number of hours covered
            total_hours = (end - start).total_seconds() / 3600.0
            if total_hours <= 0:
                continue

            target_per_hour = row["target"] / total_hours

            # Assign to each hour bucket
            hour_pointer = start.replace(minute=0, second=0, microsecond=0)
            while hour_pointer < end:
                next_hour = hour_pointer + timedelta(hours=1)
                overlap = (min(end, next_hour) - max(start, hour_pointer)).total_seconds() / 3600.0
                if overlap > 0:
                    hourly_targets[hour_pointer] += target_per_hour * overlap
                hour_pointer = next_hour

        return hourly_targets

    
    def get_defective_unit_limit(self, inputs, from_date, to_date):
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
            SELECT SUM(defective_unit_limit) as limit
            FROM `tabHourly Target`
            WHERE {where_clause}
        """
    
    def get_defects_limit(self, inputs, from_date, to_date):
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
            SELECT SUM(defects_limit) as limit
            FROM `tabHourly Target`
            WHERE {where_clause}
        """
    


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
    

