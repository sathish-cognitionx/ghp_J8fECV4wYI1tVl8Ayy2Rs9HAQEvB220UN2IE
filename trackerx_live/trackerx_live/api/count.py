import frappe
import json
from frappe import _
from frappe.utils import now_datetime
from frappe.exceptions import ValidationError
from trackerx_live.trackerx_live.utils.production_completion_util import check_and_complete_production_item
from trackerx_live.trackerx_live.api.counted_info import get_counted_info
from trackerx_live.trackerx_live.utils.cell_operator_ws_util import validate_workstation_for_supported_operation 
from trackerx_live.trackerx_live.utils.cell_operator_ws_util import get_cell_operator_by_ws 
from trackerx_live.trackerx_live.utils.sequence_of_operation import SequenceOfOpeationUtil


@frappe.whitelist()
def count_tags(tag_numbers, ws_name):
    try:
        if not ws_name:
            frappe.throw(
                _("No mapping found for workstation: {0}").format(ws_name),
                ValidationError
            )

        if isinstance(tag_numbers, str):
            try:
                tag_numbers = json.loads(tag_numbers)
            except Exception:
                tag_numbers = [tag_numbers]

        if not isinstance(tag_numbers, list) or not tag_numbers:
            frappe.throw(_("tag_numbers must be a non-empty list"), ValidationError)

        created_logs = []
        errors = []
        current_components_map = {}


        ws_info_list = get_cell_operator_by_ws(ws_name)
        if not ws_info_list:
            frappe.throw(_(f"No operation/cell mapped for workstation {ws_name}"), ValidationError)

        ws_info = ws_info_list[0]
        current_operation = ws_info["operation_name"]
        physical_cell = ws_info["cell_id"]
        current_workstation = ws_info["workstation"]



        for tag_number in tag_numbers:
            tag = frappe.get_all("Tracking Tag", filters={"tag_number": tag_number}, fields=["name"])
            if not tag:
                errors.append({"tag": tag_number, "reason": "Tag not found"})
                continue
            tag_id = tag[0]["name"]

            tag_map = frappe.db.get_value(
                "Production Item Tag Map",
                {"tracking_tag": tag_id},
                ["name", "is_active", "production_item"],
                as_dict=True
            )

            if not tag_map:
                errors.append({"tag": tag_number, "reason": "Tag not linked"})
                continue
            if not tag_map.is_active:
                errors.append({"tag": tag_number, "reason": "Tag is deactivated"})
                continue

            result = SequenceOfOpeationUtil.can_this_item_scan_in_this_operation(production_item=tag_map.production_item, workstation=current_workstation, operation=current_operation, physical_cell=physical_cell)
            if not result.is_allowed:
                continue
            production_item_doc = frappe.get_doc("Production Item", tag_map.production_item)

            if not current_operation or not current_workstation:
                errors.append({"tag": tag_number, "reason": "Missing operation/workstation"})
                continue
            
            # validate workstation for supported operation
            validate_workstation_for_supported_operation(workstation=current_workstation, operation=current_operation, api_source="Count")        


            # Log scan
            new_scan_log = frappe.new_doc("Item Scan Log")
            new_scan_log.production_item = production_item_doc.name
            new_scan_log.operation = current_operation
            new_scan_log.workstation = current_workstation
            new_scan_log.physical_cell = physical_cell
            new_scan_log.scanned_by = frappe.session.user
            new_scan_log.scan_time = now_datetime()
            new_scan_log.logged_time = now_datetime()
            new_scan_log.status = "Counted"
            new_scan_log.log_status = "Completed"
            new_scan_log.log_type = "User Scanned"
            new_scan_log.production_item_type = production_item_doc.type
          
            new_scan_log.insert()
            created_logs.append({"tag": tag_number, "log": new_scan_log.name})

            # Track component-wise totals
            comp_name = frappe.db.get_value("Tracking Component", production_item_doc.component, "component_name")
            if comp_name:
                if comp_name not in current_components_map:
                    current_components_map[comp_name] = 0
                current_components_map[comp_name] += production_item_doc.quantity

            # Check and complete production item
            check_and_complete_production_item(production_item_doc, current_operation)

        # if created_logs:
        #     frappe.db.commit()

        # Fetch today's and current hour's info
        today_info = get_counted_info(ws_name, "today")
        current_hour_info = get_counted_info(ws_name, "current_hour")
        counted_info_data = get_counted_info(ws_name)

        # Compute current_bundle_count for this session
        current_bundle_count = len(created_logs)

        return {
            "status": "success",
            "total_tags": len(tag_numbers),
            "logged_tags": len(created_logs),
            "error_tags": len(errors),
            "current_bundle_count": current_bundle_count,
            "today_count": today_info.get("total_count", 0),
            "current_hour_count": current_hour_info.get("total_count", 0),
            "component_wise_current_count": current_components_map,
            "counted_info": counted_info_data,          
            "logged_tags_info": created_logs,
            "errors_info": errors
        }

    except frappe.ValidationError as e:
        frappe.log_error(frappe.get_traceback(), "count_tags() error")
        frappe.local.response.http_status_code = 400
        return {"status": "error", "message": str(e)}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "count_tags() error")
        frappe.local.response.http_status_code = 500
        return {"status": "error", "message": str(e)}
