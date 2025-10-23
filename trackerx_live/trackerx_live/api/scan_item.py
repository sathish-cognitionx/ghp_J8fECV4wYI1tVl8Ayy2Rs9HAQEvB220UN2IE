import frappe
from frappe import _
from trackerx_live.trackerx_live.utils.cell_operator_ws_util import get_cell_operator_by_ws, validate_workstation_for_supported_operation
import json

from trackerx_live.trackerx_live.utils.trackerx_live_settings_util import TrackerXLiveSettings
from trackerx_live.trackerx_live.utils.sequence_of_operation import SequenceOfOpeationUtil

@frappe.whitelist()
def scan_item(tags, workstation, scan_source="QC",remarks=None):
    try:
        # If tags is string, convert to list
        if isinstance(tags, str):
            try:
                tags = json.loads(tags) if tags.strip().startswith("[") else [tags]
            except Exception:
                tags = [tags]

        if not isinstance(tags, list) or not tags:
            frappe.throw(
                f"Please provide at least one tag_number", 
                frappe.ValidationError
            )

        results = []

        # Fetch operation + physical cell from workstation ---
        ws_info_list = get_cell_operator_by_ws(workstation)
        if not ws_info_list:
            frappe.throw(
                f"No operation/cell mapped for workstation {workstation}",
                frappe.ValidationError
            )
            
        ws_info = ws_info_list[0]
        operation = ws_info["operation_name"]
        physical_cell = ws_info["cell_id"]


        for tag_number in tags:
            try:
                # --- Validate Tag ---
                tag = frappe.get_all(
                    "Tracking Tag",
                    filters={"tag_number": tag_number},
                    fields=["name"]
                )
                if not tag:
                    frappe.throw(
                        f"Invalid tag! This tag is not activated, Please use activated tag. Contact your supervisor",
                        frappe.ValidationError
                    )

                tag_id = tag[0]["name"]

                tag_map = frappe.db.get_value(
                    "Production Item Tag Map",
                    {"tracking_tag": tag_id, "is_active": True},
                    ["name", "is_active", "production_item"],
                    as_dict=True
                )

                if not tag_map or not tag_map.is_active:
                    frappe.throw(
                        f"Invalid Tag! Tag already unlinked, Please use activated tag. Contact your supervisor"
                    )


                

                # --- Get Production Item ---
                production_item_name = tag_map.production_item

                result = SequenceOfOpeationUtil.can_this_item_scan_in_this_operation(production_item=production_item_name, workstation=workstation, operation=operation, physical_cell=physical_cell)
                if not result["is_allowed"]:
                    frappe.throw(
                        f"This item already scanned in this operation",
                        frappe.ValidationError
                    )

                production_item_doc = frappe.get_doc("Production Item", production_item_name)

                production_item_bc_doc = frappe.get_doc("Tracking Order Bundle Configuration", production_item_doc.bundle_configuration)

                operation_doc = frappe.get_doc("Operation", operation)

                operation_group_doc = frappe.get_doc("Operation Group", operation_doc.custom_operation_group)

                tracking_order_doc = frappe.get_doc("Tracking Order", production_item_doc.tracking_order)

                fg_item_doc = frappe.get_doc("Item", tracking_order_doc.item)

                style_master_doc = frappe.get_doc("Style Master", fg_item_doc.custom_style_master)

                physical_cell_doc = frappe.get_doc("Physical Cell", physical_cell)

                from trackerx_live.trackerx_live.utils.operation_map_util import OperationMapManager
                operation_map_manager = OperationMapManager()
                operation_map = operation_map_manager.get_operation_map(tracking_order_number=tracking_order_doc.name)
                prev_operations = operation_map.get_all_previous_operations(current_operation=operation, component=production_item_doc.component,sequence_no=1)

                last_scan_log_doc = frappe.get_doc("Item Scan Log", production_item_doc.last_scan_log) if production_item_doc.last_scan_log else None

                is_defective_last = last_scan_log_doc.status in ('QC Rework', 'QC Reject', 'QC Recut') if last_scan_log_doc else False
                is_rework_last = last_scan_log_doc.status in ('QC Rework') if last_scan_log_doc else False

                if is_defective_last and not is_rework_last:
                    frappe.throw(
                        f"This Unit/Bundle is rejected by QC at {last_scan_log_doc.current_operation}"
                    )

                
                if production_item_doc.tracking_status == "Defective Unit Tagging" and not is_defective_last:
                    frappe.throw(
                        f"This is Defective Unit tagged Item, cannot be scaneed unless its a rework."
                    )
                # validate_workstation_for_supported_operation
                validate_workstation_for_supported_operation(workstation=workstation, operation=operation, api_source=scan_source)        

                # --- Cancel existing logs for same op/ws ---
                existing_logs = frappe.get_all(
                    "Item Scan Log",
                    filters={
                        "production_item": production_item_name,
                        "operation": operation,
                        "workstation": workstation,
                        "log_status": ["!=", "Cancelled"]
                    },
                    fields=["name"]
                )
                for log in existing_logs:
                    frappe.db.set_value(
                        "Item Scan Log",
                        log["name"],
                        "log_status",
                        "Cancelled",
                        update_modified=False
                    )

                # --- Create new scan log ---
                scan_log_doc = frappe.get_doc({
                    "doctype": "Item Scan Log",
                    "production_item": production_item_name,
                    "operation": operation,
                    "workstation": workstation,
                    "physical_cell": physical_cell,
                    "scanned_by": frappe.session.user,
                    "scan_time": frappe.utils.now_datetime(),
                    "logged_time": frappe.utils.now_datetime(),
                    "status": None,
                    "log_status": "Draft",
                    "log_type": "User Scanned",
                    "remarks": remarks or ""
                })
                scan_log_doc.insert(ignore_permissions=True)
                
                
                results.append({
                    "message": "Item Scanned",
                    "scan_log_id": scan_log_doc.name,
                    "production_item_number": production_item_doc.production_item_number,
                    "tracking_order": production_item_doc.tracking_order,
                    "bundle_configuration": production_item_doc.bundle_configuration,
                    "component": production_item_doc.component,
                    "component_name": production_item_doc.component,
                    "size": production_item_doc.size,
                    "quantity": production_item_doc.quantity,
                    "physical_cell": production_item_doc.physical_cell,
                    "production_type": production_item_bc_doc.production_type,
                    "dut": "ON" if TrackerXLiveSettings.is_dut_on(production_item_doc.type) else "OFF",
                    "type": production_item_doc.type,
                    "operation": operation,
                    "operation_name": operation,
                    "operation_group": operation_group_doc.name if operation_group_doc else None,
                    "operation_group_name": operation_group_doc.group_name if operation_group_doc else None,
                    "operation_type": operation_doc.custom_operation_type if operation_doc else None,
                    "workstation": workstation,
                    "workstation_name": workstation,
                    "color": fg_item_doc.custom_colour_name,
                    "style": style_master_doc.style_name,
                    "season": fg_item_doc.custom_season,
                    "material": fg_item_doc.custom_material_composition,
                    "prev_operation_ids": prev_operations,
                    "prev_and_current_operation_ids": prev_operations + [operation],
                    "smv_in_secs": operation_doc.total_operation_time * 60,
                    "cell": physical_cell_doc.name,
                    "cell_no": physical_cell_doc.cell_number,
                    "cell_name": physical_cell_doc.cell_name,
                    "is_rework_scan": is_rework_last,
                    "prev_logged_defects": ""
                })

            except Exception as inner_e:
                raise inner_e
        
        frappe.db.commit()
        return {
            "status": "completed",
            "code": 1200,
            "total_tags": len(tags),
            "data": results
        }

    except frappe.ValidationError as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Scan Item API Error")
        frappe.local.response.http_status_code = 400
        return {"status": "error", "message": str(e)}
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Scan Item API Error")
        frappe.local.response.http_status_code = 500
        return {"status": "error", "message": str(e)}
    

