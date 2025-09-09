import frappe
import json
from frappe import _

@frappe.whitelist()
def switch_tag():
    try:
        # Parse input
        if frappe.request.data:
            data = json.loads(frappe.request.data)
        else:
            return {"status": "error", "message": "Empty request body"}

        current_tag_number = data.get("current_tag_number")
        new_tag_number = data.get("new_tag_number")
        new_tag_type = data.get("new_tag_type")

        if not current_tag_number or not new_tag_number or not new_tag_type:
            return {
                "status": "error",
                "message": "Fields required: current_tag_number, new_tag_number, new_tag_type"
            }

        # ----------------------------
        # Get current tag doc
        current_tag = frappe.get_all(
            "Tracking Tag",
            filters={"tag_number": current_tag_number},
            fields=["name"]
        )
        if not current_tag:
            return {"status": "error", "message": f"No Tracking Tag found for number {current_tag_number}"}

        current_tag_id = current_tag[0].name

        # ----------------------------
        # Find active mapping for current tag
      
        current_mapping = frappe.get_all(
            "Production Item Tag Map",
            filters={"tracking_tag": current_tag_id, "is_active": 1},
            fields=["name", "production_item"]
        )

        if not current_mapping:
            return {"status": "error", "message": f"No active mapping found for tag {current_tag_number}"}

        production_item = current_mapping[0].production_item
        current_mapping_name = current_mapping[0].name

        # ----------------------------
        # Get or Create new tag

        new_tag = frappe.get_all(
            "Tracking Tag",
            filters={"tag_number": new_tag_number, "tag_type": new_tag_type},
            fields=["name"]
        )

        if new_tag:
            new_tag_id = new_tag[0].name
        else:
            # Create new Tracking Tag
            new_tag_doc = frappe.get_doc({
                "doctype": "Tracking Tag",
                "tag_number": new_tag_number,
                "tag_type": new_tag_type,
                "status": "Active",
                "activation_time":frappe.utils.now_datetime()
            })
            new_tag_doc.insert()
            new_tag_id = new_tag_doc.name

        # ----------------------------
        # Deactivate current mapping
      
        frappe.db.set_value("Production Item Tag Map", current_mapping_name, "is_active", 0)

        # ----------------------------
        #  Create new mapping
      
        new_mapping = frappe.get_doc({
            "doctype": "Production Item Tag Map",
            "production_item": production_item,
            "tracking_tag": new_tag_id,
            "linked_on": frappe.utils.now_datetime(),
            "is_active": 1
        })
        new_mapping.insert()

        frappe.db.commit()

        return {
            "status": "success",
            "message": f"Tag switched from {current_tag_number} to {new_tag_number} for Production Item {production_item}",
            "production_item": production_item,
            "old_mapping": current_mapping_name,
            "new_mapping": new_mapping.name
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Switch Tag API Error")
        return {"status": "error", "message": str(e)}
