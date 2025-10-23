# trackerx_live/scheduler/target_scheduler.py
from __future__ import annotations
import frappe
from frappe.utils import now_datetime, get_datetime, flt
from datetime import timedelta
import traceback
import logging

logger = frappe.logger("target_scheduler")
logger.setLevel(logging.INFO) 

# prefer frappe.enqueue for background tasks rather than raw threading
# scheduler entrypoint (cron in hooks.py should call this)
@frappe.whitelist()
def run_every_min():
    minute_from = now_datetime().replace(second=0, microsecond=0)
    minute_to = minute_from + timedelta(minutes=1)
    hour_from = minute_from.replace(minute=0)
    hour_to = hour_from + timedelta(hours=1)

    try:
        # correct filters usage: exclude a name using list-of-lists
        cells = frappe.get_all("Physical Cell", fields=["name"],
                               filters=[["name", "!=", "QR/Barcode Cut Bundle Activation"]])
        for c in cells:
            # enqueue a job per cell (safer than raw threads)
            frappe.enqueue(
                "trackerx_live.trackerx_live.scheduler.target_scheduler.calculate_cell_target_enqueue",
                queue="long",
                timeout=600,
                is_async=True,
                cell_name=c.get("name"),
                minute_from=minute_from,
                minute_to=minute_to,
                hour_from=hour_from,
                hour_to=hour_to,
            )
        frappe.logger("target_scheduler").info(f"Enqueued {len(cells)} tasks for window {minute_from} - {minute_to}")
    except Exception:
        frappe.logger("target_scheduler").error(f"Scheduler failed: {traceback.format_exc()}")


def calculate_cell_target_enqueue(cell_name, minute_from, minute_to, hour_from, hour_to):
    """Wrapper called by frappe.enqueue (arguments will be passed as strings sometimes)"""
    # if any args are string timestamps, convert
    try:
        if isinstance(minute_from, str):
            minute_from = get_datetime(minute_from)
        if isinstance(minute_to, str):
            minute_to = get_datetime(minute_to)
        if isinstance(hour_from, str):
            hour_from = get_datetime(hour_from)
        if isinstance(hour_to, str):
            hour_to = get_datetime(hour_to)
    except Exception:
        pass

    calculate_cell_target(cell_name, minute_from, minute_to, hour_from, hour_to)


