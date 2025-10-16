import frappe
from frappe import _
from frappe.utils import now_datetime
from trackerx_live.trackerx_live.utils.operation_map_util import OperationMapManager
import pytz


def format_datetime(dt):
    """Format datetime to yyyy-MM-dd'T'HH:mm:ss.SSS (no timezone)"""
    if not dt:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(pytz.UTC).replace(tzinfo=None)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]


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

        production_item_name = frappe.db.get_value(
            "Production Item",
            {"tracking_tag": tag_id},
            "name",
            order_by="creation desc"
        )

        if not production_item_name:
            frappe.throw(
                f"No Production Item found for this tag. Please contact your supervisor.",
                frappe.ValidationError
            )

        production_item_doc = frappe.get_doc("Production Item", production_item_name)
        tracking_order_doc = frappe.get_doc("Tracking Order", production_item_doc.tracking_order)
        fg_item_doc = frappe.get_doc("Item", tracking_order_doc.item)
        style_master_doc = frappe.get_doc("Style Master", fg_item_doc.custom_style_master) if fg_item_doc.custom_style_master else None
        
        coupled_status = "active" if production_item_doc.tracking_status == "Active" else "unlinked"

        quality_status = frappe.db.get_value(
            "Item Scan Log",
            {
                "production_item": production_item_doc.name,
                "operation": production_item_doc.current_operation
            },
            "status"
        )

        item_status = {
            "rfidTagNo": tag_id,
            "itemNo": production_item_doc.production_item_number,
            "woNo": tracking_order_doc.reference_order_number,
            "ftyProdId": production_item_doc.name,
            "style": style_master_doc.style_name if style_master_doc else None,
            "season": fg_item_doc.custom_season if getattr(fg_item_doc, "custom_season", None) else None,
            "color": fg_item_doc.custom_colour_name,
            "material": fg_item_doc.custom_material_composition,
            "bundleOrUnit": production_item_doc.bundle_configuration,
            "coupledStatus": coupled_status,
            "qualityStatus": quality_status,
            "quantity": production_item_doc.quantity,
            "unitComponentType": production_item_doc.type,
            "pfpVersionId": None,
            "sizeAndWidth": production_item_doc.size,
            "productionUnitType": "Bundle" if production_item_doc.type == "Component" or production_item_doc.bundle_configuration else "Unit"
        }

        scan_logs = frappe.get_all(
            "Item Scan Log",
            filters={"production_item": production_item_doc.name},
            fields=["name", "operation", "workstation", "physical_cell", "scanned_by",
                    "scan_time", "logged_time", "status", "remarks", "log_type", "log_status"],
            order_by="logged_time asc, scan_time asc"
        )

        item_flow_data = []
        prev_cell = None 

        for log in scan_logs:
            user = frappe.db.get_value("User", log.scanned_by, ["first_name", "last_name"], as_dict=True) if log.scanned_by else {}

            operation_doc = frappe.get_doc("Operation", log.operation) if log.operation else None
            process_type = operation_doc.custom_operation_type if operation_doc else None

            defects = frappe.get_all(
                "Item Scan Log Defect",
                filters={"parent": log.name},
                fields=["defect_type as defectCodeType",
                        "defect_description as defectDescription",
                        "name as defectLogId"]
            )

            cell_transition = False
            if log.status == "Pass" and prev_cell and log.physical_cell and log.physical_cell != prev_cell:
                cell_transition = True

            prev_cell = log.physical_cell  

            details = {
                "uuid": log.name,
                "icUuid": None,
                "userId": log.scanned_by,
                "userFirstName": user.get("first_name"),
                "userLastName": user.get("last_name"),
                "createdBy": log.scanned_by,
                "createdAt": format_datetime(log.logged_time or log.scan_time),
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
                "productionUnitType": "Bundle" if production_item_doc.type == "Component" or production_item_doc.bundle_configuration else "Unit",
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
                "createdAt": format_datetime(log.logged_time or log.scan_time),
                "bundleToBundle": False,
                "unitToUnit": False,
                "cellTranistion": cell_transition,
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
