import frappe
from frappe import _


@frappe.whitelist()
def get_physical_cells():
    """
    Get all Physical Cells excluding 'QR/Barcode Cut Bundle Activation'
    """
    try:
        cells = frappe.get_all(
            "Physical Cell",
            fields=["name", "cell_name", "cell_number", "start_time", "end_time", "operator_count"],
            filters=[
                ["name", "!=", "QR/Barcode Cut Bundle Activation"],
                ["cell_name", "!=", "QR/Barcode Cut Bundle Activation"]
            ],
            order_by="cell_number asc"
        )
        
        return {
            "status": "success",
            "data": cells,
            "count": len(cells)
        }
    
    except Exception as e:
        frappe.log_error(f"Error in get_physical_cells: {str(e)}")
        return {
            "status": "error",
            "message": str(e),
            "data": []
        }


@frappe.whitelist()
def get_operations(physical_cell=None):
    """
    Get operations with optional physical cell filter
    Args:
        physical_cell: Optional physical cell name to filter by
    """
    try:
        if physical_cell:
            # Get operations from specific physical cell's child table
            operations = frappe.db.sql("""
                SELECT DISTINCT pco.operation, op.name, op.custom_operation_type, op.custom_operation_group
                FROM `tabPhysical Cell Operation` pco
                LEFT JOIN `tabOperation` op ON pco.operation = op.name
                WHERE pco.parent = %s 
                AND pco.operation != 'QR/Barcode Cut Bundle Activation'
                AND op.name IS NOT NULL
                ORDER BY op.name
            """, (physical_cell,), as_dict=True)
            
            # Format the response
            formatted_operations = [
                {
                    "name": op.operation,
                    "operation_name":  op.name,
                    "operation_type": op.custom_operation_type,
                    "operation_group": op.custom_operation_group
                }
                for op in operations
            ]
        else:
            # Get all operations from base Operation doctype
            formatted_operations = frappe.get_all(
                "Operation",
                fields=["name", "operation_name"],
                filters=[
                    ["name", "!=", "QR/Barcode Cut Bundle Activation"],
                    ["operation_name", "!=", "QR/Barcode Cut Bundle Activation"]
                ],
                order_by="operation_name asc"
            )
        
        return {
            "status": "success",
            "data": formatted_operations,
            "count": len(formatted_operations),
            "filter_applied": {"physical_cell": physical_cell} if physical_cell else None
        }
    
    except Exception as e:
        frappe.log_error(f"Error in get_operations: {str(e)}")
        return {
            "status": "error",
            "message": str(e),
            "data": []
        }


@frappe.whitelist()
def get_workstations(physical_cell=None, operation=None):
    """
    Get workstations with optional physical cell and/or operation filters
    Args:
        physical_cell: Optional physical cell name(s) - can be string or comma-separated list
        operation: Optional operation name(s) - can be string or comma-separated list
    """
    try:
        # Parse multiple values if provided as comma-separated strings
        physical_cells = []
        operations = []
        
        if physical_cell:
            if isinstance(physical_cell, str):
                physical_cells = [cell.strip() for cell in physical_cell.split(',') if cell.strip()]
            else:
                physical_cells = [physical_cell]
        
        if operation:
            if isinstance(operation, str):
                operations = [op.strip() for op in operation.split(',') if op.strip()]
            else:
                operations = [operation]
        
        workstations = []
        
        if physical_cells or operations:
            # Build dynamic SQL query based on filters
            sql_conditions = ["pco.workstation != 'QR/Barcode Cut Bundle Activation'"]
            sql_params = []
            
            if physical_cells:
                placeholders = ', '.join(['%s'] * len(physical_cells))
                sql_conditions.append(f"pco.parent IN ({placeholders})")
                sql_params.extend(physical_cells)
            
            if operations:
                placeholders = ', '.join(['%s'] * len(operations))
                sql_conditions.append(f"pco.operation IN ({placeholders})")
                sql_params.extend(operations)
            
            where_clause = " AND ".join(sql_conditions)
            
            workstation_data = frappe.db.sql(f"""
                SELECT DISTINCT pco.workstation, ws.workstation_name
                FROM `tabPhysical Cell Operation` pco
                LEFT JOIN `tabWorkstation` ws ON pco.workstation = ws.name
                WHERE {where_clause}
                AND ws.name IS NOT NULL
                ORDER BY ws.workstation_name
            """, tuple(sql_params), as_dict=True)
            
            # Format the response
            workstations = [
                {
                    "name": ws.workstation,
                    "workstation_name": ws.workstation_name or ws.workstation
                }
                for ws in workstation_data
            ]
        else:
            # Get all workstations from base Workstation doctype
            workstations = frappe.get_all(
                "Workstation",
                fields=["name", "workstation_name"],
                filters=[
                    ["name", "!=", "QR/Barcode Cut Bundle Activation"],
                    ["workstation_name", "!=", "QR/Barcode Cut Bundle Activation"]
                ],
                order_by="workstation_name asc"
            )
        
        return {
            "status": "success",
            "data": workstations,
            "count": len(workstations),
            "filters_applied": {
                "physical_cells": physical_cells if physical_cells else None,
                "operations": operations if operations else None
            }
        }
    
    except Exception as e:
        frappe.log_error(f"Error in get_workstations: {str(e)}")
        return {
            "status": "error",
            "message": str(e),
            "data": []
        }


# Additional utility function to get complete dropdown data in one call
@frappe.whitelist()
def get_all_dropdown_data(physical_cell=None, operation=None):
    """
    Get all dropdown data in a single API call for better performance
    Args:
        physical_cell: Optional physical cell filter for operations and workstations
        operation: Optional operation filter for workstations
    """
    try:
        # Get all physical cells
        cells_data = get_physical_cells()
        
        # Get operations (filtered by physical cell if provided)
        operations_data = get_operations(physical_cell)
        
        # Get workstations (filtered by physical cell and/or operation if provided)
        workstations_data = get_workstations(physical_cell, operation)
        
        return {
            "status": "success",
            "data": {
                "physical_cells": cells_data.get("data", []),
                "operations": operations_data.get("data", []),
                "workstations": workstations_data.get("data", [])
            },
            "counts": {
                "physical_cells": cells_data.get("count", 0),
                "operations": operations_data.get("count", 0),
                "workstations": workstations_data.get("count", 0)
            },
            "filters_applied": {
                "physical_cell": physical_cell,
                "operation": operation
            }
        }
    
    except Exception as e:
        frappe.log_error(f"Error in get_all_dropdown_data: {str(e)}")
        return {
            "status": "error",
            "message": str(e),
            "data": {}
        }