def calculate_cell_target(cell_name: str, minute_from, minute_to, hours_from, hours_to):
    try:
        cell = frappe.get_cached_doc("Physical Cell", cell_name)
        now_time = minute_from.time()

        minutes = (minute_to - hours_from).total_seconds()/60

        # check breaks
        for br in (cell.get("cell_breaks") or []):
            b_start = _parse_time(br.get("break_start") or br.get("from") or br.get("start"))
            b_end = _parse_time(br.get("break_end") or br.get("to") or br.get("end"))
            if b_start and b_end and _time_in_range(now_time, b_start, b_end):
                frappe.logger("target_scheduler").info(f"Cell {cell_name} is in break ({b_start}-{b_end}). Skipping.")
                return

        # check cell working window
        cell_start = _parse_time(cell.get("start_time"))
        cell_end = _parse_time(cell.get("end_time"))
        if cell_start and cell_end and not _time_in_range(now_time, cell_start, cell_end):
            frappe.logger("target_scheduler").info(f"Cell {cell_name} outside working window. Skipping.")
            return
        
        # get attendance
        attendance_query = """
            SELECT COALESCE(value, 0) AS total_count
            FROM `tabOperator Attendance`
            WHERE physical_cell = %s
            AND hour = %s
            """
        result = frappe.db.sql(attendance_query, (cell.name, hours_from), as_dict=True)
        attendance_count = result[0].total_count if result else 0

        # running style resolution (ensure get_running_style returns expected doc)
        from trackerx_live.trackerx_live.api.live_dashboard import get_running_style
        running_style = get_running_style(workstation=None, operation=None, physical_cell=cell.name)
        if not running_style or not getattr(running_style, "item", None):
            # nothing to do for this cell if no style
            frappe.logger("target_scheduler").info(f"No Running style for the cell {cell_name} ignoreing")
            return
        style = running_style.item

        pt_filters = {"physical_cell": cell_name, "is_active": 1, "style": style}
        pt_list = frappe.get_all("Production Target Configuration", filters=pt_filters,
                                 fields=["name", "hour_target", "start", "end", "style", "operator", "sam"],
                                 order_by="modified desc")
        if not pt_list:
            frappe.logger("target_scheduler").info(f"No active Production Target Configuration for {cell_name} / style {style}")
            return

        hour_target = flt(pt_list[0].get("hour_target") or 0)
        cell_sam = flt(pt_list[0].get("sam") or 0)
        if hour_target <= 0:
            frappe.logger("target_scheduler").info(f"hour_target <= 0 for {cell_name} / style {style}")
            return

        per_minute_per_operation = hour_target / 60.0

        rows = frappe.get_all("Physical Cell Operation", filters={"parent": cell_name}, fields=["operation", "workstation"]) or []
        op_ws = {}
        for r in rows:
            op = r.get("operation")
            ws = r.get("workstation")
            if not op:
                continue
            op_ws.setdefault(op, set())
            if ws:
                op_ws[op].add(ws)

        if not op_ws:
            frappe.logger("target_scheduler").info(f"no operations configured for {cell_name}")
            return

        for operation, workstations in op_ws.items():
            ws_list = list(workstations) if workstations else [None]
            num_ws = len(ws_list)
            op_target_minute = per_minute_per_operation
            per_ws_target = op_target_minute / num_ws if num_ws else op_target_minute

            op_doc = frappe.get_cached_doc("Operation", operation) if operation else None
            allowed_unit_pct = flt(op_doc.get("custom_allowed_defective_unit_limit") or 0)
            allowed_defects_pct = flt(op_doc.get("custom_allowed_defects_limit") or 0)

            for ws in ws_list:
                # build SQL conditionally
                if ws:
                    workstation_clause = "AND sl.workstation = %s"
                    params = (cell_name, operation, ws, minute_from, minute_to)
                else:
                    workstation_clause = "AND sl.workstation IS NOT NULL"
                    params = (cell_name, operation, minute_from, minute_to)

                # sum quantity with COALESCE
                sql = f"""
                    SELECT COALESCE(SUM(pi.quantity), 0) as output_count
                    FROM `tabItem Scan Log` sl
                    LEFT JOIN `tabProduction Item` pi ON pi.name = sl.production_item
                    WHERE sl.physical_cell = %s
                      AND sl.operation = %s
                      {workstation_clause}
                      AND sl.scan_time >= %s
                      AND sl.scan_time < %s
                      AND sl.log_status = 'Completed'
                      AND sl.status IN ('Pass','SP Pass','Counted')
                """

                try:
                    res = frappe.db.sql(sql, params)
                    produced_qty = flt(res[0][0]) if res and res[0] and res[0][0] is not None else 0.0
                except Exception:
                    # fallback to safe count
                    try:
                        cond = {"physical_cell": cell_name, "operation": operation,
                                "scan_time": [">=", minute_from, "<", minute_to], "log_status": "Completed"}
                        if ws:
                            cond["workstation"] = ws
                        produced_qty = flt(frappe.db.count("Item Scan Log", cond))
                    except Exception:
                        produced_qty = 0.0

                defective_unit_limit = produced_qty * (allowed_unit_pct / 100.0)
                defects_limit = produced_qty * (allowed_defects_pct / 100.0)

                # atomic upsert pattern: try to get existing row, else create; protect against duplicates by retrying
                try:
                    # try to find existing hourly row
                    existing = frappe.db.get_value("Hourly Target", {
                        "physical_cell": cell_name,
                        "operation": operation,
                        "workstation": ws,
                        "from_time": hours_from,
                        "to_time": hours_to
                    }, ["name", "target", "defective_unit_limit", "defects_limit", "cell_sam_per_minutes"])

                    if existing:
                        name, prev_target, prev_def_unit, prev_defects, prev_cell_sam_per_minutes = existing[0], flt(existing[1] or 0), flt(existing[2] or 0), flt(existing[3] or 0), flt(existing[4] or 0)
                        new_cell_sam_per_minutes = ((prev_cell_sam_per_minutes * (minutes - 1)) + cell_sam )/minutes

                        produced_minutes = produced_qty * new_cell_sam_per_minutes
                        available_minutes = attendance_count * minutes
                        target_minutes = per_ws_target * new_cell_sam_per_minutes
                        # update atomically using ORM
                        frappe.db.sql("""UPDATE `tabHourly Target`
                                         SET `target` = %s, `defective_unit_limit` = %s, `defects_limit` = %s,
                                            `cell_sam_per_minutes` = %s, `working_time_in_mins` = %s, `produced_minutes` = %s, `available_minutes` = %s, `target_minutes` = %s
                                         WHERE name = %s""",
                                      (prev_target + per_ws_target, prev_def_unit + defective_unit_limit, prev_defects + defects_limit, new_cell_sam_per_minutes, minutes, produced_minutes, available_minutes, target_minutes, name))
                    else:
                        new_record = frappe.new_doc("Hourly Target")
                        new_record.physical_cell = cell_name
                        new_record.operation = operation
                        new_record.workstation = ws
                        new_record.company = frappe.defaults.get_user_default("Company") or None
                        new_record.from_time = hours_from
                        new_record.to_time = hours_to
                        new_record.target = per_ws_target
                        new_record.defective_unit_limit = defective_unit_limit
                        new_record.defects_limit = defects_limit
                        new_record.output = produced_qty
                        new_record.cell_sam = cell_sam
                        new_record.cell_sam_per_minutes = cell_sam
                        new_record.no_of_operators = attendance_count
                        new_record.working_time_in_mins = minutes
                        new_record.produced_minutes = new_record.output * new_record.cell_sam_per_minutes
                        new_record.available_minutes = new_record.no_of_operators * new_record.working_time_in_mins
                        new_record.target_minutes = new_record.target * new_record.cell_sam_per_minutes
                        new_record.insert(ignore_permissions=True)
                        # insert new row
                        # frappe.db.sql("""INSERT INTO `tabHourly Target`
                        #                  ( `physical_cell`, `operation`, `workstation`, `company`, `from`, `to`, `target`, `defective_unit_limit`, `defects_limit`)
                        #                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        #               ( cell_name, operation, ws, frappe.defaults.get_user_default("Company") or None,
                        #                hours_from, hours_to, per_ws_target, defective_unit_limit, defects_limit))
                    # commit after each cell's work to persist changes
                    frappe.db.commit()
                except Exception:
                    frappe.logger("target_scheduler").error(f"Failed upsert for {cell_name} {operation} {ws}: {traceback.format_exc()}")

    except Exception:
        frappe.logger("target_scheduler").error(f"Error processing cell {cell_name}: {traceback.format_exc()}")


# small helpers (copy from your file)
from datetime import datetime as _dt, time as _dt_time
def _parse_time(value):
    if not value:
        return None
    if isinstance(value, _dt_time):
        return value
    try:
        return _dt.strptime(value, "%H:%M:%S").time()
    except Exception:
        try:
            return _dt.strptime(value, "%H:%M").time()
        except Exception:
            return None

def _time_in_range(now_time: _dt_time, start: _dt_time, end: _dt_time) -> bool:
    if start is None or end is None:
        return False
    if start <= end:
        return start <= now_time < end
    return now_time >= start or now_time < end
