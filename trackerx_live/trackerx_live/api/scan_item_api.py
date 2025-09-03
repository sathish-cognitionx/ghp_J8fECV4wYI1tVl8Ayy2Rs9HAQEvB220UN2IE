import frappe
from frappe import _
import json

@frappe.whitelist()
def scan_item(tag_number,operation,workstation,remarks=None):
    try:
        
        # Get tag nummber's id
        tag = frappe.get_all(
            "Tracking Tag",
            filters={"tag_number": tag_number},
            fields=["name"]
        )
        if not tag:
            return {"status": "error", "message": f"No Tracking Tag found for number {tag_number}"}

        tag_id = tag[0].name

        # Check if tag is active and linked
        tag_map = frappe.db.get_value(
            "Production Item Tag Map",
            {"tracking_tag": tag_id},
            ["name", "is_active", "production_item"],
            as_dict=True
        )

        if not tag_map:
            return {"status": "error", "message": _("Tag number {0} not linked to any production item").format(tag_number)}
        if not tag_map.is_active:
            return {"status": "error", "message": _("Tag {0} exists but is not active").format(tag_number)}

        # Get Production Item details
        production_item_name = tag_map.production_item
        item = frappe.get_doc("Production Item", production_item_name)

        #create item scan log 
        scanned_by = frappe.session.user
        scan_time =frappe.utils.now_datetime()

        doc = frappe.get_doc({
            "doctype": "Item Scan Log",
            "production_item": production_item_name,
            "operation": operation,
            "workstation": workstation,
            "scanned_by": scanned_by,
            "scan_time": scan_time,
            "log_status":"Draft" ,
            "log_type":"User Scanned",
            "remarks": remarks
        })
        doc.insert()
        frappe.db.commit()


        # Return response
        return {"status_of_item": "Item Scaned",
                "item sacn log scan name": doc.name,

                "production_item_number": item.production_item_number,
                "tracking_order": item.tracking_order,
                "bundle_configuration": item.bundle_configuration,
                "tracking_tag":item.tracking_tag,
                "component": item.component,
                "size": item.size,
                "device_id":item.device_id,
                "quantity": item.quantity,
                "status": item.status,
                "current_operation": item.current_operation,
                "next_operation": item.next_operation,
                "current_workstation":item.current_workstation,
                "next_workstation":item.next_workstation
        }
    

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), " Scan Item API Error")
        return {"status": "error", "message": str(e)}