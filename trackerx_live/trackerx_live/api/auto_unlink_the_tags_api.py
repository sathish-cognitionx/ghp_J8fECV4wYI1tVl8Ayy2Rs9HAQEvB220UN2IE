import frappe
import json
from frappe import _
from trackerx_live.trackerx_live.utils.cell_operator_ws_util import get_cell_operator_by_ws, validate_workstation_for_supported_operation


@frappe.whitelist()
def auto_unlink_tags(tag_numbers, ws_name=None):
    try:
        if isinstance(tag_numbers, str):
            try:
                tag_numbers = json.loads(tag_numbers)
            except Exception:
                tag_numbers = [tag_numbers]

        if not isinstance(tag_numbers, list) or not tag_numbers:
            frappe.throw(_("Tag numbers are required"), frappe.ValidationError)

        if not ws_name:
            frappe.throw(_("Workstation name is required"), frappe.ValidationError)
            
        updated_tags, skipped_tags, not_found_tags = [], [], []
        qcg_bulk_error_beans = []
        production_item_doc = None

        for tracking_tag_number in tag_numbers:
            tag = frappe.get_all(
                "Tracking Tag",
                filters={"tag_number": tracking_tag_number},
                fields=["name"]
            )

            if not tag:
                not_found_tags.append(tracking_tag_number)
                continue

            tag_id = tag[0].name
            tag_map = frappe.get_all(
                "Production Item Tag Map",
                filters={"tracking_tag": tag_id, "is_active": 1},
                fields=["name", "production_item"]
            )

            if not tag_map:
                skipped_tags.append(tracking_tag_number)
                continue
                
            # Validate workstation for operation         
            ws_info_list = get_cell_operator_by_ws(ws_name)
            if not ws_info_list:
                frappe.throw(_(f"No operation/cell mapped for workstation {ws_name}"), frappe.ValidationError)
            ws_info = ws_info_list[0]
            current_operation = ws_info["operation_name"]
            validate_workstation_for_supported_operation(workstation=ws_name, operation=current_operation, api_source="Unlink")        

            tag_doc = frappe.get_doc("Production Item Tag Map", tag_map[0].name)
            tag_doc.is_active = 0
            tag_doc.deactivated_source = "EOL UnLink"
            tag_doc.save()

            production_item_name = tag_map[0].get("production_item")
            if production_item_name:
                production_item_doc = frappe.get_doc("Production Item", production_item_name)
                production_item_doc.tracking_status = "Unlinked"
                production_item_doc.unlinked_source = "EOL"
                production_item_doc.save()

                # build qcg bean entry for this tag
                qcg_bulk_error_beans.append({
                    "rfid": tracking_tag_number,
                    "bulkSkippedRfidBeen": {
                        "process": production_item_doc.current_operation,
                        "sequence": 4,  # static for now
                        "ws": [ws_name],
                        "scanStatus": "success",
                        "processGroup": "",
                        "cell": production_item_doc.physical_cell,
                        "processId": production_item_doc.current_operation,
                        "processGroupId": "",
                        "cellNames": [production_item_doc.physical_cell] if production_item_doc.physical_cell else []
                    },
                    "bulkDefectiveRfidBeen": {
                        "process": production_item_doc.current_operation,
                        "sequence": 4,  # static for now
                        "ws": [ws_name],
                        "scanStatus": "success",
                        "processGroup": "",
                        "cell": production_item_doc.physical_cell,
                        "processId": production_item_doc.current_operation,
                        "processGroupId": "",
                        "cellNames": [production_item_doc.physical_cell] if production_item_doc.physical_cell else []
                    },
                    "sizeAndWidth": ""
                })

            updated_tags.append(tracking_tag_number)

        frappe.db.commit()

        # tracking order + item info
        factory_product_id, work_order_no, style, colour, material = "", "", "", "", ""
        if production_item_doc:
            if production_item_doc.tracking_order:
                trk_order = frappe.get_doc("Tracking Order", production_item_doc.tracking_order)
                factory_product_id = trk_order.item
                work_order_no = trk_order.reference_order_type
                # fetch extra item fields if they exist
                if trk_order.item:
                    item_doc = frappe.get_doc("Item", trk_order.item)
                    style = getattr(item_doc, "custom_style_master", "")
                    colour = getattr(item_doc, "custom_colour_name", "")
                    material = getattr(item_doc, "custom_material_composition", "")

        # final structured response
        response = {
            "data": {
                "workOrderWiseSkippedProcessBeanList": [
                    {
                        "qcgBulkErrorBeans": qcg_bulk_error_beans,
                        "totalRfidCount": len(tag_numbers),
                        "skippedAndDefectiveRfidCount": len(skipped_tags),
                        "defectiveRfidCount": len(not_found_tags),
                        "factoryProductId": factory_product_id,
                        "workOrderNo": work_order_no,
                        "style": style,
                        "colour": colour,
                        "material": material,
                        "poLineItem": None
                    }
                ],
                "totalRfidSkippedCount": len(skipped_tags),
                "todayScanCountAtEol": len(tag_numbers)
            },
            "code": 0,
            "info": "Unlink tag success",
            "status": "success",
            "cause": None
        }

        return response

    except frappe.ValidationError as e:
        frappe.log_error(frappe.get_traceback(), "auto_unlink_tags() error")
        frappe.local.response.http_status_code = 400
        return {"status": "error", "message": str(e)}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "auto_unlink_tags() error")
        frappe.local.response.http_status_code = 500
        return {"status": "error", "message": str(e)}
