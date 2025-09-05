import frappe
from frappe import _
import json
from frappe.model.naming import make_autoname

#------------------------------------------------
# function for production_item_number autoname 
def get_next_production_item_number(tracking_order):
    # Get latest production_item_number for this tracking_order
    last_number = frappe.db.sql("""
        SELECT MAX(production_item_number)
        FROM `tabProduction Item`
        WHERE tracking_order = %s
    """, tracking_order)[0][0]

    if last_number:
        last_counter = int(last_number.split("-")[-1])  # last 4 digits
        next_counter = last_counter + 1
    else:
        next_counter = 1

    return f"{tracking_order}-{next_counter:04d}"

#---------------------------------------
# function to update activation statuses
def update_activation_status(tracking_order, bundle_configuration,
                             activated_count, new_items_count):
    # check If current bundle reached its activation limit 
    if activated_count + new_items_count >= frappe.db.get_value(
        "Tracking Order Bundle Configuration",
        bundle_configuration,
        "number_of_bundles"
    ):
        frappe.db.set_value(
            "Tracking Order Bundle Configuration",
            bundle_configuration,
            "activation_status",
            "Completed"
        )

    # check If ALL component bundle configurations are Completed 
    total_rows = frappe.db.count(
        "Tracking Order Bundle Configuration",
        {
            "parent": tracking_order,
            "parenttype": "Tracking Order",
            "parentfield": "component_bundle_configurations"
        }
    )

    completed_rows = frappe.db.count(
        "Tracking Order Bundle Configuration",
        {
            "parent": tracking_order,
            "parenttype": "Tracking Order",
            "parentfield": "component_bundle_configurations",
            "activation_status": "Completed"
        }
    )
    if total_rows > 0 and total_rows == completed_rows:
        frappe.db.set_value(
                "Tracking Order", tracking_order,
                "activation_status", "Completed"
            )



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

            # Check if already mapped
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
        # Validation 2 – Bundle Configuration (required always)
        if not bundle_configuration:
            return {
                "status": "error",
                "message": _("Bundle Configuration is required")
            }

        bundle_row = frappe.get_all(
            "Tracking Order Bundle Configuration",
            filters={
                "parent": tracking_order,
                "parenttype": "Tracking Order",
                "parentfield": "component_bundle_configurations",
                "name": bundle_configuration
            },
            fields=["bundle_quantity", "number_of_bundles", "size", "component", "production_type"]
        )
        if not bundle_row:
            return {
                "status": "error",
                "message": _(f"Bundle Configuration {bundle_configuration} does not belong to Tracking Order {tracking_order}")
            }
        bundle_row = bundle_row[0]

        # ---------------------------
        # Validation 3 – Component check
        tracking_order_doc = frappe.get_doc("Tracking Order", tracking_order)
        component_id = None
        for row in tracking_order_doc.tracking_components:
            if row.component_name == component_name:
                component_id = row.name
                break

        if not component_id:
            return {
                "status": "error",
                "message": _(f"No Component found with name {component_name} in Tracking Order {tracking_order}")
            }

        if bundle_row.component and bundle_row.component != component_id:
            return {
                "status": "error",
                "message": _(f"Bundle Configuration {bundle_configuration} is not assigned to Component {component_name}")
            }

        # ---------------------------
        # Validation 4 – Activation limit
        activated_count = frappe.db.count(
            "Production Item",
            {"tracking_order": tracking_order, "bundle_configuration": bundle_configuration}
        )
        if activated_count >= bundle_row.number_of_bundles:
            return {
                "status": "error",
                "message": _(f"Bundle Configuration {bundle_configuration} has limit {bundle_row.number_of_bundles}, already activated {activated_count}")
            }

        # ---------------------------
        # Validation 5 – Size handling
        size = None
        if bundle_row.production_type == "Bundle":
            size = bundle_row.size
        elif bundle_row.production_type == "Single Unit":
            size = tracking_order_doc.single_unit_size

        if not size:
            return {
                "status": "error",
                "message": _("Size must be set (either from bundle or single unit)")
            }

        # ---------------------------
        # Validation 6 – Operation Map
        current_operation, next_operation = None, None
        if tracking_order_doc.operation_map:
            first_row = tracking_order_doc.operation_map[0].as_dict()
            current_operation = first_row.get("operation")
            next_operation = first_row.get("next_operation")

        if not current_operation or not next_operation:
            return {
                "status": "error",
                "message": _(f"Missing current/next operation in Tracking Order {tracking_order}")
            }

        # ---------------------------
        # Status always "Activated"
        status = "Activated"

        # ---------------------------
        # Create Production Items (one per tag)
        created_items = []
        for tag_id in tag_ids:
            production_item_number = get_next_production_item_number(tracking_order)

            doc = frappe.get_doc({
                "doctype": "Production Item",
                "production_item_number": production_item_number,
                "tracking_order": tracking_order,
                "bundle_configuration": bundle_configuration,
                "component": component_id,
                "device_id": device_id,
                "size": size,
                "quantity": bundle_row.bundle_quantity or 1,
                "status": status,
                "current_operation": current_operation,
                "next_operation": next_operation,
                "current_workstation": current_workstation,
                "next_workstation": next_workstation,
                "tracking_tag": tag_id,
                "source": "Activation",
                "tracking_status": "Active",
                "unlinked_source": None
            })
            doc.insert()
            created_items.append(doc.name)

        # --------------------------------
        # Validation 7- Call function for Post-Activation Status Updates
        update_activation_status(tracking_order, bundle_configuration, activated_count, len(tag_ids))


        return {
            "status": "success",
            "message": _("Production Items created successfully"),
            "Production Item names": created_items
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Production Item API Error")
        return {"status": "error", "message": str(e)}
