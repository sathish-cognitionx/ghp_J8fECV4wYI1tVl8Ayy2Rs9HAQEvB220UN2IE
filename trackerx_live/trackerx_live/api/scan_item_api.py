import frappe
from frappe import _

@frappe.whitelist()
def scan_item(tag_number, operation, workstation, remarks=None):
    try:
        # Get tag number's id
        tag = frappe.get_all(
            "Tracking Tag",
            filters={"tag_number": tag_number},
            fields=["name"]
        )
        if not tag:
            return {"status": "error", "message": f"No Tracking Tag found for number {tag_number}"}

        tag_id = tag[0]["name"]

        # Check if tag is active and linked
        tag_map = frappe.db.get_value(
            "Production Item Tag Map",
            {"tracking_tag": tag_id},
            ["name", "is_active", "production_item"],
            as_dict=True
        )

        if not tag_map:
            return {"status": "error", "message": _(f"Tag number {tag_number} not linked to production item")}
        if not tag_map.is_active:
            return {"status": "error", "message": _(f"Tag {tag_number} is deactivated")}

        # Get Production Item details
        production_item_name = tag_map.production_item
        item = frappe.get_doc("Production Item", production_item_name)

        # ---- Cancel duplicates ----
        existing_logs = frappe.get_all(
            "Item Scan Log",
            filters={
                "production_item": production_item_name,
                "operation": operation,
                "workstation": workstation,
                "log_status": ["!=", "Canceled"]
            },
            fields=["name"]
        )

        for log in existing_logs:
            frappe.db.set_value("Item Scan Log", log["name"], "log_status", "Cancelled", update_modified=False)

        # ---- Create new scan log ----
        scan_log_doc = frappe.get_doc({
            "doctype": "Item Scan Log",
            "production_item": production_item_name,
            "operation": operation,
            "workstation": workstation,
            "scanned_by": frappe.session.user,
            "scan_time": frappe.utils.now_datetime(),
            "log_status": "Draft",
            "log_type": "User Scanned",
            "remarks": remarks or ""
        })
        scan_log_doc.insert()

        # Return response
        return {
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
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Scan Item API Error")
        return {"status": "error", "message": str(e)}
