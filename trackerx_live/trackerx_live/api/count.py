import frappe
import json
from frappe import _
from frappe.utils import now_datetime
from trackerx_live.trackerx_live.utils.production_completion_util import check_and_complete_production_item
from trackerx_live.trackerx_live.api.counted_info import get_counted_info

@frappe.whitelist()
def count_tags(tag_numbers, ws_name):
    try:
        if not ws_name:
            frappe.throw(
                _("No mapping found for workstation: {0}").format(ws_name),
                exc=frappe.ValidationError
            )

        # Convert tag_numbers if passed as JSON string
        if isinstance(tag_numbers, str):
            try:
                tag_numbers = json.loads(tag_numbers)
            except Exception:
                tag_numbers = [tag_numbers]

        if not isinstance(tag_numbers, list) or not tag_numbers:
            frappe.throw(_("tag_numbers must be a non-empty list"), frappe.ValidationError)

        created_logs = []
        errors = []

        for tag_number in tag_numbers:
            # --- Validate Tag ---
            tag = frappe.get_all(
                "Tracking Tag",
                filters={"tag_number": tag_number},
                fields=["name"]
            )
            if not tag:
                errors.append({"tag": tag_number, "reason": "Tag not found"})
                continue

            tag_id = tag[0]["name"]

            tag_map = frappe.db.get_value(
                "Production Item Tag Map",
                {"tracking_tag": tag_id},
                ["name", "is_active", "production_item"],
                as_dict=True
            )

            if not tag_map:
                errors.append({"tag": tag_number, "reason": "Tag not linked"})
                continue
            if not tag_map.is_active:
                errors.append({"tag": tag_number, "reason": "Tag is deactivated"})
                continue

            production_item_doc = frappe.get_doc("Production Item", tag_map.production_item)

            current_operation = production_item_doc.current_operation
            current_workstation = production_item_doc.current_workstation

            if not current_operation or not current_workstation:
                errors.append({"tag": tag_number, "reason": "Missing operation/workstation"})
                continue

            # Create a new scan log with status Counted
            new_log = frappe.get_doc({
                "doctype": "Item Scan Log",
                "production_item": production_item_doc.name,
                "operation": current_operation,
                "workstation": current_workstation,
                "physical_cell": production_item_doc.physical_cell,
                "scanned_by": frappe.session.user,
                "scan_time": now_datetime(),
                "logged_time": now_datetime(),
                "status": "Counted",
                "log_status": "Completed",
                "log_type": "User Scanned",
                "production_item_type": production_item_doc.type,
            })
            new_log.insert(ignore_permissions=True)

            created_logs.append({
                "tag": tag_number,
                "log": new_log.name
            })

            # Check and complete production item
            check_and_complete_production_item(production_item_doc, current_operation)

        if created_logs:
            frappe.db.commit()

        if not created_logs and errors:
            frappe.throw(_("All tags failed validation"), exc=frappe.ValidationError)

        # Call counted_info for the workstation 
        counted_info_data = get_counted_info(ws_name)
        today_info = get_counted_info(ws_name, "today")
        current_hour_info = get_counted_info(ws_name, "current_hour")

        return {
            "status": "success",
            "total_tags": len(tag_numbers),
            "logged_tags": len(created_logs),
            "error_tags": len(errors),
            "today_count": today_info.get("total_count", 0),
            "current_hour_count": current_hour_info.get("total_count", 0),
            "counted_info": counted_info_data,
            "logged_tags_info": created_logs,
            "errors_info": errors
        }

    except Exception:
        frappe.throw(_("Update Scan Logs by Tags API failed"), exc=frappe.ValidationError)
