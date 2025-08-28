import frappe
from frappe import _

@frappe.whitelist()
def create_production_item(production_item_number, tracking_order, component, tracking_tags, size, quantity,
                           device_id, current_operation, current_workstation,
                           next_operation, next_workstation, bundle_configuration):
    try:
        # Convert tracking_tags to list 
        if isinstance(tracking_tags, str):
            import json
            tracking_tags = json.loads(tracking_tags)

        if not isinstance(tracking_tags, list) or not tracking_tags:
            return {"status": "error", "message": _("tracking_tags must be a non-empty list")}

        # ---------------------------
        # Validation 1 – Handle Tags
        tag_ids = []
        for tag_number in tracking_tags:
            # Check if Tracking Tag exists
            tag_doc = frappe.get_all("Tracking Tag", filters={"tag_number": tag_number}, 
                    fields=["name"])

            if not tag_doc:
                return {
                    "status": "error",
                    "message": _(f"Tracking Tag '{tag_number}' does not exist. ")
                }
            tag_id = tag_doc[0].name
           
            # Check if this tag is already mapped to another Production Item 
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

        # -------------------------------------------------
        # Validation 2 – Bundle Configuration check
        if bundle_configuration:
            # Ensure bundle_config belongs to given tracking_order
            exists_in_order = frappe.get_all(
                "Tracking Order Bundle Configuration",
                filters={"parent": tracking_order, "name": bundle_configuration},
                fields=["number_of_bundles"]
            )
            if not exists_in_order:
                return {
                    "status": "error",
                    "message": _(f"Bundle Configuration {bundle_configuration} does not belong to Tracking Order {tracking_order}")
                }

            number_of_bundles = exists_in_order[0].number_of_bundles or 0

            # Count already activated items for this bundle configuration
            activated_count = frappe.db.count(
                "Production Item",
                {"tracking_order": tracking_order, "bundle_configuration": bundle_configuration, "status": "Activated"}
            )

            # set limit for number_of_bundles that can be linked
            if activated_count > number_of_bundles:
                return {
                    "status": "error",
                    "message": _(f"Bundle Configuration {bundle_configuration} has limit {number_of_bundles}, already activated {activated_count}")
                }

        # Status always "Activated"
        status = "Activated"

        # -------------------------------------------------
        # Create Production Items (one per tag)
        created_items = []

        for tag_id in tag_ids:
            # Create Production Item (let frappe generate unique name)
            doc = frappe.get_doc({
                "doctype": "Production Item",
                "production_item_number": production_item_number,  # keep original number, same for all
                "tracking_order": tracking_order,
                "component": component,
                "device_id": device_id,
                "size": size,
                "quantity": quantity,
                "status": status,
                "current_operation": current_operation,
                "next_operation": next_operation,
                "current_workstation": current_workstation,
                "next_workstation": next_workstation,
                "bundle_configuration": bundle_configuration,
                "tracking_tag": tag_id
            })
            doc.insert()

            # Link in Production Item Tag Map
            frappe.get_doc({
                "doctype": "Production Item Tag Map",
                "production_item": doc.name,
                "tracking_tag": tag_id,
                "is_active": 1,
                "linked_on": frappe.utils.now()
            }).insert()

            created_items.append(doc.name)

        frappe.db.commit()

        return {
            "status": "success",
            "message": _("Production Items created successfully"),
            "names": created_items
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Production Item API Error")
        return {"status": "error", "message": str(e)}
