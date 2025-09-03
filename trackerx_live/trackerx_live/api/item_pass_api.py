import frappe
from frappe import _
from frappe.utils import now_datetime

@frappe.whitelist()
def item_pass(scaned_log, remarks=None):
    try:
        # current logged time
        logged_time = now_datetime()

        # Get existing Item Scan Log by ID
        doc = frappe.get_doc("Item Scan Log", scaned_log)

        # Calculate time difference by scan time and log time
        time_to_log = None
        if doc.scan_time:
            time_to_log = logged_time - doc.scan_time
            time_to_log = round(time_to_log.total_seconds(), 2) 

        # Update fields
        doc.logged_time = logged_time
        doc.log_status = "Completed"
        doc.status = "Pass"
        doc.remarks = remarks

        doc.save()
        frappe.db.commit()

        return {
            "status": "success",
            "message": f"Item Scan Log '{scaned_log}' updated as Pass",
            "name": doc.name,
            "time_to_log": f"{time_to_log} seconds"
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Item Scan Log API Error")
        return {"status": "error", "message": str(e)}
