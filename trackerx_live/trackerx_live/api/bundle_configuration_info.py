import frappe
from frappe import _
from frappe.exceptions import ValidationError

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
                "activation_status": "Ready",
                "work_order": row.work_order,
                "sales_order": row.sales_order,
                "shade": row.shade
                
            }).insert()


# ------------------
# Main API function
@frappe.whitelist()
def get_bundle_configuration_info(tracking_order, component_name):
    try:
        if not tracking_order or not component_name:
            frappe.throw(_("Both Tracking Order and component name are required"), ValidationError)

        tracking_order_doc = frappe.get_doc("Tracking Order", tracking_order)

        # --- Item details ---
        item_info = {}
        if tracking_order_doc.item:
            item_info = frappe.db.get_value(
                "Item",
                tracking_order_doc.item,
                ["name", "custom_style_master", "custom_colour_name", "custom_season"],
                as_dict=True
            )

        # Find component_id
        component_id = None
        for row in tracking_order_doc.tracking_components:
            if row.component_name == component_name:
                component_id = row.name
                break

        if not component_id:
            frappe.throw(_("Component not found"), ValidationError)

        bundle_configs = [
            row for row in tracking_order_doc.bundle_configurations if row.component == component_id
        ]
        if not bundle_configs:
            activate_component_bundle_configuration(tracking_order, component_id)
            tracking_order_doc.reload()

        # Get all component bundle configs
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
                {"tracking_order": tracking_order, "bundle_configuration": bc["name"]}
            )
            completed_count = frappe.db.count(
                "Production Item",
                {"tracking_order": tracking_order, "bundle_configuration": bc["name"], "status": "Completed"}
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
                "product_code": item_info.get("name") if item_info else None,
                "style": item_info.get("custom_style_master") if item_info else None,
                "colour": item_info.get("custom_colour_name") if item_info else None,
                "season": item_info.get("custom_season") if item_info else None,
                "bundle_configurations": bundle_info_list,
                "total_activated_count": total_activated_count,
                "total_pending_activation": total_pending_activation,
                "total_completed_count": total_completed_count,
                "total_number_of_bundles": total_number_of_bundles            
        }

    except frappe.ValidationError as e:
        frappe.log_error(frappe.get_traceback(), "get_bundle_configuration_info() error")
        frappe.local.response.http_status_code = 400
        frappe.db.rollback()
        return {"status": "error", "message": str(e)}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "get_bundle_configuration_info() error")
        frappe.db.rollback()
        frappe.local.response.http_status_code = 500
        return {"status": "error", "message": str(e)}
