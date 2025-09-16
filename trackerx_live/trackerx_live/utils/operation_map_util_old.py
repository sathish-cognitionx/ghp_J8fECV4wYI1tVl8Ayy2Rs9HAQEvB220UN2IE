"""
Operation Map Utility for Manufacturing Flow Tracking
====================================================

This module provides comprehensive functionality for managing operation maps
in manufacturing workflows, including validation, caching, and flow tracking.
"""

from typing import Dict, List, Set, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import json
from collections import defaultdict, deque


class OperationType(Enum):
    """Types of operations in the manufacturing flow"""
    ACTIVATION = "Activation"
    UNLINK_LINK = "Unlink Link"
    PRODUCTION = "Production"
    QC = "QC"
    COUNT = "Count"
    OTHER = "Other"


@dataclass
class OperationNode:
    """Represents a single operation in the flow"""
    operation: str
    component: str
    operation_type: OperationType
    sequence_no: int = 1
    configs: Dict[str, Any] = field(default_factory=dict)
    next_operations: List['OperationNode'] = field(default_factory=list)
    previous_operations: List['OperationNode'] = field(default_factory=list)
    
    def __hash__(self):
        return hash((self.operation, self.component, self.sequence_no))
    
    def __eq__(self, other):
        if not isinstance(other, OperationNode):
            return False
        return (self.operation == other.operation and 
                self.component == other.component and 
                self.sequence_no == other.sequence_no)


