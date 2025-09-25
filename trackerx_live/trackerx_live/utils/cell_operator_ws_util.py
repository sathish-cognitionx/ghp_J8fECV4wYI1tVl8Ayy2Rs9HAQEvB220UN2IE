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


def validate_workstation_for_supported_operation(workstation, operation, api_source):
    if not workstation or not operation or not api_source:
        frappe.throw("Workstation, Operation, and API Source must be provided.")

    try:
        enum_value = get_operation_type(operation)

        if enum_value.value == api_source: 
            return True
        else:
            frappe.throw(
                f"This workstation is not supported for {api_source}. Workstation is mapped to the operation for {enum_value.value}"
            )
            
    except Exception as e:
        frappe.throw(
              f"This workstation is not supported for {api_source}"
        )


def get_operation_type(operation):
    operation_doc = frappe.get_doc("Operation", operation)
    operation_type = operation_doc.custom_operation_type

    try:
        return OperationType[operation_type.upper().replace(" ", "_")]
    except KeyError:
        frappe.throw(f"Operation type is not recognized in OperationType enum.")
