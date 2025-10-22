import frappe
from frappe import _
from frappe.utils import now_datetime
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

        style_master_doc = None
        if getattr(fg_item_doc, "custom_style_master", None):
            style_master_doc = frappe.get_doc("Style Master", fg_item_doc.custom_style_master)

        coupled_status = "active" if production_item_doc.tracking_status == "Active" else "unlinked"

        quality_status = frappe.db.get_value(
            "Item Scan Log",
            {"production_item": production_item_doc.name, "operation": production_item_doc.current_operation},
            "status",
            order_by="logged_time desc"
        )

        item_status = {
            "rfidTagNo": tag_id,
            "itemNo": production_item_doc.production_item_number,
            "woNo": tracking_order_doc.reference_order_number,
            "ftyProdId": production_item_doc.name,
            "style": style_master_doc.style_name if style_master_doc else None,
            "season": getattr(fg_item_doc, "custom_season", None),
            "color": getattr(fg_item_doc, "custom_colour_name", None),
            "material": getattr(fg_item_doc, "custom_material_composition", None),
            "bundleOrUnit": production_item_doc.bundle_configuration,
            "coupledStatus": coupled_status,
            "qualityStatus": quality_status,
            "quantity": production_item_doc.quantity,
            "unitComponentType": production_item_doc.type,
            "sizeAndWidth": production_item_doc.size,
            "productionUnitType": (
                "Bundle" if production_item_doc.type == "Component" or production_item_doc.bundle_configuration else "Unit"
            )
        }

        scan_logs = frappe.get_all(
            "Item Scan Log",
            filters={"production_item": production_item_doc.name},
            fields=[
                "name", "operation", "workstation", "physical_cell", "scanned_by",
                "scan_time", "logged_time", "status", "remarks", "log_type", "log_status"
            ],
            order_by="logged_time asc, scan_time asc"
        )

        item_flow_data = []
        prev_cell = None

        for log in scan_logs:
            user = frappe.db.get_value("User", log.scanned_by, ["first_name", "last_name"], as_dict=True) if log.scanned_by else {}
            operation_doc = frappe.get_doc("Operation", log.operation) if log.operation else None
            process_type = getattr(operation_doc, "custom_operation_type", None)

            defects = frappe.get_all(
                "Item Scan Log Defect",
                filters={"parent": log.name},
                fields=[
                    "defect_type as defectCodeType",
                    "defect_description as defectDescription",
                    "name as defectLogId"
                ]
            )

            cell_transition = False
            cell_from = prev_cell
            cell_to = log.physical_cell
            if (
                log.status == "Pass"
                and prev_cell
                and log.physical_cell
                and log.physical_cell != prev_cell
            ):
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
                "type": log.log_type,
                "parentTagNo": None,
                "productionUnitType": (
                    "Bundle" if production_item_doc.type == "Component" or production_item_doc.bundle_configuration else "Unit"
                ),
                "decoupledType": production_item_doc.unlinked_source,
                "defects": defects or [],
                "scanId": log.name,
                "defectVisible": bool(defects)
            }

            metadata = {
                "headerKey": None,
                "cellFrom": cell_from,
                "cellTo": cell_to,
                "missingUnitCount": 0,
                "defectiveUnitCount": len(defects),
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
