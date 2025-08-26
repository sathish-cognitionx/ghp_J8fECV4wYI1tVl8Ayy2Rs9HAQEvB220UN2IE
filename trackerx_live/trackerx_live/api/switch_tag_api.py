import frappe
import json
from frappe import _

@frappe.whitelist(allow_guest=False)
def switch_tag():
    try:
        # Parse input
        if frappe.request.data:
            data = json.loads(frappe.request.data)
        else:
            return {"status": "error", "message": "Empty request body"}

        current_tag = data.get("current_tag")
        new_tag = data.get("new_tag")

        if not current_tag or not new_tag:
            return {"status": "error", "message": "Both current_tag and new_tag are required"}

        # Find Production Item from current tag
        current_mapping = frappe.get_all(
            "Production Item Tag Map",
            filters={"tracking_tag": current_tag, "is_active": 1},
            fields=["name", "production_item"]
        )

        if not current_mapping:
            return {"status": "error", "message": f"No active mapping found for tag {current_tag}"}

        production_item = current_mapping[0].production_item
        current_mapping_name = current_mapping[0].name

        # Deactivate current mapping
        frappe.db.set_value("Production Item Tag Map", current_mapping_name, "is_active", 0)

        # Create new mapping for new tag
        new_mapping = frappe.get_doc({
            "doctype": "Production Item Tag Map",
            "production_item": production_item,
            "tracking_tag": new_tag,
            "linked_on": frappe.utils.now_datetime(),
            "is_active": 1
        })
        new_mapping.insert()

        frappe.db.commit()

        return {
            "status": "success",
            "message": f"Tag switched from {current_tag} to {new_tag} for Production Item {production_item}",
            "production_item": production_item,
            "old_mapping": current_mapping_name,
            "new_mapping": new_mapping.name
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Switch Tag API Error")
        return {"status": "error", "message": str(e)}
