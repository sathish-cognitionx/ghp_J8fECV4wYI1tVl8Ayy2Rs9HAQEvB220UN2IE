import frappe
import json
from frappe import _
from trackerx_live.trackerx_live.utils.cell_operator_ws_util import get_cell_operator_by_ws

@frappe.whitelist()
def bulk_scan_tags(tag_numbers, workstation, remarks=None):
    """
    Bulk scan API:
    - Input: list of tag_numbers (JSON string or Python list), and workstation.
    - Operation and physical cell are derived from workstation.
    - For each tag, find its Production Item and create Item Scan Log 
      (idempotent per production item + operation + workstation + user).
    - Returns structured response for frontend.
    """
    try:
        # Convert tag_numbers if passed as string
        if isinstance(tag_numbers, str):
            try:
                tag_numbers = json.loads(tag_numbers)
            except Exception:
                tag_numbers = [tag_numbers]

        if not isinstance(tag_numbers, list) or not tag_numbers:
            return {"status": "error", "message": _("tag_numbers must be a non-empty list")}

        # --- Step 0: Get operation + physical cell from workstation ---
        ws_info_list = get_cell_operator_by_ws(workstation)
        if not ws_info_list:
            return {
                "status": "error",
                "message": f"No operation/cell mapped for workstation {workstation}"
            }
        ws_info = ws_info_list[0]
        operation = ws_info["operation_name"]
        physical_cell = ws_info["cell_id"]

        scanned_by = frappe.session.user
        scan_time = frappe.utils.now_datetime()
        status = "Pass"

        created_logs = []
        errors = []
        skipped = []

        for tag_number in tag_numbers:
            # Get Tag
            tag = frappe.get_all(
                "Tracking Tag",
                filters={"tag_number": tag_number},
                fields=["name"]
            )
            if not tag:
                errors.append({
                    "tag": tag_number,
                    "reason": "Tag not found"
                })
                continue

            tag_id = tag[0].name

            # Get mapped Production Item
            tag_map = frappe.db.get_value(
                "Production Item Tag Map",
                {"tracking_tag": tag_id, "is_active": 1},
                ["production_item"],
                as_dict=True
            )
            if not tag_map:
                errors.append({
                    "tag": tag_number,
                    "reason": "Tag not linked"
                })
                continue

            production_item = tag_map.production_item
            prod_item_doc = frappe.get_doc("Production Item", production_item)

            # check if Already scanned (same production item + op + ws + user)
            existing_log = frappe.db.exists(
                "Item Scan Log",
                {
                    "production_item": production_item,
                    "operation": operation,
                    "workstation": workstation,
                    "scanned_by": scanned_by,
                }
            )
            if existing_log:
                skipped.append({
                    "tag": tag_number,
                    "reason": "Already scanned",
                    "log": existing_log
                })
                continue

            # Create Item Scan Log
            doc = frappe.get_doc({
                "doctype": "Item Scan Log",
                "production_item": production_item,
                "operation": operation,
                "workstation": workstation,
                "physical_cell": physical_cell,
                "scanned_by": scanned_by,
                "scan_time": scan_time,
                "status": status,
                "remarks": remarks,
                "log_status": "Completed",
                "log_type": "User Scanned"
            })
            doc.insert()
            created_logs.append({
                "tag": tag_number,
                "production_item": production_item,
                "log_name": doc.name
            })

        if created_logs: 
            frappe.db.commit()

        return {
            "status": "success" if created_logs else "error",
            "summary": {
                "total_tags": len(tag_numbers),
                "created_count": len(created_logs),
                "skipped_count": len(skipped),
                "error_count": len(errors),
            },
            "created_logs": created_logs,
            "skipped": skipped,
            "errors": errors
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Bulk Scan Tags API Error")
        return {"status": "error", "message": str(e)}
