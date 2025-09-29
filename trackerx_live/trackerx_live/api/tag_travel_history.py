import frappe
from frappe import _
from frappe.utils import now_datetime
from trackerx_live.trackerx_live.utils.operation_map_util import OperationMapManager

@frappe.whitelist()
def tag_travel_history(tag_number):
    try:
        tag_id = frappe.db.get_value(
            "Tracking Tag",
            {"tag_number": tag_number},
            "name"
        )

        if not tag_id:
            frappe.throw(
                f"Invalid tag! This tag is not activated, Please use activated tag. Contact your supervisor",
                frappe.ValidationError
            )

        tag_map = frappe.db.get_value(
            "Production Item Tag Map",
            {"tracking_tag": tag_id},
            ["name", "is_active", "production_item"],
            as_dict=True
        )

        if not tag_map or not tag_map.is_active:
            frappe.throw(
                f"Invalid Tag! Tag already unlinked, Please use activated tag. Contact your supervisor"
            )

        production_item_doc = frappe.get_doc("Production Item", tag_map.production_item)
        tracking_order_doc = frappe.get_doc("Tracking Order", production_item_doc.tracking_order)
        fg_item_doc = frappe.get_doc("Item", tracking_order_doc.item)
        style_master_doc = frappe.get_doc("Style Master", fg_item_doc.custom_style_master) if fg_item_doc.custom_style_master else None

        item_status = {
            "rfidTagNo": tag_id,
            "itemNo": production_item_doc.production_item_number,
            "woNo": tracking_order_doc.reference_order_number,
            "ftyProdId": production_item_doc.name,
            "style": style_master_doc.style_name if style_master_doc else None,
            "season": fg_item_doc.custom_season,
            "color": fg_item_doc.custom_colour_name,
            "material": fg_item_doc.custom_material_composition,
            "bundleOrUnit": production_item_doc.bundle_configuration,
            "coupledStatus": production_item_doc.status,
            "qualityStatus": None,
            "quantity": production_item_doc.quantity,
            "unitComponentType": production_item_doc.type,
            "pfpVersionId": None,
            "sizeAndWidth": production_item_doc.size
        }

        scan_logs = frappe.get_all(
            "Item Scan Log",
            filters={"production_item": production_item_doc.name},
            fields=["name", "operation", "workstation", "physical_cell", "scanned_by",
                    "scan_time", "status", "remarks", "log_type", "log_status"],
            order_by="scan_time asc"
        )

        operation_map_manager = OperationMapManager()
        operation_map = operation_map_manager.get_operation_map(tracking_order_number=tracking_order_doc.name)

        item_flow_data = []

        for log in scan_logs:
            user = frappe.get_value("User", log.scanned_by, ["first_name", "last_name"], as_dict=True) if log.scanned_by else {}

            operation_doc = frappe.get_doc("Operation", log.operation) if log.operation else None
            process_type = operation_doc.custom_operation_type if operation_doc else None

            defects = frappe.get_all(
                "Item Scan Log Defect",
                filters={"parent": log.name},
                fields=["defect_type as defectCodeType",
                        "defect_description as defectDescription",
                        "name as defectLogId"]
            )

            details = {
                "uuid": log.name,
                "icUuid": None,
                "userId": log.scanned_by,
                "userFirstName": user.get("first_name"),
                "userLastName": user.get("last_name"),
                "createdBy": log.scanned_by,
                "createdAt": log.scan_time,
                "cellId": log.physical_cell,
                "cell": log.physical_cell,
                "wsId": log.workstation,
                "ws": log.workstation,
                "processId": log.operation,
                "process": log.operation,
                "processType": process_type,
                "rfid": tag_id,
                "rfGeneratedId": None,
                "type": log.log_type,
                "parentTagNo": None,
                "productionUnitType": production_item_doc.type,
                "decoupledType": None,
                "defects": defects or [],
                "scanId": log.name,
                "defectVisible": bool(defects)
            }

            metadata = {
                "headerKey": None,
                "cellFrom": None,
                "cellTo": None,
                "cellTransDir": None,
                "missingUnitCount": 0,
                "defectiveUnitCount": len(defects),
                "inputLabel": None,
                "outputLabel": None,
                "createdAt": log.scan_time,
                "bundleToBundle": False,
                "unitToUnit": False,
                "cellTranistion": False,
                "bundleToUnit": False
            }

            item_flow_data.append({
                "itemDetailsResponseBean": [details],
                "metadata": metadata
            })

        response = {
            "status": "success",
            "data": {
                "itemStatusResponseBean": item_status,
                "itemFlowDataBeans": item_flow_data
            },
            "message": f"Travel history for tag {tag_id}"
        }

        return response

    except frappe.ValidationError as ve:
        frappe.log_error(frappe.get_traceback(), "Tag Travel History API Error")
        frappe.local.response.http_status_code = 400
        return {"status": "error", "message": str(ve)}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Tag Travel History API Error")
        frappe.local.response.http_status_code = 500
        return {"status": "error", "message": str(e)}
