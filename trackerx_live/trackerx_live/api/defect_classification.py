"""
QC Production Item Management APIs
File: trackerx_live/api/qc_management.py

This module provides three APIs for QC supervisors to manage production items
with QC Reject/Recut statuses.
"""

import frappe
from frappe import _
from frappe.utils import now_datetime
from functools import wraps
import trackerx_live.trackerx_live.utils.tracking_tag_util as tracking_tag_util


# Role-based access control decorator
def require_qc_roles(allowed_roles=None):
    """
    Decorator to restrict API access to specific roles
    Default roles: QC Head, QC Supervisor, Supervisor
    """
    if allowed_roles is None:
        allowed_roles = ["QC Head", "QC Supervisor", "Supervisor"]
    
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = frappe.session.user
            user_roles = frappe.get_roles(user)
            
            # Check if user has any of the required roles
            has_access = any(role in user_roles for role in allowed_roles)
            
            if not has_access:
                frappe.throw(
                    _("Access Denied. Required roles: {}").format(", ".join(allowed_roles)),
                    frappe.PermissionError
                )
            
            return fn(*args, **kwargs)
        return wrapper
    return decorator


@frappe.whitelist()
@require_qc_roles()
def get_qc_rejected_units(view="list"):
    """
    API 1: List all Production Items with QC Reject/Recut status
    Grouped by: Physical Cell -> Current Operation -> Current Workstation
    
    Returns:
        dict: Hierarchical structure with counts at each level
    """
    try:
        # Query to get production items with QC Reject or QC Recut status
        query = """
            SELECT 
                pi.name as production_item,
                pi.production_item_number,
                pi.tracking_order,
                pi.bundle_configuration,
                pi.component,
                pi.size,
                pi.quantity,
                pi.status as production_status,
                pi.current_operation,
                pi.current_workstation,
                pi.device_id,
                pi.tracking_tag,
                isl.name as scan_log_id,
                isl.physical_cell,
                isl.operation,
                isl.workstation,
                isl.status as scan_status,
                isl.scan_time,
                isl.scanned_by,
                isl.remarks
            FROM 
                `tabProduction Item` pi
            INNER JOIN 
                `tabItem Scan Log` isl ON pi.last_scan_log = isl.name
            WHERE 
                pi.status = 'In Production'
                AND isl.status IN ('QC Rejected', 'QC Recut')
                AND isl.log_status = 'Completed'
            ORDER BY 
                isl.physical_cell, isl.operation, isl.workstation
        """
        
        items = frappe.db.sql(query, as_dict=True)

        data = None
        list = []
        
        if not items:
            return {
                "success": True,
                "message": "No items found with QC Reject/Recut status",
                "data": [],
                "total_count": 0
            }
        
        # Build hierarchical structure
        grouped_data = {}
        total_count = 0
        
        for item in items:
            physical_cell = item.physical_cell or "Unassigned"
            operation = item.operation or "No Operation"
            workstation = item.workstation or "No Workstation"
            
            # Initialize physical cell level
            if physical_cell not in grouped_data:
                grouped_data[physical_cell] = {
                    "count": 0,
                    "operations": {}
                }
            
            # Initialize operation level
            if operation not in grouped_data[physical_cell]["operations"]:
                grouped_data[physical_cell]["operations"][operation] = {
                    "count": 0,
                    "workstations": {}
                }
            
            # Initialize workstation level
            if workstation not in grouped_data[physical_cell]["operations"][operation]["workstations"]:
                grouped_data[physical_cell]["operations"][operation]["workstations"][workstation] = {
                    "count": 0,
                    "items": []
                }
            
            # Add item details at workstation level
            active_tags = tracking_tag_util.get_tags_by_production_item(item.production_item)
            tracking_tag = None
            if active_tags:
                tracking_tag = active_tags[0]
            
            item_scan_log_doc = frappe.get_doc("Item Scan Log", item.scan_log_id)

            item_detail = {
                "production_item": item.production_item,
                "production_item_number": item.production_item_number,
                "tracking_order": item.tracking_order,
                "component": item.component,
                "size": item.size,
                "quantity": item.quantity,
                "device_id": item.device_id,
                "tracking_tag": tracking_tag,
                "scan_status": item.scan_status,
                "scan_time": str(item.scan_time) if item.scan_time else None,
                "scanned_by": item.scanned_by,
                "remarks": item.remarks,
                "scan_log_id": item.scan_log_id,
                "style": "Style",
                "color": "Color",
                "so_number": "SO Number",
                "line_item_number": "Line Item Number",
                "cell": physical_cell,
                "operation": operation,
                "workstation": workstation,
                "defect_list": item_scan_log_doc.defect_list
            }
            
            list.append(item_detail)
            grouped_data[physical_cell]["operations"][operation]["workstations"][workstation]["items"].append(item_detail)
            
            # Update counts
            grouped_data[physical_cell]["operations"][operation]["workstations"][workstation]["count"] += 1
            grouped_data[physical_cell]["operations"][operation]["count"] += 1
            grouped_data[physical_cell]["count"] += 1
            total_count += 1
        
        if view == "tree":
            data = grouped_data
        else:
            data = list
        return {
            "success": True,
            "message": f"Found {total_count} items with QC Reject/Recut status",
            "data": data,
            "total_count": total_count,
            "timestamp": now_datetime()
        }
    
    except Exception as e:
        frappe.local.response.http_status_code = 400
        frappe.log_error(message=str(e), title="QC Defective Items Grouped API Error")
        return {
            "success": False,
            "message": f"Error retrieving data: {str(e)}",
            "data": {}
        }