@dataclass
class ValidationResult:
    """Result of operation map validation"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class OperationMapUtil:
    """
    Comprehensive utility for managing operation maps in manufacturing flows.
    Handles validation, caching, and flow tracking.
    """
    
    def __init__(self):
        self._cache = {}
        self._operation_graphs = {}  # item -> operation graph
        self._component_operations = {}  # (item, component) -> list of operations
        self._operation_lookup = {}  # (item, operation, component, seq) -> OperationNode
        
    def build_operation_map(self, item: str, operation_map_data: List[Dict]) -> ValidationResult:
        """
        Build and validate operation map from raw data
        
        Args:
            item: Item name/ID
            operation_map_data: List of operation map records
            
        Returns:
            ValidationResult with validation status and any errors
        """
        try:
            # Clear existing cache for this item
            self._clear_item_cache(item)
            
            # Create operation nodes
            nodes = self._create_operation_nodes(operation_map_data)
            
            # Build the graph structure
            self._build_graph_structure(item, nodes, operation_map_data)
            
            # Validate the operation map
            validation_result = self._validate_operation_map(item, nodes)
            
            if validation_result.is_valid:
                # Cache the validated structure
                self._cache_operation_map(item, nodes)
                
            return validation_result
            
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                errors=[f"Failed to build operation map: {str(e)}"]
            )
    
    def _create_operation_nodes(self, operation_map_data: List[Dict]) -> Dict[Tuple, OperationNode]:
        """Create operation nodes from raw data"""
        nodes = {}
        
        for record in operation_map_data:
            operation = record.get('operation', '')
            component = record.get('component', '')
            sequence_no = record.get('sequence_no', 1)
            configs = record.get('configs', {})
            
            # Determine operation type from configs or operation name
            operation_type = self._determine_operation_type(operation, configs)
            
            node_key = (operation, component, sequence_no)
            nodes[node_key] = OperationNode(
                operation=operation,
                component=component,
                operation_type=operation_type,
                sequence_no=sequence_no,
                configs=configs if isinstance(configs, dict) else {}
            )
        
        return nodes
    
    def _determine_operation_type(self, operation: str, configs: Dict) -> OperationType:
        """Determine operation type based on operation name and configs"""
        operation_lower = operation.lower()
        
        if 'activation' in operation_lower:
            return OperationType.ACTIVATION
        elif 'unlink' in operation_lower or 'link' in operation_lower:
            return OperationType.UNLINK_LINK
        elif 'qc' in operation_lower or 'quality' in operation_lower:
            return OperationType.QC
        elif 'count' in operation_lower:
            return OperationType.COUNT
        elif 'production' in operation_lower or 'manufacturing' in operation_lower:
            return OperationType.PRODUCTION
        else:
            return OperationType.OTHER
    
    def _build_graph_structure(self, item: str, nodes: Dict[Tuple, OperationNode], 
                             operation_map_data: List[Dict]):
        """Build the graph structure by connecting nodes"""
        
        # Create lookup for next operations
        for record in operation_map_data:
            current_key = (record.get('operation'), record.get('component'), 
                          record.get('sequence_no', 1))
            next_operation = record.get('next_operation')
            
            if current_key not in nodes:
                continue
                
            current_node = nodes[current_key]
            
            # Find next operation nodes
            if next_operation:
                next_nodes = self._find_next_operation_nodes(
                    next_operation, record.get('component'), nodes, operation_map_data
                )
                
                for next_node in next_nodes:
                    current_node.next_operations.append(next_node)
                    next_node.previous_operations.append(current_node)
    
    def _find_next_operation_nodes(self, next_operation: str, component: str,
                                 nodes: Dict[Tuple, OperationNode],
                                 operation_map_data: List[Dict]) -> List[OperationNode]:
        """Find all possible next operation nodes"""
        next_nodes = []
        
        for record in operation_map_data:
            if (record.get('operation') == next_operation and 
                record.get('component') == component):
                
                node_key = (record.get('operation'), record.get('component'),
                           record.get('sequence_no', 1))
                
                if node_key in nodes:
                    next_nodes.append(nodes[node_key])
        
        return next_nodes
    
    def _validate_operation_map(self, item: str, nodes: Dict[Tuple, OperationNode]) -> ValidationResult:
        """Validate the operation map for correctness"""
        errors = []
        warnings = []
        
        if not nodes:
            errors.append("Operation map is empty")
            return ValidationResult(is_valid=False, errors=errors)
        
        node_list = list(nodes.values())
        
        # Check for cycles
        cycle_result = self._detect_cycles(node_list)
        if cycle_result:
            errors.append(f"Cycle detected in operation flow: {cycle_result}")
        
        # Check for disconnected components
        disconnected = self._find_disconnected_components(node_list)
        if disconnected:
            warnings.extend([f"Disconnected operation: {op}" for op in disconnected])
        
        # Check for single final node
        final_nodes = self._find_final_nodes(node_list)
        if len(final_nodes) == 0:
            errors.append("No final operation found")
        elif len(final_nodes) > 1:
            final_components = set(node.component for node in final_nodes)
            if len(final_components) > 1:
                errors.append(f"Multiple final components found: {final_components}")
        
        # Check for activation operations
        activation_nodes = [n for n in node_list if n.operation_type == OperationType.ACTIVATION]
        if not activation_nodes:
            warnings.append("No activation operations found")
        
        # Validate Unlink/Link operations
        unlink_errors = self._validate_unlink_operations(node_list)
        errors.extend(unlink_errors)
        
        is_valid = len(errors) == 0
        return ValidationResult(is_valid=is_valid, errors=errors, warnings=warnings)
    
    def _detect_cycles(self, nodes: List[OperationNode]) -> Optional[str]:
        """Detect cycles in the operation flow using DFS"""
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {node: WHITE for node in nodes}
        
        def dfs(node):
            color[node] = GRAY
            for next_node in node.next_operations:
                if color[next_node] == GRAY:
                    return f"{node.operation}({node.component}) -> {next_node.operation}({next_node.component})"
                elif color[next_node] == WHITE and dfs(next_node):
                    return f"{node.operation}({node.component}) -> {next_node.operation}({next_node.component})"
            color[node] = BLACK
            return None
        
        for node in nodes:
            if color[node] == WHITE:
                cycle = dfs(node)
                if cycle:
                    return cycle
        
        return None
    
    def _find_disconnected_components(self, nodes: List[OperationNode]) -> List[str]:
        """Find operations that are not connected to the main flow"""
        if not nodes:
            return []
        
        # Find all nodes reachable from starting nodes
        start_nodes = [n for n in nodes if not n.previous_operations]
        if not start_nodes:
            start_nodes = nodes[:1]  # Use any node if no clear start
        
        visited = set()
        queue = deque(start_nodes)
        
        while queue:
            node = queue.popleft()
            if node in visited:
                continue
            visited.add(node)
            queue.extend(node.next_operations)
            queue.extend(node.previous_operations)
        
        disconnected = []
        for node in nodes:
            if node not in visited:
                disconnected.append(f"{node.operation}({node.component})")
        
        return disconnected
    
    def _find_final_nodes(self, nodes: List[OperationNode]) -> List[OperationNode]:
        """Find nodes that have no next operations (final operations)"""
        return [node for node in nodes if not node.next_operations]
    
    def _validate_unlink_operations(self, nodes: List[OperationNode]) -> List[str]:
        """Validate Unlink/Link operations have proper configurations"""
        errors = []
        
        for node in nodes:
            if node.operation_type == OperationType.UNLINK_LINK:
                configs = node.configs
                
                # Check if unlink operation has proper configuration
                if not configs:
                    errors.append(f"Unlink operation {node.operation} missing configuration")
                    continue
                
                # Validate merge/split configurations
                if 'merge_components' in configs and 'split_components' in configs:
                    errors.append(f"Unlink operation {node.operation} cannot have both merge and split")
        
        return errors
    
    def _cache_operation_map(self, item: str, nodes: Dict[Tuple, OperationNode]):
        """Cache the validated operation map for quick access"""
        self._operation_graphs[item] = nodes
        
        # Build component-operation lookup
        component_ops = defaultdict(list)
        operation_lookup = {}
        
        for node in nodes.values():
            component_ops[node.component].append(node)
            lookup_key = (item, node.operation, node.component, node.sequence_no)
            operation_lookup[lookup_key] = node
        
        self._component_operations[item] = dict(component_ops)
        self._operation_lookup.update(operation_lookup)
    
    def _clear_item_cache(self, item: str):
        """Clear cache for a specific item"""
        if item in self._operation_graphs:
            del self._operation_graphs[item]
        if item in self._component_operations:
            del self._component_operations[item]
        
        # Remove from operation lookup
        keys_to_remove = [k for k in self._operation_lookup.keys() if k[0] == item]
        for key in keys_to_remove:
            del self._operation_lookup[key]
    
    # Public API Methods
    
    def get_next_operations(self, item: str, current_operation: str, 
                           component: str, sequence_no: int = 1) -> List[OperationNode]:
        """Get next possible operations for a component after current operation"""
        lookup_key = (item, current_operation, component, sequence_no)
        
        if lookup_key not in self._operation_lookup:
            return []
        
        current_node = self._operation_lookup[lookup_key]
        return current_node.next_operations.copy()
    
    def get_previous_operations(self, item: str, current_operation: str,
                              component: str, sequence_no: int = 1) -> List[OperationNode]:
        """Get previous operations that lead to current operation"""
        lookup_key = (item, current_operation, component, sequence_no)
        
        if lookup_key not in self._operation_lookup:
            return []
        
        current_node = self._operation_lookup[lookup_key]
        return current_node.previous_operations.copy()
    
    def get_component_operations(self, item: str, component: str) -> List[OperationNode]:
        """Get all operations for a specific component"""
        if item not in self._component_operations:
            return []
        
        return self._component_operations[item].get(component, [])
    
    def get_skipped_operations(self, item: str, component: str, 
                              last_operation: str, current_operation: str) -> List[OperationNode]:
        """Get operations that were skipped between last and current operation"""
        if item not in self._operation_graphs:
            return []
        
        # Find path from last to current operation
        last_nodes = [n for n in self._operation_graphs[item].values() 
                     if n.operation == last_operation and n.component == component]
        current_nodes = [n for n in self._operation_graphs[item].values()
                        if n.operation == current_operation and n.component == component]
        
        if not last_nodes or not current_nodes:
            return []
        
        # Find shortest path and identify skipped operations
        skipped = []
        for last_node in last_nodes:
            for current_node in current_nodes:
                path = self._find_shortest_path(last_node, current_node)
                if path and len(path) > 2:  # More than direct connection
                    skipped.extend(path[1:-1])  # Exclude start and end
        
        return list(set(skipped))  # Remove duplicates
    
    def _find_shortest_path(self, start: OperationNode, end: OperationNode) -> List[OperationNode]:
        """Find shortest path between two operation nodes using BFS"""
        if start == end:
            return [start]
        
        queue = deque([(start, [start])])
        visited = {start}
        
        while queue:
            current, path = queue.popleft()
            
            for next_node in current.next_operations:
                if next_node == end:
                    return path + [next_node]
                
                if next_node not in visited:
                    visited.add(next_node)
                    queue.append((next_node, path + [next_node]))
        
        return []  # No path found
    
    def is_valid_transition(self, item: str, component: str, 
                           from_operation: str, to_operation: str) -> bool:
        """Check if transition from one operation to another is valid"""
        next_ops = self.get_next_operations(item, from_operation, component)
        return any(op.operation == to_operation for op in next_ops)
    
    def get_starting_operations(self, item: str, component: str) -> List[OperationNode]:
        """Get operations that can be starting points for a component"""
        if item not in self._component_operations:
            return []
        
        component_ops = self._component_operations[item].get(component, [])
        return [op for op in component_ops if not op.previous_operations]
    
    def get_final_operations(self, item: str, component: str) -> List[OperationNode]:
        """Get final operations for a component"""
        if item not in self._component_operations:
            return []
        
        component_ops = self._component_operations[item].get(component, [])
        return [op for op in component_ops if not op.next_operations]
    
    def get_operation_flow(self, item: str, component: str) -> List[List[OperationNode]]:
        """Get all possible operation flows for a component"""
        start_ops = self.get_starting_operations(item, component)
        final_ops = self.get_final_operations(item, component)
        
        all_paths = []
        for start_op in start_ops:
            for final_op in final_ops:
                path = self._find_shortest_path(start_op, final_op)
                if path:
                    all_paths.append(path)
        
        return all_paths
    
    def get_all_components(self, item: str) -> List[str]:
        """Get all components in the operation map"""
        if item not in self._component_operations:
            return []
        
        return list(self._component_operations[item].keys())
    
    def export_operation_map(self, item: str) -> Dict:
        """Export operation map structure for serialization"""
        if item not in self._operation_graphs:
            return {}
        
        nodes_data = []
        for node in self._operation_graphs[item].values():
            nodes_data.append({
                'operation': node.operation,
                'component': node.component,
                'operation_type': node.operation_type.value,
                'sequence_no': node.sequence_no,
                'configs': node.configs,
                'next_operations': [(n.operation, n.component, n.sequence_no) 
                                   for n in node.next_operations]
            })
        
        return {
            'item': item,
            'nodes': nodes_data,
            'components': self.get_all_components(item)
        }
    
    def clear_cache(self):
        """Clear all cached data"""
        self._cache.clear()
        self._operation_graphs.clear()
        self._component_operations.clear()
        self._operation_lookup.clear()


# Example usage and testing
if __name__ == "__main__":
    # Sample operation map data
    operation_data = [
        {
            'operation': 'Fabric Cutting',
            'component': 'Body',
            'next_operation': 'Sewing',
            'sequence_no': 1,
            'configs': {}
        },
        {
            'operation': 'Sewing',
            'component': 'Body',
            'next_operation': 'Quality Check',
            'sequence_no': 1,
            'configs': {}
        },
        {
            'operation': 'Quality Check',
            'component': 'Body',
            'next_operation': 'Packaging',
            'sequence_no': 1,
            'configs': {}
        },
        {
            'operation': 'Packaging',
            'component': 'Body',
            'next_operation': '',
            'sequence_no': 1,
            'configs': {}
        }
    ]
    
    # Initialize utility
    op_util = OperationMapUtil()
    
    # Build and validate operation map
    result = op_util.build_operation_map('T-Shirt', operation_data)
    
    print(f"Validation Result: {result.is_valid}")
    if result.errors:
        print(f"Errors: {result.errors}")
    if result.warnings:
        print(f"Warnings: {result.warnings}")
    
    # Test API methods
    if result.is_valid:
        next_ops = op_util.get_next_operations('T-Shirt', 'Fabric Cutting', 'Body')
        print(f"Next operations after Fabric Cutting: {[op.operation for op in next_ops]}")
        
        starting_ops = op_util.get_starting_operations('T-Shirt', 'Body')
        print(f"Starting operations: {[op.operation for op in starting_ops]}")
        
        flow = op_util.get_operation_flow('T-Shirt', 'Body')
        print(f"Operation flow: {[[op.operation for op in path] for path in flow]}")