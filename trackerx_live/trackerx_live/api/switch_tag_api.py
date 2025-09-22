import frappe
from trackerx_live.trackerx_live.utils.cell_operator_ws_util import get_cell_operator_by_ws, validate_workstation_for_supported_operation

@frappe.whitelist()
def switch_tag(current_tag_number, new_tag_number, new_tag_type, 
                workstation, device_id=None):
    try:
        # Validate mandatory fields
        if not current_tag_number or not new_tag_number or not new_tag_type:
            frappe.throw("Fields required: current_tag_number, new_tag_number, new_tag_type")

        # Get current tag doc
        current_tag = frappe.get_all(
            "Tracking Tag",
            filters={"tag_number": current_tag_number},
            fields=["name"]
        )
        if not current_tag:
            frappe.throw(f"No Tracking Tag found for number {current_tag_number}")
        current_tag_id = current_tag[0].name

        # Find active mapping for current tag
        current_mapping = frappe.get_all(
            "Production Item Tag Map",
            filters={"tracking_tag": current_tag_id, "is_active": 1},
            fields=["name", "production_item"]
        )
        if not current_mapping:
            frappe.throw(f"No active mapping found for tag {current_tag_number}")

        production_item = current_mapping[0].production_item
        current_mapping_name = current_mapping[0].name

        # Fetch current operation for the production item
        production_item_doc = frappe.get_doc("Production Item", production_item)
        current_operation = production_item_doc.current_operation

        # Validate workstation for operation
        validate_workstation_for_supported_operation(workstation=workstation, operation=current_operation, api_source="Switch")        

        # Get or create new tag
        new_tag = frappe.get_all(
            "Tracking Tag",
            filters={"tag_number": new_tag_number, "tag_type": new_tag_type},
            fields=["name"]
        )
        if new_tag:
            new_tag_id = new_tag[0].name
        else:
            new_tag_doc = frappe.get_doc({
                "doctype": "Tracking Tag",
                "tag_number": new_tag_number,
                "tag_type": new_tag_type,
                "status": "Active",
                "activation_time": frappe.utils.now_datetime()
            })
            new_tag_doc.insert()
            new_tag_id = new_tag_doc.name

        # Deactivate current mapping
        frappe.db.set_value("Production Item Tag Map", current_mapping_name, "is_active", 0)

        # Create new mapping
        new_mapping = frappe.get_doc({
            "doctype": "Production Item Tag Map",
            "production_item": production_item,
            "tracking_tag": new_tag_id,
            "linked_on": frappe.utils.now_datetime(),
            "is_active": 1
        })
        new_mapping.insert()

        # Log in Item Scan Log
        item_scan_log = frappe.get_doc({
            "doctype": "Item Scan Log",
            "production_item": production_item,
            "workstation": workstation,
            "operation": current_operation,
            "physical_cell": production_item_doc.physical_cell,
            "scanned_by": frappe.session.user,
            "scan_time": frappe.utils.now_datetime(),
            "logged_time": frappe.utils.now_datetime(),
            "status": "Tag Switched",
            "remarks": f"Tag switched from {current_tag_number} to {new_tag_number}"
        })
        item_scan_log.insert()

        return {
            "status": "success",
            "message": f"Tag switched from {current_tag_number} to {new_tag_number}",
            "production_item": production_item,
            "old_mapping": current_mapping_name,
            "new_mapping": new_mapping.name,
            "item_scan_log": item_scan_log.name
        }

    except frappe.ValidationError as e:
        frappe.log_error(frappe.get_traceback(), "switch_tag() error")
        frappe.local.response.http_status_code = 400
        return {"status": "error", "message": str(e)}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "switch_tag() error")
        frappe.local.response.http_status_code = 500
        return {"status": "error", "message": str(e)}
