# import frappe
# import json
# from frappe import _

# @frappe.whitelist(allow_guest=True)
# def log_defect_api(production_item_id, process_id, ws_id, defects):
#     """
#     API to log defects into Item Scan Log (parent) and Item Scan Log Defect (child table).
#     User does not need to send scanned_by, status, or remarks.
#     """

#     try:
#         # Validate mandatory inputs
#         if not production_item_id or not process_id or not ws_id or not defects:
#             return {"error": "Missing required fields"}

#         # Convert defects JSON string → Python list
#         if isinstance(defects, str):
#             defects = json.loads(defects)

#         # Create parent Item Scan Log
#         parent_doc = frappe.get_doc({
#             "doctype": "Item Scan Log",
#             "production_item": production_item_id,
#             "operation": process_id,
#             "workstation": ws_id,
#             "scanned_by": frappe.session.user,  
#             "scan_time": frappe.utils.now_datetime(),
#             "status": "Fail",           
#             "remarks": None                     
#         })

#         # Add defects into child table
#         for defect in defects:
#             parent_doc.append("defect_list", {
#                 "defect_type": defect.get("defect_type"),
#                 "defect_code": defect.get("defect_id"),
#                 "defect_description": defect.get("defect_desc"),
#                 "severity": defect.get("severity")
#             })

#         # Save parent + child
#         parent_doc.insert(ignore_permissions=True)
#         frappe.db.commit()

#         return {
#             "status": "success",
#             "message": f"{len(defects)} defects logged successfully",
#             "item_scan_log_id": parent_doc.name,
#             "defect_rows": [d.name for d in parent_doc.defect_list]
#         }

#     except Exception as e:
#         frappe.log_error(frappe.get_traceback(), "log_defect_api_error")
#         return {"error": str(e)}

import frappe
import json
from frappe import _

@frappe.whitelist(allow_guest=True)
def log_defect_api(production_item_id, process_id, ws_id, defects):
    """
    API to log defects into Item Scan Log (parent) and Item Scan Log Defect (child table).
    User only sends defect_id, rest details fetched from Tracking Order Defect Master.
    """

    try:
        # Validate mandatory inputs
        if not production_item_id or not process_id or not ws_id or not defects:
            return {"error": "Missing required fields"}

        # Convert defects JSON string → Python list
        if isinstance(defects, str):
            defects = json.loads(defects)

        # Create parent Item Scan Log
        parent_doc = frappe.get_doc({
            "doctype": "Item Scan Log",
            "production_item": production_item_id,
            "operation": process_id,
            "workstation": ws_id,
            "scanned_by": frappe.session.user,
            "scan_time": frappe.utils.now_datetime(),
            "status": "Fail",
            "remarks": None
        })

        # Add defects into child table
        for defect in defects:
            defect_id = defect.get("defect_id")
            if not defect_id:
                continue

            # Fetch from Tracking Order Defect Master
            defect_doc = frappe.get_doc("Tracking Order Defect Master", defect_id)

            parent_doc.append("defect_list", {
                "defect": defect_doc.name,                # Link field
                "defect_type": defect_doc.defect_type,    # field from master
                "defect_description": defect_doc.defect_description,
                "severity": defect_doc.severity
            })

        # Save parent + child
        parent_doc.insert(ignore_permissions=True)
        frappe.db.commit()

        # Prepare detailed response (like UI list)
        response_defects = []
        for d in parent_doc.defect_list:
            response_defects.append({
                "row_id": d.name,
                "defect_id": d.defect,
                "defect_type": d.defect_type,
                # "description": d.defect_description,
                "severity": d.severity
            })

        return {
            "status": "success",
            "message": f"{len(defects)} defects logged successfully",
            "item_scan_log_id": parent_doc.name,
            "defects": response_defects
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "log_defect_api_error")
        return {"error": str(e)}

