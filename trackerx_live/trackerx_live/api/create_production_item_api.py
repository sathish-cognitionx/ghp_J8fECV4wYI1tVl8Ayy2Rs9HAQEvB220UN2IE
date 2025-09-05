import frappe
from frappe import _
import json
from frappe.model.naming import make_autoname

@frappe.whitelist()
def create_production_item(tracking_order, component_name, tracking_tags, 
                           device_id, bundle_configuration,
                           current_workstation, next_workstation):
    try:
        # ---------------------------
        # Convert tracking_tags to list 
        if isinstance(tracking_tags, str):
            tracking_tags = json.loads(tracking_tags)

        if not isinstance(tracking_tags, list) or not tracking_tags:
            return {"status": "error", "message": _("tracking_tags must be a non-empty list")}

        # ---------------------------
        # Validation 1 – Handle Tags
        tag_ids = []
        for tag_number in tracking_tags:
            tag_doc = frappe.get_all("Tracking Tag", filters={"tag_number": tag_number}, fields=["name"])
            if not tag_doc:
                return {
                    "status": "error",
                    "message": _(f"Tracking Tag '{tag_number}' does not exist.")
                }

            tag_id = tag_doc[0].name

            # Check if this tag is already mapped
            existing_mapping = frappe.get_all(
                "Production Item Tag Map",
                filters={"tracking_tag": tag_id, "is_active": 1},
                fields=["name", "production_item"]
            )
            if existing_mapping:
                return {
                    "status": "error",
                    "message": _(f"Tracking Tag '{tag_number}' is already mapped to Production Item {existing_mapping[0].production_item}")
                }

            tag_ids.append(tag_id)

        # ---------------------------
        # Validation 2 – Bundle Configuration
        size = None
        bundle_qty = 1  
        bundle_row = None   

        if bundle_configuration:
            exists_in_order = frappe.get_all(
                "Tracking Order Bundle Configuration",
                filters={
                    "parent": tracking_order,
                    "parenttype": "Tracking Order",
                    "parentfield": "component_bundle_configurations",  
                    "name": bundle_configuration
                },
                fields=["bundle_quantity", "number_of_bundles", "size", "component"]
            )
            if not exists_in_order:
                return {
                    "status": "error",
                    "message": _(f"Bundle Configuration {bundle_configuration} does not belong to Tracking Order {tracking_order}")
                }
            bundle_row = exists_in_order[0]
            size = bundle_row.size
            bundle_qty = bundle_row.bundle_quantity or 1  

        # ---------------------------
        # Validation 3 – check Component with bundle and tracking order
        tracking_order_doc = frappe.get_doc("Tracking Order", tracking_order)

        component_id = None
        for row in tracking_order_doc.tracking_components:
            if row.component_name == component_name:
                component_id = row.name
                break

        if not component_id:
            return {
                "status": "error",
                "message": f"No Component found with name {component_name} in Tracking Order {tracking_order}"
            }

        if bundle_row and bundle_row.component and bundle_row.component != component_id:
            return {
                "status": "error",
                "message": _(f"Bundle Configuration {bundle_configuration} is not assigned to Component {component_name}")
            }

        if bundle_row:
            # Check activation limit
            activated_count = frappe.db.count(
                "Production Item",
                {"tracking_order": tracking_order, "bundle_configuration": bundle_configuration}
            )
            if activated_count >= bundle_row.number_of_bundles:
                return {
                    "status": "error",
                    "message": _(f"Bundle Configuration {bundle_configuration} has limit {bundle_row.number_of_bundles} to activate, already activated bundle are {activated_count}")
                }
   
        # ---------------------------
        # Validation 4 – Operations from operation_map
        current_operation = None
        next_operation = None

        for row in tracking_order_doc.operation_map:
            row_dict = row.as_dict()  
            current_operation = row_dict.get("operation")
            next_operation = row_dict.get("next_operation")
            break

        if not current_operation or not next_operation:
            return {
                "status": "error",
                "message": f"Missing current/next operation in Tracking Order {tracking_order}"
            }

        # Status always "Activated"
        status = "Activated"

        # ---------------------------
        # Create Production Items (one per tag)
        created_items = []

        for tag_id in tag_ids:
            production_item_number = make_autoname("PRD-ITEM-.YYYY.-.####") 

            doc = frappe.get_doc({
                "doctype": "Production Item",
                "production_item_number": production_item_number,
                "tracking_order": tracking_order,
                "component": component_id,
                "device_id": device_id,
                "size": size,
                "quantity": bundle_qty,  
                "status": status,
                "current_operation": current_operation,
                "next_operation": next_operation,
                "current_workstation": current_workstation,  
                "next_workstation": next_workstation,
                "bundle_configuration": bundle_configuration,
                "tracking_tag": tag_id
            })
            doc.insert()
            created_items.append(doc.name)

        return {
            "status": "success",
            "message": _("Production Items created successfully"),
            "Production Item names": created_items
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Production Item API Error")
        return {"status": "error", "message": str(e)}
