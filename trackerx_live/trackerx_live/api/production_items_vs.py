import frappe, json
from frappe import _

@frappe.whitelist(allow_guest=True)
def create_production_item():
    try:
        # Try to parse JSON body
        if frappe.request and frappe.request.data:
            try:
                data = json.loads(frappe.request.data)
            except Exception:
                data = frappe.form_dict
        else:
            data = frappe.form_dict

        doc = frappe.get_doc({
            "doctype": "Production Item",
            "production_item_number": data.get("production_item_number"),
            "tracking_order": data.get("tracking_order"),
            "bundle_configuration": data.get("bundle_configuration"),
            "component": data.get("component"),
            "device_id": data.get("device_id"),
            "size": data.get("size"),
            "quantity": data.get("quantity"),
            "status": data.get("status"),
            "current_operation": data.get("current_operation"),
            "next_operation": data.get("next_operation"),
            "current_workstation": data.get("current_workstation"),
            "next_workstation": data.get("next_workstation"),
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()

        return {"status": "success", "message": _("Production Item created"), "name": doc.name}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Production Item API Error")
        return {"status": "error", "message": str(e)}

