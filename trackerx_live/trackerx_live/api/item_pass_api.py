import frappe
from frappe import _
from frappe.utils import now_datetime
from frappe.exceptions import ValidationError
from trackerx_live.trackerx_live.utils.production_completion_util import check_and_complete_production_item

@frappe.whitelist()
def item_pass(scan_log_id, remarks=None):
    try:
        if not scan_log_id:
            frappe.throw(_("Scan Log ID is required"), ValidationError)

        # Current logged time
        logged_time = now_datetime()

        # Get existing Item Scan Log by ID
        scan_log_doc = frappe.get_doc("Item Scan Log", scan_log_id)
        if not scan_log_doc:
            frappe.throw(_("Invalid Scan Log ID: {0}").format(scan_log_id), ValidationError)

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

        production_item_doc = frappe.get_doc("Production Item", scan_log_doc.production_item)
        current_operation = scan_log_doc.operation

        # Call the util function
        check_and_complete_production_item(production_item_doc, current_operation)

        return {
            "status": "success",
            "message": f"Item Scan Log '{scan_log_id}' updated as Pass",
            "item_scan_log": scan_log_doc.name,
            "cycle_time": f"{cycle_time} seconds" if cycle_time is not None else None
        }

    except frappe.ValidationError as e:
        frappe.log_error(frappe.get_traceback(), "item_pass() error")
        frappe.local.response.http_status_code = 400
        return {"status": "error", "message": str(e)}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "item_pass() error")
        frappe.local.response.http_status_code = 500
        return {"status": "error", "message": str(e)}
