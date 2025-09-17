
import frappe
import json
from collections import defaultdict
from frappe.model.docstatus import DocStatus

def generate_operation_map_from_item(item):
    
    try:
        # Fetch the Process Map document
        submitted_process_maps = frappe.get_list(
            "Process Map",
            filters={
                "select_fg": item,
                "docstatus": 1  # Filters for submitted documents
            },
            order_by='modified desc'
            # You can add other parameters like 'fields', 'order_by', 'limit', etc.
            # For example, to get all fields: fields=["*"]
        )

        if not submitted_process_maps:
            raise Exception(f"No approved process map(s) found for {item}")
        
        process_map_name = submitted_process_maps[0].name

        if len(submitted_process_maps) > 1:
            frappe.msgprint(f"Found more than 1 process map for {item}, Choosing the latest Process Map {process_map_name}")
        
        process_map_doc = frappe.get_doc("Process Map", process_map_name)
        
        # Parse nodes and edges JSON
        nodes_json = process_map_doc.nodes or "[]"
        edges_json = process_map_doc.edges or "[]"
        
        nodes = json.loads(nodes_json)
        edges = json.loads(edges_json)
        
        # Create a mapping of node IDs to node labels (operation names)
        node_id_to_label = {}
        for node in nodes:
            node_id_to_label[node['id']] = node['label']
        
        # Track sequence numbers for each operation-component combination
        sequence_tracker = defaultdict(int)
        
        # Process edges to create operation map entries
        operation_map_entries = []
        
        for edge in edges:
            source_operation = node_id_to_label.get(edge['source'])
            target_operation = node_id_to_label.get(edge['target'])
            components = edge.get('components', [])
            
            # Skip if source or target operation not found
            if not source_operation or not target_operation:
                continue
            
            # Create an entry for each component in the edge
            for component in components:
                # Create unique key for sequence tracking
                sequence_key = f"{source_operation}|{component}"
                sequence_tracker[sequence_key] += 1
                
                operation_entry = {
                    'operation': source_operation,
                    'component': component,
                    'next_operation': target_operation,
                    'sequence_no': sequence_tracker[sequence_key],
                    'configs': {}
                }
                
                operation_map_entries.append(operation_entry)
        
        return {
            "map_name": process_map_name, 
            "operation_map_entries": operation_map_entries
        }
        
    except Exception as e:
        raise e
