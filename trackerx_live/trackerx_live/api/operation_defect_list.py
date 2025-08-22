import frappe
import json
from frappe import _

@frappe.whitelist(allow_guest=True)
def get_defects_by_operation(operation_name):
    """
    Get all defects linked with a given operation
    """
    try:
        operation_doc = frappe.get_doc("Operation", operation_name)

        defects = []
        for row in operation_doc.custom_defect_list: 
            defects.append({
                "defect": row.defect,
                "defect_description": row.defect_description,
                "defect_type": row.defect_type,
                "defect_code": row.defect_code
                # "defect_category": row.defect_category,
                # "severity": row.severity

            })

        return {
            "operation": operation_name,
            "defects": defects
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "get_defects_by_operation_error")
        return {"error": str(e)}
    
