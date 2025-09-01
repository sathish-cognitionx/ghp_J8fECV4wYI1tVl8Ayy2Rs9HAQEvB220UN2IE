import frappe
import json
from frappe import _

@frappe.whitelist()
def create_item_scan_log():
    try:
        #JSON body from request
        if frappe.request.data:
            data = json.loads(frappe.request.data)
        else:
            return {"status": "error", "message": "Empty request body"}

        production_item_number = data.get("production_item_number")
        production_item = data.get("production_item")
        operation = data.get("operation")
        workstation = data.get("workstation")
        scanned_by = frappe.session.user
        scan_time =frappe.utils.now_datetime()
        status = "Pass"
        remarks = data.get("remarks")
        tag_number = data.get("tag_number")

        if not tag_number:
            return {"status": "error", "message": _("Tag number is required")}

        # Get Production Item by Production Item Number
        prod_item = frappe.get_all(
            "Production Item",
            filters={"production_item_number": production_item_number},
            fields=["name"]
        )
        if not prod_item:
            return {"status": "error", "message": f"No Production Item found for number {production_item_number}"}

        production_item_id = prod_item[0].name


        # Get tag nummber's id
        tag = frappe.get_all(
            "Tracking Tag",
            filters={"tag_number": tag_number},
            fields=["name"]
        )
        if not tag:
            return {"status": "error", "message": f"No Tracking Tag found for number {tag_number}"}

        tag_id = tag[0].name

        # Check if tag exists
        tag_map = frappe.db.get_value(
            "Production Item Tag Map",
            {"tracking_tag": tag_id},
            ["name", "is_active", "production_item"],
            as_dict=True
        )

        if not tag_map:
            return {"status": "error", "message": _("Tag number {0} not found").format(tag_number)}


        if not tag_map.is_active:
            return {"status": "error", "message": _("Tag {0} exists but is not active").format(tag_number)}


        # Validate- tag is linked with production item number
        mapping_valid = frappe.db.exists(
            "Production Item Tag Map",
            {"production_item": production_item_id, "tracking_tag": tag_id, "is_active": 1}
        )
        if not mapping_valid:
            return {
                "status": "error",
                "message": _("Tag {0} not linked to Production Item {1}").format(tag_number, production_item_number)
            }


        # Create Item Scan Log
        doc = frappe.get_doc({
            "doctype": "Item Scan Log",
            "production_item": production_item,
            "operation": operation,
            "workstation": workstation,
            "scanned_by": scanned_by,
            "scan_time": scan_time,
            "status": status,
            "remarks": remarks
        })
        doc.insert()
        frappe.db.commit()

        return {"status": "success", "message": "Item Scan Log created", "name": doc.name}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Item Scan Log API Error")
        return {"status": "error", "message": str(e)}