@frappe.whitelist()
@require_qc_roles()
def scan_qc_rejected_item(tag):
    """
    API 2: Validate and retrieve production item with QC Reject/Recut status
    
    Args:
        production_item_name (str): Name/ID of the production item
    
    Returns:
        dict: Production item details, scan log info, and defect details
    """
    try:

        production_item_name = tracking_tag_util.get_active_production_item_by_tag(tag)
        if not production_item_name:
            frappe.throw(
                f"No item is activated against the the tag number {tag}, Contact supervisor"
            )

        # Check if production item exists
        if not frappe.db.exists("Production Item", production_item_name):
            return {
                "success": False,
                "message": f"Production Item '{production_item_name}' not found",
                "data": None
            }
        
        # Get production item details
        prod_item = frappe.get_doc("Production Item", production_item_name)
        
        # Check if last_scan_log exists
        if not prod_item.last_scan_log:
            return {
                "success": False,
                "message": "No scan log found for this production item",
                "data": None
            }
        
        # Get scan log details
        scan_log = frappe.get_doc("Item Scan Log", prod_item.last_scan_log)
        
        # Validate status
        if scan_log.status not in ["QC Rejected", "QC Recut"]:
            return {
                "success": False,
                "message": f"Item status is '{scan_log.status}', not QC Rejected or QC Recut",
                "data": production_item_name
            }
        
        # Get defect details
        defects = []
        for defect_row in scan_log.defect_list:
            defects.append({
                "defect": defect_row.defect,
                "defect_type": defect_row.defect_type,
                "defect_code": defect_row.defect_code,
                "defect_description": defect_row.defect_description,
                "severity": defect_row.severity,
                "defect_category": defect_row.defect_category
            })
        
        # Prepare response
        response_data = {
            "production_item": {
                "name": prod_item.name,
                "production_item_number": prod_item.production_item_number,
                "tracking_order": prod_item.tracking_order,
                "bundle_configuration": prod_item.bundle_configuration,
                "component": prod_item.component,
                "size": prod_item.size,
                "quantity": prod_item.quantity,
                "status": prod_item.status,
                "current_operation": prod_item.current_operation,
                "next_operation": prod_item.next_operation,
                "current_workstation": prod_item.current_workstation,
                "next_workstation": prod_item.next_workstation,
                "device_id": prod_item.device_id,
                "tracking_tag": prod_item.tracking_tag,
                "physical_cell": prod_item.physical_cell,
                "type": prod_item.type
            },
            "scan_log": {
                "name": scan_log.name,
                "physical_cell": scan_log.physical_cell,
                "operation": scan_log.operation,
                "workstation": scan_log.workstation,
                "status": scan_log.status,
                "scan_time": str(scan_log.scan_time) if scan_log.scan_time else None,
                "logged_time": str(scan_log.logged_time) if scan_log.logged_time else None,
                "scanned_by": scan_log.scanned_by,
                "remarks": scan_log.remarks,
                "log_status": scan_log.log_status,
                "log_type": scan_log.log_type,
                "dut": scan_log.dut
            },
            "defects": defects,
            "defect_count": len(defects)
        }
        
        return {
            "success": True,
            "message": "Production item validated successfully",
            "data": response_data,
            "timestamp": now_datetime()
        }
    
    except Exception as e:
        frappe.log_error(message=str(e), title="Validate QC Defective Item API Error")
        return {
            "success": False,
            "message": f"Error validating item: {str(e)}",
            "data": None
        }


