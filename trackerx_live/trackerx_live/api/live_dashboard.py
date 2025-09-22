import frappe
from datetime import datetime, timedelta
from frappe.utils import now_datetime, today, get_datetime


@frappe.whitelist()
def get_production_count(**kwargs):
    """
    API to get production count based on Item Scan Log
    
    Parameters:
    - period: 'current_hour', 'last_one_hour', 'today' (default: 'today')
    - device_id: string or list of device IDs
    - workstation: string or list of workstations
    - operation: string or list of operations
    - physical_cell: string or list of physical cells
    
    Returns:
    {
        "data": {
            "output_count": 0,
            "ie_target": "",
            "full_ie_target": "",
            "plan_target": "",
            "color": "RED"
        }
    }
    """
    try:
        # Get parameters
        period = kwargs.get('period', 'today')
        device_id = kwargs.get('device_id')
        workstation = kwargs.get('workstation')
        operation = kwargs.get('operation')
        physical_cell = kwargs.get('physical_cell')
        
        # Build filters
        filters = build_filters(period, device_id, workstation, operation, physical_cell, status_filter='Pass')
        
        # Get production count
        output_count = get_output_count(filters)
        
        # Calculate other targets (placeholder functions for future integration)
        ie_target = get_ie_target(filters)
        full_ie_target = get_full_ie_target(filters)
        plan_target = get_plan_target(filters)
        output_color = get_output_color(output_count, ie_target, full_ie_target, plan_target)
        
        return {
            "data": {
                "output_count": output_count,
                "ie_target": ie_target,
                "full_ie_target": full_ie_target,
                "plan_target": plan_target,
                "color": output_color
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Error in get_production_count: {str(e)}")
        return {
            "data": {
                "output_count": 0,
                "ie_target": "",
                "full_ie_target": "",
                "plan_target": "",
                "color": "RED"
            },
            "error": str(e)
        }


def build_filters(period, device_id=None, workstation=None, operation=None, physical_cell=None, status_filter=None):
    """Build filters for the query based on input parameters"""
    filters = {
        'log_status': 'Completed'
    }
    
    # Add status filter if provided
    if status_filter:
        if isinstance(status_filter, list):
            filters['status'] = ['in', status_filter]
        else:
            filters['status'] = status_filter
    
    # Add time-based filters
    time_filters = get_time_filters(period)
    filters.update(time_filters)
    
    # Add optional filters
    if device_id:
        if isinstance(device_id, str):
            filters['device_id'] = device_id
        elif isinstance(device_id, list):
            filters['device_id'] = ['in', device_id]
    
    if workstation:
        if isinstance(workstation, str):
            filters['workstation'] = workstation
        elif isinstance(workstation, list):
            filters['workstation'] = ['in', workstation]
    
    if operation:
        if isinstance(operation, str):
            filters['operation'] = operation
        elif isinstance(operation, list):
            filters['operation'] = ['in', operation]
    
    if physical_cell:
        if isinstance(physical_cell, str):
            filters['physical_cell'] = physical_cell
        elif isinstance(physical_cell, list):
            filters['physical_cell'] = ['in', physical_cell]
    
    return filters


def get_time_filters(period):
    """Get time-based filters based on period"""
    current_time = now_datetime()
    
    if period == 'current_hour':
        # From current hour start to now
        start_time = current_time.replace(minute=0, second=0, microsecond=0)
        return {
            'logged_time': ['between', [start_time, current_time]]
        }
    
    elif period == 'last_one_hour':
        # From now-1hour to now
        end_time = current_time
        start_time = current_time - timedelta(hours=1)
        return {
            'logged_time': ['between', [start_time, end_time]]
        }
    
    elif period == 'today':
        # Today's data
        start_time = get_datetime(today() + " 00:00:00")
        return {
            'logged_time': ['>=', start_time]
        }
    
    else:
        # Default to today
        start_time = get_datetime(today() + " 00:00:00")
        return {
            'logged_time': ['>=', start_time]
        }


def get_output_count(filters):
    """Calculate the total production count based on filters"""
    try:
        # Get all Item Scan Log records that match the filters
        scan_logs = frappe.get_all(
            'Item Scan Log',
            filters=filters,
            fields=['production_item']
        )
        
        if not scan_logs:
            return 0
        
        # Get unique production items
        production_items = list(set([log.production_item for log in scan_logs]))
        
        # Calculate total quantity
        total_quantity = 0
        
        for item in production_items:
            # Get quantity from Production Item
            item_doc = frappe.get_doc('Production Item', item)
            quantity = item_doc.get('quantity', 1)  # Default to 1 if quantity field doesn't exist
            total_quantity += quantity
        
        return total_quantity
        
    except Exception as e:
        frappe.log_error(f"Error in get_output_count: {str(e)}")
        return 0


# Placeholder functions for future integration
def get_ie_target(filters):
    """
    Placeholder function to calculate IE Target
    To be implemented based on your business logic
    """
    return ""


def get_full_ie_target(filters):
    """
    Placeholder function to calculate Full IE Target
    To be implemented based on your business logic
    """
    return ""


def get_plan_target(filters):
    """
    Placeholder function to calculate Plan Target
    To be implemented based on your business logic
    """
    return ""


def get_output_color(output_count, ie_target, full_ie_target, plan_target):
    """
    Placeholder function to determine output color
    To be implemented based on your business logic
    
    Possible values: RED, YELLOW, GREEN, WHITE
    """
    # Default logic - can be customized later
    if output_count == 0:
        return "RED"
    else:
        return "WHITE"  # Default color until logic is implemented


# Alternative API endpoint for direct HTTP calls
@frappe.whitelist(allow_guest=False, methods=['GET', 'POST'])
def production_count_api():
    """
    HTTP API endpoint for production count
    Can be called via: /api/method/your_app.your_module.api.production_count_api
    """
    # Get parameters from request
    if frappe.request.method == 'GET':
        kwargs = frappe.request.args
    else:
        kwargs = frappe.request.json or {}
    
    return get_production_count(**kwargs)


# Utility function to validate and convert parameters
def validate_parameters(kwargs):
    """Validate and convert input parameters"""
    validated = {}
    
    # Validate period
    valid_periods = ['current_hour', 'last_one_hour', 'today']
    period = kwargs.get('period', 'today')
    if period not in valid_periods:
        period = 'today'
    validated['period'] = period
    
    # Convert string lists to actual lists for multi-value parameters
    multi_value_params = ['device_id', 'workstation', 'operation', 'physical_cell']
    for param in multi_value_params:
        value = kwargs.get(param)
        if value:
            if isinstance(value, str) and ',' in value:
                # Convert comma-separated string to list
                validated[param] = [v.strip() for v in value.split(',')]
            else:
                validated[param] = value
    
    return validated


# Example usage function for testing
def test_production_count():
    """Test function to demonstrate API usage"""
    
    # Test 1: Get today's count for all
    result1 = get_production_count(period='today')
    print("Today's total count:", result1)
    
    # Test 2: Get current hour count for specific workstation
    result2 = get_production_count(
        period='current_hour',
        workstation='WS001'
    )
    print("Current hour count for WS001:", result2)
    
    # Test 3: Get last hour count for multiple operations
    result3 = get_production_count(
        period='last_one_hour',
        operation=['OP001', 'OP002']
    )
    print("Last hour count for multiple operations:", result3)
    
    return [result1, result2, result3]


@frappe.whitelist()
def get_defective_unit_count(**kwargs):
    """
    API to get defective unit count based on Item Scan Log
    
    Parameters:
    - period: 'current_hour', 'last_one_hour', 'today' (default: 'today')
    - device_id: string or list of device IDs
    - workstation: string or list of workstations
    - operation: string or list of operations
    - physical_cell: string or list of physical cells
    
    Returns count of Item Scan Log records with status = QC Rework, QC Reject, or QC Recut
    """
    try:
        # Get parameters
        period = kwargs.get('period', 'today')
        device_id = kwargs.get('device_id')
        workstation = kwargs.get('workstation')
        operation = kwargs.get('operation')
        physical_cell = kwargs.get('physical_cell')
        
        # Build filters with defect statuses
        defect_statuses = ['QC Rework', 'QC Reject', 'QC Recut']
        filters = build_filters(period, device_id, workstation, operation, physical_cell, status_filter=defect_statuses)
        
        # Get defective unit count (count of records, not sum of quantities)
        defective_count = frappe.db.count('Item Scan Log', filters)
        
        return {
            "data": {
                "defective_unit_count": defective_count,
                "limit": 0,
                "color": "YELLOW"
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Error in get_defective_unit_count: {str(e)}")
        return {
            "data": {
                "defective_unit_count": 0,
                "limit": 0,
                "color": "WHITE"
            },
            "error": str(e)
        }


@frappe.whitelist()
def get_defects_count(**kwargs):
    """
    API to get total defects count based on child table entries
    
    Parameters:
    - period: 'current_hour', 'last_one_hour', 'today' (default: 'today')
    - device_id: string or list of device IDs
    - workstation: string or list of workstations
    - operation: string or list of operations
    - physical_cell: string or list of physical cells
    
    Returns count of defect entries in the child table
    """
    try:
        # Get parameters
        period = kwargs.get('period', 'today')
        device_id = kwargs.get('device_id')
        workstation = kwargs.get('workstation')
        operation = kwargs.get('operation')
        physical_cell = kwargs.get('physical_cell')
        
        # Build filters for Item Scan Log
        filters = build_filters(period, device_id, workstation, operation, physical_cell)
        
        # Get Item Scan Log records that match the filters
        scan_logs = frappe.get_all(
            'Item Scan Log',
            filters=filters,
            fields=['name']
        )
        
        if not scan_logs:
            return {
                "data": {
                    "defects_count": 0,
                    "limit": 0,
                    "color": "GREEN"
                }
            }
        
        # Get defect count from child table
        parent_names = [log.name for log in scan_logs]
        defects_count = frappe.db.count(
            'Item Scan Log Defect',
            {'parent': ['in', parent_names]}
        )
        
        return {
            "data": {
                "defects_count": defects_count,
                "limit": 0,
                "color": "GREEN"
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Error in get_defects_count: {str(e)}")
        return {
            "data": {
                "defects_count": 0,
                "limit": 0,
                "color": "WHITE"
            },
            "error": str(e)
        }


@frappe.whitelist()
def get_top_defects_last_hour(**kwargs):
    """
    API to get top defects in the last 1 hour
    
    Parameters:
    - device_id: string or list of device IDs
    - workstation: string or list of workstations
    - operation: string or list of operations
    - physical_cell: string or list of physical cells
    
    Returns list of defects ordered by frequency (most used first)
    """
    try:
        # Get parameters
        device_id = kwargs.get('device_id')
        workstation = kwargs.get('workstation')
        operation = kwargs.get('operation')
        physical_cell = kwargs.get('physical_cell')
        
        # Build filters for last 1 hour
        filters = build_filters('last_one_hour', device_id, workstation, operation, physical_cell)
        
        # Get Item Scan Log records from last hour
        scan_logs = frappe.get_all(
            'Item Scan Log',
            filters=filters,
            fields=['name']
        )
        
        if not scan_logs:
            return {
                "data": {
                    "top_defects": []
                }
            }
        
        # Get defects from child table with frequency count
        parent_names = [log.name for log in scan_logs]
        
        defects_data = frappe.db.sql("""
            SELECT 
                defect,
                defect_code,
                defect_description,
                defect_type,
                severity,
                COUNT(*) as frequency
            FROM `tabItem Scan Log Defect`
            WHERE parent IN %(parent_names)s
                AND defect IS NOT NULL
            GROUP BY defect, defect_code, defect_description, defect_type, severity
            ORDER BY frequency DESC
        """, {'parent_names': parent_names}, as_dict=True)
        
        return {
            "data": {
                "top_defects": defects_data
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Error in get_top_defects_last_hour: {str(e)}")
        return {
            "data": {
                "top_defects": []
            },
            "error": str(e)
        }


@frappe.whitelist()
def get_output_line_graph(**kwargs):
    """
    API to get hourly output count for today (line graph data)
    
    Parameters:
    - device_id: string or list of device IDs
    - workstation: string or list of workstations
    - operation: string or list of operations
    - physical_cell: string or list of physical cells
    
    Returns hourly output data for the current day (max 24 points)
    """
    try:
        # Get parameters
        device_id = kwargs.get('device_id')
        workstation = kwargs.get('workstation')
        operation = kwargs.get('operation')
        physical_cell = kwargs.get('physical_cell')
        
        # Build base filters (without time filter)
        filters = {
            'log_status': 'Completed',
            'status': 'Pass'
        }
        
        # Add optional filters
        if device_id:
            if isinstance(device_id, str):
                filters['device_id'] = device_id
            elif isinstance(device_id, list):
                filters['device_id'] = ['in', device_id]
        
        if workstation:
            if isinstance(workstation, str):
                filters['workstation'] = workstation
            elif isinstance(workstation, list):
                filters['workstation'] = ['in', workstation]
        
        if operation:
            if isinstance(operation, str):
                filters['operation'] = operation
            elif isinstance(operation, list):
                filters['operation'] = ['in', operation]
        
        if physical_cell:
            if isinstance(physical_cell, str):
                filters['physical_cell'] = physical_cell
            elif isinstance(physical_cell, list):
                filters['physical_cell'] = ['in', physical_cell]
        
        # Get today's start time
        today_start = get_datetime(today() + " 00:00:00")
        current_time = now_datetime()
        
        # Initialize hourly data
        hourly_data = []
        
        for hour in range(24):
            hour_start = today_start + timedelta(hours=hour)
            hour_end = hour_start + timedelta(hours=1)
            
            # Skip future hours
            if hour_start > current_time:
                hourly_data.append({
                    "hour": f"{hour:02d}:00",
                    "hour_label": f"{hour:02d}:00-{(hour+1)%24:02d}:00",
                    "output_count": 0
                })
                continue
            
            # Adjust end time for current hour
            if hour_end > current_time:
                hour_end = current_time
            
            # Build time-specific filters
            hour_filters = filters.copy()
            hour_filters['logged_time'] = ['between', [hour_start, hour_end]]
            
            # Get scan logs for this hour
            scan_logs = frappe.get_all(
                'Item Scan Log',
                filters=hour_filters,
                fields=['production_item']
            )
            
            # Calculate quantity for this hour
            hour_count = 0
            if scan_logs:
                production_items = list(set([log.production_item for log in scan_logs]))
                
                for item in production_items:
                    try:
                        item_doc = frappe.get_doc('Production Item', item)
                        quantity = item_doc.get('quantity', 1)
                        hour_count += quantity
                    except:
                        hour_count += 1  # Default to 1 if item not found
            
            hourly_data.append({
                "hour": f"{hour:02d}:00",
                "hour_label": f"{hour:02d}:00-{(hour+1)%24:02d}:00",
                "output_count": hour_count
            })
        
        return {
            "data": {
                "hourly_output": hourly_data,
                "total_today": sum([h['output_count'] for h in hourly_data])
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Error in get_output_line_graph: {str(e)}")
        return {
            "data": {
                "hourly_output": [],
                "total_today": 0
            },
            "error": str(e)
        }


# HTTP API endpoints for all the new functions
@frappe.whitelist(allow_guest=False, methods=['GET', 'POST'])
def defective_unit_count_api():
    """HTTP API endpoint for defective unit count"""
    if frappe.request.method == 'GET':
        kwargs = frappe.request.args
    else:
        kwargs = frappe.request.json or {}
    
    return get_defective_unit_count(**kwargs)


@frappe.whitelist(allow_guest=False, methods=['GET', 'POST'])
def defects_count_api():
    """HTTP API endpoint for defects count"""
    if frappe.request.method == 'GET':
        kwargs = frappe.request.args
    else:
        kwargs = frappe.request.json or {}
    
    return get_defects_count(**kwargs)


@frappe.whitelist(allow_guest=False, methods=['GET', 'POST'])
def top_defects_api():
    """HTTP API endpoint for top defects"""
    if frappe.request.method == 'GET':
        kwargs = frappe.request.args
    else:
        kwargs = frappe.request.json or {}
    
    return get_top_defects_last_hour(**kwargs)


@frappe.whitelist(allow_guest=False, methods=['GET', 'POST'])
def output_line_graph_api():
    """HTTP API endpoint for output line graph"""
    if frappe.request.method == 'GET':
        kwargs = frappe.request.args
    else:
        kwargs = frappe.request.json or {}
    
    return get_output_line_graph(**kwargs)