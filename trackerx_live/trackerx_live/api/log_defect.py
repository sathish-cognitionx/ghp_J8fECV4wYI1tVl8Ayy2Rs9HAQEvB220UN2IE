import frappe
import json
from frappe import _

@frappe.whitelist()
def log_defect_api(scan_log_id=None, production_item_id=None, process_id=None, ws_id=None, defects=None):
    """
    API to log defects into Item Scan Log (parent) and Item Scan Log Defect (child table).

    Flow:
    - If scan_log_id is given → update that Item Scan Log.
    - If scan_log_id not given → check if same log exists for (production_item_id + process_id + ws_id).
        - If exists → update that log.
        - Else → create a new log.
    """

    try:
        if not defects:
            return {"error": "Defects list required"}

        # Convert defects JSON string → Python list
        if isinstance(defects, str):
            defects = json.loads(defects)

        parent_doc = None

        # -------------------------
        # CASE 1: scan_log_id explicitly provided
        # -------------------------
        if scan_log_id:
            parent_doc = frappe.get_doc("Item Scan Log", scan_log_id)

        # -------------------------
        # CASE 2: Check if existing log present for same production_item + process + ws
        # -------------------------
        elif production_item_id and process_id and ws_id:
            existing_log = frappe.db.get_value(
                "Item Scan Log",
                {"production_item": production_item_id, "operation": process_id, "workstation": ws_id},
                "name"
            )
            if existing_log:
                parent_doc = frappe.get_doc("Item Scan Log", existing_log)

        # -------------------------
        # CASE 3: Create new log
        # -------------------------
        if not parent_doc:
            if not production_item_id or not process_id or not ws_id:
                return {"error": "Missing required fields for new log creation"}

            parent_doc = frappe.get_doc({
                "doctype": "Item Scan Log",
                "production_item": production_item_id,
                "operation": process_id,
                "workstation": ws_id,
                "scanned_by": frappe.session.user,
                "scan_time": frappe.utils.now_datetime(),
                "status": "Fail",
                "remarks": None,
                "log_status": "Completed"
            })

        # -------------------------
        # Update / Reset Defects
        # -------------------------
        parent_doc.status = "Fail"
        if hasattr(parent_doc, "log_status"):
            parent_doc.log_status = "Completed"

        parent_doc.set("defect_list", [])
        skipped = []

        for defect in defects:
            defect_id = defect.get("defect_id")
            if not defect_id:
                continue

            if frappe.db.exists("Tracking Order Defect Master", defect_id):
                defect_doc = frappe.get_doc("Tracking Order Defect Master", defect_id)
                parent_doc.append("defect_list", {
                    "defect": defect_doc.name,
                    "defect_type": defect_doc.defect_type,
                    "defect_description": defect_doc.defect_description,
                    "severity": defect_doc.severity
                })
            else:
                skipped.append(defect_id)

        # Save changes (insert or update)
        if parent_doc.is_new():
            parent_doc.insert(ignore_permissions=True)
        else:
            parent_doc.save(ignore_permissions=True)

        frappe.db.commit()

        # -------------------------
        # Response
        # -------------------------
        response_defects = []
        for d in parent_doc.defect_list:
            response_defects.append({
                "row_id": d.name,
                "defect_id": d.defect,
                "defect_type": d.defect_type,
                "defect_description": d.defect_description,
                "severity": d.severity
            })

        return {
            "status": "success",
            "message": f"{len(defects)} defects processed successfully",
            "item_scan_log_id": parent_doc.name,
            "defects": response_defects,
            "skipped_defects": skipped
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "log_defect_api_error")
        return {"error": str(e)}