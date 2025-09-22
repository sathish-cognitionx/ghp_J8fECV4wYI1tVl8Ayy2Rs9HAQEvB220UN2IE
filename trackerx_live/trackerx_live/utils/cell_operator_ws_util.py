import frappe
from frappe.utils import flt
from trackerx_live.trackerx_live.enums.operation_type import OperationType


def get_cell_operator_by_ws(ws_name):
    workstation_info_list = []
    try:
        cell_operation_ws_list = frappe.get_all( "Physical Cell Operation",
            filters={
                "workstation": ws_name,  
            },
            fields=["name", "operation", "parent"]
        )

        

        for cell_operation_ws in cell_operation_ws_list:
            cell = frappe.get_doc("Physical Cell", cell_operation_ws.parent)
            operation = frappe.get_doc("Operation", cell_operation_ws.operation)
            workstation_info_list.append({
                 "workstation": ws_name,
                 "cell_number": cell.cell_number,
                 "cell_name": cell.cell_name,
                 "cell_id": cell.name,
                 "operation_group": cell.supported_operation_group,
                 "operation_name": operation.name,
                 "operation_type": operation.custom_operation_type
            })

    except Exception as e:
            pass
    
    return workstation_info_list


def validate_workstation_for_supported_opeation(workstation, opeation, api_source):
    try:
        
        # get the operation type
        
        if workstation:
               1=1
    except Exception as e:
        frappe.throw(
              f"This workstation is not supported for Activation"
        )
     
def get_operation_type(opeation):
    return OperationType.ACTIVATION
    