@frappe.whitelist()
@require_qc_roles()
def reclassify(production_item_name, defective_units):
    """
    API 3: Review and modify the status of production items
    Creates new scan log entries and marks old ones as cancelled
    
    Args:
        production_item_name (str): Name/ID of the production item
        defective_units (list): List of dicts containing:
            - defects: List of defect objects
            - status: New status (SP Rework, SP Pass, SP Reject, SP Recut)
            - remarks: Optional remarks
    
    Returns:
        dict: Success status and created scan log details
    """
    try:
        # Parse defective_units if it's a string (from API call)
        import json
        if isinstance(defective_units, str):
            defective_units = json.loads(defective_units)
        
        # Validate production item exists
        if not frappe.db.exists("Production Item", production_item_name):
            return {
                "success": False,
                "message": f"Production Item '{production_item_name}' not found"
            }
        
        # Get production item
        prod_item = frappe.get_doc("Production Item", production_item_name)
        
        # Validate last scan log exists
        if not prod_item.last_scan_log:
            return {
                "success": False,
                "message": "No scan log found for this production item"
            }
        
        # Get old scan log
        old_scan_log = frappe.get_doc("Item Scan Log", prod_item.last_scan_log)
        
        # Validate old scan log status
        if old_scan_log.status not in ["QC Rejected", "QC Recut"]:
            return {
                "success": False,
                "message": f"Item status is '{old_scan_log.status}', not QC Rejected or QC Recut"
            }
        
        # Validate new status
        valid_statuses = ["SP Rework", "SP Pass", "SP Rejected", "SP Recut"]
        defective_unit = defective_units[0]
        #TODO currently supporting only for DUT on so only one unit classfication no bundle classfication, so picking the only one obhect
        if defective_unit.get("status") not in valid_statuses:
            return {
                "success": False,
                "message": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            }
        
        # Start transaction
        frappe.db.begin()
        
        try:
            # Mark old scan log as cancelled
            old_scan_log.log_status = "SP Override"
            old_scan_log.remarks = f"Overriden by {frappe.session.user} for SP review. Original remarks: {old_scan_log.remarks or 'None'}"
            old_scan_log.save(ignore_permissions=True)
            
            # Create new scan log
            new_scan_log = frappe.get_doc({
                "doctype": "Item Scan Log",
                "production_item": prod_item.name,
                "operation": old_scan_log.operation,
                "workstation": old_scan_log.workstation,
                "physical_cell": old_scan_log.physical_cell,
                "scanned_by": frappe.session.user,
                "scan_time": old_scan_log.scan_time,
                "logged_time": old_scan_log.logged_time,
                "status": defective_unit.get("status"),
                "log_status": "Completed",
                "log_type": "User Scanned",
                "production_item_type": old_scan_log.production_item_type,
                "dut": old_scan_log.dut,
                "device_id": old_scan_log.device_id,
                "remarks": defective_unit.get("remarks", f"SP Review by {frappe.session.user}")
            })
            
            # Add defects
            defects = defective_unit.get("defects", [])
            for defect in defects:
                new_scan_log.append("defect_list", {
                    "defect": defect.get("defect"),
                    "defect_type": defect.get("defect_type"),
                    "defect_code": defect.get("defect_code"),
                    "defect_description": defect.get("defect_description"),
                    "severity": defect.get("severity"),
                    "defect_category": defect.get("defect_category")
                })
            
            new_scan_log.insert(ignore_permissions=True)
            
            # Update production item with new scan log
            prod_item.last_scan_log = new_scan_log.name
            prod_item.save(ignore_permissions=True)
            
            # Commit transaction
            frappe.db.commit()
            
            return {
                "success": True,
                "message": "Status updated successfully",
                "data": {
                    "old_scan_log": old_scan_log.name,
                    "new_scan_log": new_scan_log.name,
                    "new_status": new_scan_log.status,
                    "production_item": prod_item.name,
                    "defect_count": len(defects),
                    "updated_by": frappe.session.user,
                    "updated_time": str(now_datetime())
                }
            }
        
        except Exception as e:
            # Rollback on error
            frappe.db.rollback()
            raise e
    
    except Exception as e:
        frappe.local.response.http_status_code = 400
        frappe.log_error(message=str(e), title="Review and Update QC Status API Error")
        return {
            "success": False,
            "message": f"Error updating status: {str(e)}"
        }


# Additional utility function for bulk operations
@frappe.whitelist()
@require_qc_roles()
def bulk_review_and_update_qc_status(items_data):
    """
    Bulk version of API 3 for updating multiple production items
    
    Args:
        items_data (list): List of dicts containing:
            - production_item_name: Name/ID of production item
            - defects: List of defect objects
            - status: New status
            - remarks: Optional remarks
    
    Returns:
        dict: Success status with results for each item
    """
    try:
        import json
        if isinstance(items_data, str):
            items_data = json.loads(items_data)
        
        results = []
        success_count = 0
        failure_count = 0
        
        for item in items_data:
            result = review_and_update_qc_status(
                production_item_name=item.get("production_item_name"),
                updated_items={
                    "status": item.get("status"),
                    "defects": item.get("defects", []),
                    "remarks": item.get("remarks")
                }
            )
            
            results.append({
                "production_item": item.get("production_item_name"),
                "result": result
            })
            
            if result.get("success"):
                success_count += 1
            else:
                failure_count += 1
        
        return {
            "success": True,
            "message": f"Processed {len(items_data)} items: {success_count} succeeded, {failure_count} failed",
            "results": results,
            "summary": {
                "total": len(items_data),
                "success": success_count,
                "failure": failure_count
            },
            "timestamp": now_datetime()
        }
    
    except Exception as e:
        frappe.log_error(message=str(e), title="Bulk Review and Update QC Status API Error")
        return {
            "success": False,
            "message": f"Error in bulk update: {str(e)}"
        }