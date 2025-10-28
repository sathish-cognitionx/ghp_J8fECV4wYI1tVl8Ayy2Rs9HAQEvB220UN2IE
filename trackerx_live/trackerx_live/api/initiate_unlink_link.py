import frappe
from frappe import _
from trackerx_live.trackerx_live.utils.cell_operator_ws_util import get_cell_operator_by_ws, validate_workstation_for_supported_operation
from trackerx_live.trackerx_live.utils.operation_map_util import OperationMapManager
import json

@frappe.whitelist()
def initiate_unlink_link(tags, workstation, device_id=None, forcefully=False):
    try:
        if isinstance(tags, str):
            try:
                tags = json.loads(tags) if tags.strip().startswith("[") else [tags]
            except Exception:
                tags = [tags]

        if not isinstance(tags, list) or not tags:
            frappe.throw(
                _("Please provide at least one tag_number"),
                frappe.ValidationError
            )

        # Validate workstation
        ws_info_list = get_cell_operator_by_ws(workstation)
        if not ws_info_list:
            frappe.throw(
                _(f"No operation/cell mapped for workstation {workstation}"),
                frappe.ValidationError
            )
        ws_info = ws_info_list[0]
        current_operation = ws_info["operation_name"]
        validate_workstation_for_supported_operation(
            workstation=workstation,
            operation=current_operation,
            api_source="Unlink Link"
        )

        response = {
            "workstation": workstation,
            "device_id": device_id,
            "input": {
                "tags": tags,
                "components": [],
                "forcefully": forcefully,
                "scan_complete": False
            }
        }

        component_map = {}
        settings = frappe.get_single("TrackerX Live Settings")

        # initial component map
        for tag_number in tags:
            try:
                tag_id = frappe.get_value("Tracking Tag", {"tag_number": tag_number}, "name")
                if not tag_id:
                    frappe.throw(
                        _(f"Invalid tag! This tag is not activated: {tag_number}"),
                        frappe.ValidationError
                    )

                prod_item = frappe.get_value(
                    "Production Item",
                    {"tracking_tag": tag_id},
                    ["name", "component", "production_item_number", "quantity", "type", "status", "tracking_order", "tracking_tag"],
                    as_dict=True
                )
                if not prod_item:
                    frappe.throw(
                        _(f"No Production Item found for tag: {tag_number}"),
                        frappe.ValidationError
                    )

                tag_doc = frappe.get_doc("Tracking Tag", prod_item.tracking_tag)
                op_map = OperationMapManager().get_operation_map(prod_item.tracking_order)
                is_final_op = op_map.is_final_operation(current_operation, prod_item.component)

                if not (is_final_op and settings.auto_unlink_at_final_operation and tag_doc.tag_type in ["NFC", "RFID"]):
                    continue

                comp_id = prod_item.component
                comp_name = frappe.get_value("Tracking Component", comp_id, "component_name")

                if comp_id not in component_map:
                    component_map[comp_id] = {
                        "componentId": comp_id,
                        "componentName": comp_name,
                        "tags": [],
                        "production_units": [],
                        "totalTags": 0,
                        "alreadyScanned": 0,
                        "pending": 0,
                        "total_units": 0
                    }

                component_map[comp_id]["tags"].append(tag_number)
                component_map[comp_id]["production_units"].append({
                    "tag": tag_number,
                    "quantity": prod_item.quantity,
                    "production_type": prod_item.type,
                    "production_item_number": prod_item.production_item_number
                })
                component_map[comp_id]["total_units"] += prod_item.quantity

            except Exception as inner_e:
                frappe.log_error(frappe.get_traceback(), f"Error processing tag {tag_number}")
                raise inner_e

        # Compute totalTags, alreadyScanned, pending
        for comp in component_map.values():
            comp["totalTags"] = len(comp["tags"])
        # dynamic adjustment for total_units
        if component_map:
            max_units = max(comp["total_units"] for comp in component_map.values())
            for comp in component_map.values():
                if comp["total_units"] < max_units:
                    comp["totalTags"] += 1

        scan_complete = True
        for comp in component_map.values():
            comp["alreadyScanned"] = len(comp["tags"])
            comp["pending"] = comp["totalTags"] - comp["alreadyScanned"]
            if comp["pending"] > 0:
                scan_complete = False

        response["input"]["components"] = list(component_map.values())
        response["input"]["scan_complete"] = scan_complete

        if scan_complete or forcefully:
            min_units = min(comp["total_units"] for comp in component_map.values()) if component_map else 0
            response["output"] = [{
                "componentId": "",
                "componentName": "new_component",
                "tags": [],
                "production_units": [],
                "totalTags": 1,
                "alreadyScanned": 0,
                "pending": 1,
                "total_units": min_units,
                "forcefully": forcefully,
                "scan_complete": scan_complete
            }]
            if forcefully:
                for comp in component_map.values():
                    for pu in comp["production_units"]:
                        remaining_qty = pu["quantity"] - min_units if pu["quantity"] > min_units else 0
                        if remaining_qty > 0:
                            frappe.db.set_value("Production Item", pu["production_item_number"], "status", "Scrap")
                frappe.db.commit()

        return response

    except frappe.ValidationError as e:
        frappe.log_error(frappe.get_traceback(), "Get Tracking Order Components API Validation Error")
        frappe.local.response.http_status_code = 400
        return {"status": "error", "message": str(e)}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Tracking Order Components API Error")
        frappe.local.response.http_status_code = 500
        return {"status": "error", "message": str(e)}
