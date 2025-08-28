import frappe
from frappe import _

@frappe.whitelist(allow_guest=False)
def create_production_item(production_item_number, tracking_order, component, tracking_tag, size, quantity,
                           status, current_operation, current_workstation,
                           device_id, next_operation, next_workstation, 
                           bundle_configuration):
    try:
        # Validate if tracking_tag is already mapped in Production Item Tag Map
        if tracking_tag:
            existing_mapping = frappe.db.exists("Production Item Tag Map", {"tracking_tag": tracking_tag})
            if existing_mapping:
                return {
                    "status": "error",
                    "message": _(f"Tracking Tag '{tracking_tag}' is already used by another Production Item")
                }

        # Validate bundle_configuration
        if bundle_configuration and not frappe.db.exists("Tracking Order Bundle Configuration", bundle_configuration):
            return {
                "status": "error",
                "message": _(f"Invalid Bundle Configuration: {bundle_configuration}")
            }

        # Create Production Item doc
        doc = frappe.get_doc({
            "doctype": "Production Item",
            "production_item_number": production_item_number,
            "tracking_order": tracking_order,
            "component": component,
            "device_id": device_id,
            "tracking_tag": tracking_tag,
            "size": size,
            "quantity": quantity,
            "status": status,
            "current_operation": current_operation,
            "next_operation": next_operation,
            "current_workstation": current_workstation,
            "next_workstation": next_workstation,
            "bundle_configuration": bundle_configuration 
        })
        
        doc.insert()
        frappe.db.commit()

        return {
            "status": "success",
            "message": _("Production Item created"),
            "name": doc.name
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Production Item API Error")
        return {
            "status": "error",
            "message": str(e)
        }
