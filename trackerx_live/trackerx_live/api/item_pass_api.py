import frappe
from frappe import _
from frappe.utils import now_datetime

@frappe.whitelist()
def item_pass(scan_log_id, remarks=None):
    try:
        # current logged time
        logged_time = now_datetime()

        # Get existing Item Scan Log by ID
        scan_log_doc = frappe.get_doc("Item Scan Log", scan_log_id)

        # Calculate cycle time
        cycle_time = None
        if scan_log_doc.scan_time:
            cycle_time = (logged_time - scan_log_doc.scan_time).total_seconds()
            cycle_time = round(cycle_time, 2)

        # Update fields
        scan_log_doc.logged_time = logged_time
        scan_log_doc.log_status = "Completed"
        scan_log_doc.status = "Pass"
        scan_log_doc.remarks = remarks or ""

        scan_log_doc.save()

        return {
            "status": "success",
            "message": f"Item Scan Log '{scan_log_id}' updated as Pass",
            "item_scan_log": scan_log_doc.name,
            "cycle_time": f"{cycle_time} seconds" if cycle_time is not None else None
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Item Scan Log API Error")
        return {"status": "error", "message": str(e)}
