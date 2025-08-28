import frappe
from frappe import _

@frappe.whitelist()
def get_bundle_configuration_info(tracking_order):
    try:
        if not tracking_order:
            return {"status": "error", "message": "Tracking Order is required"}

        # Fetch all bundle configurations linked to the Tracking Order
        bundle_configs = frappe.get_all(
            "Tracking Order Bundle Configuration",
            filters={"parent": tracking_order},
            fields=["name", "bc_name", "size", "bundle_quantity", "number_of_bundles"]
        ) or []

        if not bundle_configs:
            return {
                "status": "error",
                "message": f"No bundle configurations found for Tracking Order {tracking_order}"
            }

        bundle_info_list = []
        total_activated_count = 0
        total_pending_activation = 0
        total_number_of_bundles = 0

        #loop for each bundle config
        for bc in bundle_configs:
            # Count activated production items for each bundle config
            activated_count = frappe.db.count(
                "Production Item",
                {
                    "tracking_order": tracking_order,
                    "bundle_configuration": bc["name"],   
                    "status": "Activated"
                }
            )

            # Calculate pending activations
            pending_activation = (bc.get("number_of_bundles") or 0) - activated_count

            # Update totals
            total_activated_count += activated_count
            total_pending_activation += pending_activation
            total_number_of_bundles += (bc.get("number_of_bundles") or 0)

            # Append bundle info
            bundle_info_list.append({
                "name": bc.get("name"),
                "bc_name": bc.get("bc_name"),
                "size": bc.get("size"),
                "bundle_quantity": bc.get("bundle_quantity"),
                "number_of_bundles": bc.get("number_of_bundles"),
                "activated_count": activated_count,
                "pending_activation": pending_activation
            })

        return {
            "status": "success",
            "tracking_order": tracking_order,
            "bundle_configurations": bundle_info_list,
            "total_activated_count": total_activated_count,
            "total_pending_activation": total_pending_activation,
            "total_number_of_bundles": total_number_of_bundles
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Bundle Configuration Info Error")
        return {"status": "error", "message": str(e)}
