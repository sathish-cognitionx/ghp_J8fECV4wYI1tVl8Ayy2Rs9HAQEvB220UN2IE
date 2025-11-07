import frappe

def get_all_parent_production_items(production_item_name):
    """
    Recursively find all parent production items from Switch Log.
    
    Args:
        production_item_name (str): Name of the production item
        
    Returns:
        list: List of all parent production item names
    """
    all_parents = []
    visited = set()  # To prevent infinite loops
    
    def find_parents(item_name):
        # Prevent infinite recursion
        if item_name in visited:
            return
        
        visited.add(item_name)
        
        # Find all Switch Logs where this item is in 'to_production_items'
        switch_logs = frappe.db.sql("""
            SELECT DISTINCT parent
            FROM `tabSwitch Log Production Item`
            WHERE production_item = %s
            AND parentfield = 'to_production_items'
        """, (item_name,), as_dict=True)
        
        # For each Switch Log found, get all items from 'from_production_items'
        for log in switch_logs:
            parent_items = frappe.db.sql("""
                SELECT production_item
                FROM `tabSwitch Log Production Item`
                WHERE parent = %s
                AND parentfield = 'from_production_items'
            """, (log.parent,), as_dict=True)
            
            # Add parent items to the result and recursively find their parents
            for parent_item in parent_items:
                parent_name = parent_item.production_item
                if parent_name and parent_name not in all_parents:
                    all_parents.append(parent_name)
                    # Recursively find parents of this parent item
                    find_parents(parent_name)
    
    # Start the recursive search
    find_parents(production_item_name)
    
    return all_parents


# Alternative version with more details
def get_all_parent_production_items_detailed(production_item_name):
    """
    Recursively find all parent production items with switch log details.
    
    Args:
        production_item_name (str): Name of the production item
        
    Returns:
        list: List of dicts with parent item details and switch log info
    """
    all_parents = []
    visited = set()
    
    def find_parents(item_name, level=0):
        if item_name in visited:
            return
        
        visited.add(item_name)
        
        # Find Switch Logs where this item is in 'to_production_items'
        switch_logs = frappe.db.sql("""
            SELECT DISTINCT slpi.parent
            FROM `tabSwitch Log Production Item` slpi
            INNER JOIN `tabSwitch Log` sl ON sl.name = slpi.parent
            WHERE slpi.production_item = %s
            AND slpi.parentfield = 'to_production_items'
            ORDER BY sl.switched_on DESC
        """, (item_name,), as_dict=True)
        
        for log in switch_logs:
            # Get Switch Log details
            switch_log = frappe.get_doc("Switch Log", log.parent)
            
            # Get parent items from 'from_production_items'
            parent_items = frappe.db.sql("""
                SELECT production_item
                FROM `tabSwitch Log Production Item`
                WHERE parent = %s
                AND parentfield = 'from_production_items'
            """, (log.parent,), as_dict=True)
            
            for parent_item in parent_items:
                parent_name = parent_item.production_item
                if parent_name:
                    all_parents.append({
                        "production_item": parent_name,
                        "switch_log": log.parent,
                        "switch_type": switch_log.switch_type,
                        "switched_on": switch_log.switched_on,
                        "switched_by": switch_log.switched_by,
                        "level": level
                    })
                    # Recursively find parents
                    find_parents(parent_name, level + 1)
    
    find_parents(production_item_name)
    
    return all_parents