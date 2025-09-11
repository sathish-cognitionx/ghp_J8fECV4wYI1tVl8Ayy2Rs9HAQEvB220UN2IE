import frappe
from frappe import _
from trackerx_live.trackerx_live.utils.cell_operator_ws_util import get_cell_operator_by_ws
import json

@frappe.whitelist()
def scan_item(tags, workstation, remarks=None):
    """
    Create Item Scan Log(s) for one or multiple tags.
    - tags can be a single tag_number (string) OR a list of tag_numbers (JSON/string).
    - Only workstation is passed in; operation & physical cell are derived from workstation.
    """
    try:
        # If tags is string, convert to list
        if isinstance(tags, str):
            try:
                tags = json.loads(tags) if tags.strip().startswith("[") else [tags]
            except Exception:
                tags = [tags]

        if not isinstance(tags, list) or not tags:
            return {"status": "error", "message": "Please provide at least one tag_number"}

        results = []

        # --- Step 0: Fetch operation + physical cell from workstation ---
        ws_info_list = get_cell_operator_by_ws(workstation)
        if not ws_info_list:
            return {
                "status": "error",
                "message": f"No operation/cell mapped for workstation {workstation}"
            }
        ws_info = ws_info_list[0]
        operation = ws_info["operation_name"]
        physical_cell = ws_info["cell_id"]

        for tag_number in tags:
            try:
                # --- Step 1: Validate Tag ---
                tag = frappe.get_all(
                    "Tracking Tag",
                    filters={"tag_number": tag_number},
                    fields=["name"]
                )
                if not tag:
                    results.append({
                        "tag": tag_number,
                        "status": "error",
                        "message": f"No Tracking Tag found"
                    })
                    continue

                tag_id = tag[0]["name"]

                tag_map = frappe.db.get_value(
                    "Production Item Tag Map",
                    {"tracking_tag": tag_id},
                    ["name", "is_active", "production_item"],
                    as_dict=True
                )

                if not tag_map:
                    results.append({
                        "tag": tag_number,
                        "status": "error",
                        "message": "Tag not linked to any Production Item"
                    })
                    continue
                if not tag_map.is_active:
                    results.append({
                        "tag": tag_number,
                        "status": "error",
                        "message": "Tag is deactivated"
                    })
                    continue

                # --- Step 2: Get Production Item ---
                production_item_name = tag_map.production_item
                item = frappe.get_doc("Production Item", production_item_name)

                # --- Step 3: Cancel existing logs for same op/ws ---
                existing_logs = frappe.get_all(
                    "Item Scan Log",
                    filters={
                        "production_item": production_item_name,
                        "operation": operation,
                        "workstation": workstation,
                        "log_status": ["!=", "Cancelled"]
                    },
                    fields=["name"]
                )
                for log in existing_logs:
                    frappe.db.set_value(
                        "Item Scan Log",
                        log["name"],
                        "log_status",
                        "Cancelled",
                        update_modified=False
                    )

                # --- Step 4: Create new scan log ---
                scan_log_doc = frappe.get_doc({
                    "doctype": "Item Scan Log",
                    "production_item": production_item_name,
                    "operation": operation,
                    "workstation": workstation,
                    "physical_cell": physical_cell,
                    "scanned_by": frappe.session.user,
                    "scan_time": frappe.utils.now_datetime(),
                    "logged_time": frappe.utils.now_datetime(),
                    "log_status": "Draft",
                    "log_type": "User Scanned",
                    "remarks": remarks or ""
                })
                scan_log_doc.insert()

                results.append({
                    "tag": tag_number,
                    "status": "success",
                    "message": "Item Scanned",
                    "scan_log_id": scan_log_doc.name,
                    "production_item_number": item.production_item_number,
                    "tracking_order": item.tracking_order,
                    "bundle_configuration": item.bundle_configuration,
                    "component": item.component,
                    "size": item.size,
                    "quantity": item.quantity,
                    "status": item.status,
                })

            except Exception as inner_e:
                results.append({
                    "tag": tag_number,
                    "status": "error",
                    "message": str(inner_e)
                })

        return {
            "status": "completed",
            "total_tags": len(tags),
            "results": results
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Scan Item API Error")
        return {"status": "error", "message": str(e)}
