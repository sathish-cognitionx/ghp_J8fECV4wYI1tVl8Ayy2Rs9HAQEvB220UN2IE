import frappe
from frappe import _
import json
from trackerx_live.trackerx_live.utils.cell_operator_ws_util import get_cell_operator_by_ws
from trackerx_live.trackerx_live.api.bundle_configuration_info import get_bundle_configuration_info

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

#---------------------
# Main function

@frappe.whitelist()
def create_production_item(tracking_order, component_name, tracking_tags,
                           device_id, bundle_configuration,
                           current_workstation,tag_type="RIFD"):
    try:
        # ---------------------------
        # Convert tracking_tags to list
        if isinstance(tracking_tags, str):
            tracking_tags = json.loads(tracking_tags)

        if not isinstance(tracking_tags, list) or not tracking_tags:
            return {"status": "error", "message": _("Invalid tags input")}

        # ---------------------------
        # Validation 1 – Handle Tags
        tag_ids = []
        for tag_number in tracking_tags:
            tag_doc = frappe.get_all("Tracking Tag", filters={"tag_number": tag_number}, fields=["name"])
            
            if not tag_doc:
                # Tag does not exist – create a new one
                new_tag = frappe.get_doc({
                    "doctype": "Tracking Tag",
                    "tag_number": tag_number,
                    "tag_type":tag_type,
                    "activation_time":frappe.utils.now_datetime(),
                    "status": "Active"  
                })
                new_tag.insert()
                tag_id = new_tag.name
            else:
                tag_id = tag_doc[0].name

            # Check if already mapped in Tag Map
            existing_mapping = frappe.get_all(
                "Production Item Tag Map",
                filters={"tracking_tag": tag_id, "is_active": 1},
                fields=["production_item"]
            )
            if existing_mapping:
                return {"status": "error", "message": _(f"Tag {tag_number} already in use")}

            # Check if already linked to another Production Item
            existing_pi = frappe.get_all(
                "Production Item",
                filters={"tracking_tag": tag_id},
                fields=["production_item_number"]
            )
            if existing_pi:
                return {"status": "error", "message": _(f"Tag {tag_number} already linked")}

            tag_ids.append(tag_id)

        # ---------------------------
        # Validation 2 – Bundle Configuration (required always)
        if not bundle_configuration:
            return {"status": "error", "message": _("Bundle configuration required")}

        tracking_order_doc = frappe.get_doc("Tracking Order", tracking_order)

        bundle_row = None
        for row in tracking_order_doc.component_bundle_configurations:
            if str(row.name) == str(bundle_configuration):
                bundle_row = row.as_dict()
                break

        if not bundle_row:
            return {"status": "error", "message": _("Invalid bundle configuration")}

        # ---------------------------
        # Validation 3 – Component check
        component_id = None
        for row in tracking_order_doc.tracking_components:
            if row.component_name == component_name:
                component_id = row.name
                break

        if not component_id:
            return {"status": "error", "message": _("Component not found in order")}

        if bundle_row.component and bundle_row.component != component_id:
            return {"status": "error", "message": _("Bundle not linked to component ")}

        # ---------------------------
        # Validation 4 – Activation limit
        activated_count = frappe.db.count(
            "Production Item",
            {"tracking_order": tracking_order, "bundle_configuration": bundle_configuration}
        )
        if activated_count >= bundle_row.number_of_bundles:
            return {"status": "error", "message": _("Bundle activation limit reached")}

        # ---------------------------
        # Validation 5 – Size handling
        size = None
        if bundle_row.production_type == "Bundle":
            size = bundle_row.size
        elif bundle_row.production_type == "Single Unit":
            size = tracking_order_doc.single_unit_size

        if not size:
            return {"status": "error", "message": _("Size not defined")}

        # ---------------------------
        # Validation 6 – Operation & Physical Cell from workstation
        ws_info_list = get_cell_operator_by_ws(current_workstation)
        if not ws_info_list:
            return {"status": "error", "message": f"No operation/cell mapped for workstation {current_workstation}"}
        ws_info = ws_info_list[0]
        current_operation = ws_info["operation_name"]
        physical_cell = ws_info["cell_id"]

        # Derive next_operation from order operation map
        next_operation = None
        if tracking_order_doc.operation_map:
            first_row = tracking_order_doc.operation_map[0].as_dict()
            next_operation = first_row.get("next_operation")

        if not current_operation or not next_operation:
            return {"status": "error", "message": _("Operation map missing")}

        # ---------------------------
        # Status always "Activated"
        status = "Activated"

        # ---------------------------
        # Create Production Items (one per tag)
        created_items = []
        for tag_id in tag_ids:
            production_item_number = get_next_production_item_number(tracking_order)

            # Create Production Item
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
                "next_workstation": current_workstation,
                "physical_cell": physical_cell,
                "tracking_tag": tag_id,
                "source": "Activation",
                "tracking_status": "Active",
                "unlinked_source": None
            })
            doc.insert()
            created_items.append(doc.name)

            # Link to Production Item Tag Map
            tag_map_doc = frappe.get_doc({
                "doctype": "Production Item Tag Map",
                "production_item": doc.name,
                "tracking_tag": tag_id,
                "linked_on":frappe.utils.now_datetime(),
                "is_active": 1
            })
            tag_map_doc.insert()

            # Create Item Scan Log
            scan_log_doc = frappe.get_doc({
                "doctype": "Item Scan Log",
                "production_item": doc.name,
                "workstation": current_workstation,
                "operation": current_operation,
                "physical_cell": physical_cell,
                "scanned_by": frappe.session.user,
                "scan_time": frappe.utils.now_datetime(),
                "logged_time": frappe.utils.now_datetime(),
                "status": "Activated",
                "production_item_type": "Unit" if bundle_row.production_type=="Single Unit" else "Bundle"
                
            })
            scan_log_doc.insert()


        # --------------------------------
        # Validation 7- Call function for Post-Activation Status Updates
        update_activation_status(tracking_order, bundle_configuration, activated_count, len(tag_ids))

        bundle_info=get_bundle_configuration_info(tracking_order, component_name)


        return {
            "status": "success",
            "message": _("Production items created"),
            "production_items": created_items,
            "bundle_info":bundle_info
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Production Item API Error")
        return {"status": "error", "message": str(e)}
