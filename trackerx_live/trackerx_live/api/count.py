import frappe
import json
from frappe import _
from trackerx_live.trackerx_live.utils.production_completion_util import check_and_complete_production_item
from trackerx_live.trackerx_live.api.counted_info import get_counted_info

@frappe.whitelist()
def count_tags(tag_numbers,ws_name, period="today"):
    try:
        # Convert tag_numbers if passed as JSON string
        if isinstance(tag_numbers, str):
            try:
                tag_numbers = json.loads(tag_numbers)
            except Exception:
                tag_numbers = [tag_numbers]

        if not isinstance(tag_numbers, list) or not tag_numbers:
            return {"status": "error", "message": _("tag_numbers must be a non-empty list")}

        updated_logs = []
        skipped = []
        errors = []

        for tag_number in tag_numbers:
            # Get Tracking Tag
            tag = frappe.get_all(
                "Tracking Tag",
                filters={"tag_number": tag_number},
                fields=["name"]
            )
            if not tag:
                errors.append({"tag": tag_number, "reason": "Tag not found"})
                continue
            tag_id = tag[0].name

            # Get Production Item linked to tag
            production_item_name = frappe.get_value(
                "Production Item",
                {"tracking_tag": tag_id},
                "name"
            )
            if not production_item_name:
                errors.append({"tag": tag_number, "reason": "No Production Item linked"})
                continue

            production_item_doc = frappe.get_doc("Production Item", production_item_name)

            # Get all scan logs for this Production Item
            scan_logs = frappe.get_all(
                "Item Scan Log",
                filters={"production_item": production_item_name},
                fields=["name", "status", "operation"]
            )

            if not scan_logs:
                skipped.append({"tag": tag_number, "reason": "Item Scan Log not found"})
                continue

            # Update each scan log
            for log in scan_logs:
                doc = frappe.get_doc("Item Scan Log", log["name"])
                doc.status = "Counted"
                doc.save(ignore_permissions=True)
                updated_logs.append({
                    "tag": tag_number,
                    "log": doc.name
                })

                current_operation = log.get("operation")
                check_and_complete_production_item(production_item_doc, current_operation)

        if updated_logs:
            frappe.db.commit()

        # Call counted_info for the workstation 
        counted_info_data = None   
        counted_info_data = get_counted_info(ws_name, period)

        # Add total_count for today and current hour
        today_info = get_counted_info(ws_name, "today")
        current_hour_info = get_counted_info(ws_name, "current_hour")

        return {
            "status": "success" if updated_logs else "error",
            "message": {
                "total_tags": len(tag_numbers),
                "updated_count": len(updated_logs),
                "skipped_count": len(skipped),
                "error_count": len(errors),
                "today_count": today_info.get("total_count", 0),
                "current_hour_count": current_hour_info.get("total_count", 0),
                "counted_info": counted_info_data
            },
            "updated_logs": updated_logs,
            "skipped": skipped,
            "errors": errors
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Update Scan Logs by Tags API Error")
        return {"status": "error", "message": str(e)}
