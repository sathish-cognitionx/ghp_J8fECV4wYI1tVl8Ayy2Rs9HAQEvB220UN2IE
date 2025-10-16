import frappe
from frappe.model.document import Document
from frappe.utils import flt
import math
import json
from collections import defaultdict

def cuttingx_cut_kit_plan_on_submit(doc, method=None):
    update_operation_map(doc, method=None)


def update_operation_map(doc, method=None):

    process_map_name = doc.operation_map
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

    for entry in operation_map_entries:
        operation_row = frappe.new_doc("Operation Map")
        operation_row.operation = entry["operation"]
        operation_row.component = entry["component"]
        operation_row.next_operation = entry["next_operation"]
        operation_row.sequence_no = entry["sequence_no"]
        operation_row.configs = entry["configs"] or {}
        operation_row.parent = doc.name
        operation_row.parenttype = "Cut Kit Plan"
        operation_row.parentfield = "table_operation_map"
        
        doc.table_operation_map.append(operation_row)
    
    doc.save()