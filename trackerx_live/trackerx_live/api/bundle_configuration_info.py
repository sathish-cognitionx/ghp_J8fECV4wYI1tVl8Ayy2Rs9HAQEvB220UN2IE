import frappe
from frappe import _

#----------------------------------------------------------
# Function for activating component_bundle_configurations
def activate_component_bundle_configuration(tracking_order, component_id):
    tracking_order_doc = frappe.get_doc("Tracking Order", tracking_order)

    for row in tracking_order_doc.bundle_configurations:
        # Always ensure parent rows have source="Configuration"
        frappe.db.set_value(
            "Tracking Order Bundle Configuration",
            row.name,
            {
                "component": component_id,
                "source": "Configuration"
            }
        )

        # Avoid duplicate insertions in component_bundle_configurations
        existing = frappe.db.exists("Tracking Order Bundle Configuration", {
            "parent": tracking_order,
            "parenttype": "Tracking Order",
            "parentfield": "component_bundle_configurations",
            "component": component_id,
            "bc_name": row.bc_name
        })

        if not existing:
            # Insert into component_bundle_configurations with Activation + Ready
            frappe.get_doc({
                "doctype": "Tracking Order Bundle Configuration",
                "parent": tracking_order,
                "parenttype": "Tracking Order",
                "parentfield": "component_bundle_configurations",
                "bc_name": row.bc_name,
                "size": row.size,
                "bundle_quantity": row.bundle_quantity,
                "number_of_bundles": row.number_of_bundles,
                "production_type": row.production_type,
                "component": component_id,
                "parent_bundle_configuration": row.name,
                "source": "Activation",
                "activation_status": "Ready"
            }).insert()


# ------------------
# Main API function
@frappe.whitelist()
def get_bundle_configuration_info(tracking_order, component_name):
    try:
        if not tracking_order or not component_name:
            return {
                "message": {
                    "status": "error",
                    "error": "Both Tracking Order and component name are required"
                }
            }

        tracking_order_doc = frappe.get_doc("Tracking Order", tracking_order)

        # Find component_id from tracking_components
        component_id = None
        for row in tracking_order_doc.tracking_components:
            if row.component_name == component_name:
                component_id = row.name
                break

        if not component_id:
            return {
                "message": {
                    "status": "error",
                    "error": "Component not found "
                }
            }

       
        bundle_configs = [
            row for row in tracking_order_doc.bundle_configurations if row.component == component_id
        ]
        if not bundle_configs:
            activate_component_bundle_configuration(tracking_order, component_id)
            tracking_order_doc.reload()

        # Get all component_bundle_configurations rows
        all_component_bcs = frappe.get_all(
            "Tracking Order Bundle Configuration",
            filters={
                "parent": tracking_order,
                "parenttype": "Tracking Order",
                "parentfield": "component_bundle_configurations",
                "component": component_id
            },
            fields=[
                "name", "bc_name", "size", "bundle_quantity", "number_of_bundles",
                "production_type", "component", "parent_bundle_configuration",
                "source", "activation_status"
            ]
        )

        # Count stats
        bundle_info_list = []
        total_activated_count = 0
        total_pending_activation = 0
        total_completed_count = 0
        total_number_of_bundles = 0

        for bc in all_component_bcs:
            activated_count = frappe.db.count(
                "Production Item",
                {
                    "tracking_order": tracking_order,
                    "bundle_configuration": bc["name"],
                }
            )
            completed_count = frappe.db.count(
                "Production Item",
                {
                    "tracking_order": tracking_order,
                    "bundle_configuration": bc["name"],
                    "status": "Completed"
                }
            )

            pending_activation = (bc.get("number_of_bundles") or 0) - activated_count

            total_activated_count += activated_count
            total_pending_activation += pending_activation
            total_completed_count += completed_count
            total_number_of_bundles += (bc.get("number_of_bundles") or 0)

            bundle_info_list.append({
                "bundle_config_id": bc.get("name"),
                "bc_name": bc.get("bc_name"),
                "size": bc.get("size"),
                "bundle_quantity": bc.get("bundle_quantity"),
                "number_of_bundles": bc.get("number_of_bundles"),
                "component": bc.get("component"),
                "parent_bundle_configuration": bc.get("parent_bundle_configuration"),
                "source": bc.get("source"),
                "activation_status": bc.get("activation_status"),
                "activated_count": activated_count,
                "pending_activation": pending_activation,
                "completed_count": completed_count
            })

        return {      
                "status": "success",
                "component_name": component_name,
                "component_id": component_id,
                "tracking_order": tracking_order,
                "production_type": tracking_order_doc.production_type,
                "bundle_configurations": bundle_info_list,
                "total_activated_count": total_activated_count,
                "total_pending_activation": total_pending_activation,
                "total_completed_count": total_completed_count,
                "total_number_of_bundles": total_number_of_bundles    
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Bundle Configuration Info Error")
        return {
            "message": {
                "status": "error",
                "error": str(e)
            }
        }
