"""
Operation Map Data Structure for Tracking Order Level Management
===============================================================

This module provides operation map management at tracking order level,
where each tracking order has its own OperationMapData instance with
all nodes and flow logic encapsulated.
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
    UNLINK = "Unlink"
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
    
    def to_dict(self) -> Dict:
        """Convert node to dictionary representation"""
        return {
            'operation': self.operation,
            'component': self.component,
            'operation_type': self.operation_type.value,
            'sequence_no': self.sequence_no,
            'configs': self.configs,
            'next_operations': [(n.operation, n.component, n.sequence_no) 
                               for n in self.next_operations],
            'previous_operations': [(n.operation, n.component, n.sequence_no) 
                                   for n in self.previous_operations]
        }


@dataclass
class ValidationResult:
    """Result of operation map validation"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class OperationMapData:
    """
    Operation Map Data structure for a specific tracking order.
    Contains all nodes, relationships, and provides public API methods
    for operation flow management.
    """
    
    def __init__(self, tracking_order_number: str):
        self.tracking_order_number = tracking_order_number
        self.is_built = False
        self.validation_result = None
        
        # Core data structures
        self._nodes = {}  # (operation, component, sequence_no) -> OperationNode
        self._component_operations = {}  # component -> list of OperationNodes
        self._operation_lookup = {}  # (operation, component, sequence_no) -> OperationNode
        self._components = set()
        
        # Flow analysis cache
        self._starting_operations_cache = {}
        self._final_operations_cache = {}
        self._flow_paths_cache = {}
    
    def build_from_operation_map(self, operation_map_data: List[Dict]) -> ValidationResult:
        """
        Build operation map from tracking order's operation map data
        
        Args:
            operation_map_data: List of operation map records from tracking order
            
        Returns:
            ValidationResult with validation status and any errors
        """
        try:
            # Reset state
            self._reset_data_structures()
            
            # Create operation nodes
            self._create_operation_nodes(operation_map_data)
            
            # Build the graph structure
            self._build_graph_structure(operation_map_data)
            
            # Validate the operation map
            self.validation_result = self._validate_operation_map()
            
            if self.validation_result.is_valid:
                # Build lookup structures and caches
                self._build_lookup_structures()
                self.is_built = True
            
            return self.validation_result
            
        except Exception as e:
            self.validation_result = ValidationResult(
                is_valid=False,
                errors=[f"Failed to build operation map: {str(e)}"]
            )
            return self.validation_result
    
    def _reset_data_structures(self):
        """Reset all internal data structures"""
        self._nodes.clear()
        self._component_operations.clear()
        self._operation_lookup.clear()
        self._components.clear()
        self._starting_operations_cache.clear()
        self._final_operations_cache.clear()
        self._flow_paths_cache.clear()
        self.is_built = False
    
    def _create_operation_nodes(self, operation_map_data: List[Dict]):
        """Create operation nodes from raw data"""
        for record in operation_map_data:
            operation = record.get('operation', '')
            component = record.get('component', '')
            sequence_no = record.get('sequence_no', 1)
            configs = record.get('configs', {})
            
            if not operation or not component:
                continue
            
            # Determine operation type
            operation_type = self._determine_operation_type(operation, configs)
            
            # Create node
            node_key = (operation, component, sequence_no)
            self._nodes[node_key] = OperationNode(
                operation=operation,
                component=component,
                operation_type=operation_type,
                sequence_no=sequence_no,
                configs=configs if isinstance(configs, dict) else {}
            )
            
            self._components.add(component)
    
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
    
    def _build_graph_structure(self, operation_map_data: List[Dict]):
        """Build the graph structure by connecting nodes"""
        for record in operation_map_data:
            current_key = (record.get('operation'), record.get('component'), 
                          record.get('sequence_no', 1))
            next_operation = record.get('next_operation')
            
            if current_key not in self._nodes or not next_operation:
                continue
                
            current_node = self._nodes[current_key]
            
            # Find next operation nodes
            next_nodes = self._find_next_operation_nodes(
                next_operation, record.get('component'), operation_map_data
            )
            
            for next_node in next_nodes:
                current_node.next_operations.append(next_node)
                next_node.previous_operations.append(current_node)
    
    def _find_next_operation_nodes(self, next_operation: str, component: str,
                                 operation_map_data: List[Dict]) -> List[OperationNode]:
        """Find all possible next operation nodes"""
        next_nodes = []
        
        for record in operation_map_data:
            if (record.get('operation') == next_operation and 
                record.get('component') == component):
                
                node_key = (record.get('operation'), record.get('component'),
                           record.get('sequence_no', 1))
                
                if node_key in self._nodes:
                    next_nodes.append(self._nodes[node_key])
        
        return next_nodes
    
    def _validate_operation_map(self) -> ValidationResult:
        """Validate the operation map for correctness"""
        errors = []
        warnings = []
        
        if not self._nodes:
            errors.append("Operation map is empty")
            return ValidationResult(is_valid=False, errors=errors)
        
        node_list = list(self._nodes.values())
        
        # Check for cycles
        cycle_result = self._detect_cycles(node_list)
        if cycle_result:
            errors.append(f"Cycle detected in operation flow: {cycle_result}")
        
        # Check for disconnected components
        disconnected = self._find_disconnected_components(node_list)
        if disconnected:
            warnings.extend([f"Disconnected operation: {op}" for op in disconnected])
        
        # Check for single final component (can have multiple final operations)
        final_nodes = self._find_final_nodes(node_list)
        if len(final_nodes) == 0:
            errors.append("No final operation found")
        else:
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
            start_nodes = nodes[:1]
        
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
                
                if not configs:
                    errors.append(f"Unlink operation {node.operation} missing configuration")
                    continue
                
                # Validate merge/split configurations
                if 'merge_components' in configs and 'split_components' in configs:
                    errors.append(f"Unlink operation {node.operation} cannot have both merge and split")
        
        return errors
    
    def _build_lookup_structures(self):
        """Build lookup structures for fast access"""
        # Build component operations lookup
        component_ops = defaultdict(list)
        
        for node in self._nodes.values():
            component_ops[node.component].append(node)
            
            # Build operation lookup
            lookup_key = (node.operation, node.component, node.sequence_no)
            self._operation_lookup[lookup_key] = node
        
        self._component_operations = dict(component_ops)
    
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
        
        return []
    
    # PUBLIC API METHODS
    
    def is_valid(self) -> bool:
        """Check if operation map is valid and built"""
        return self.is_built and self.validation_result and self.validation_result.is_valid
    
    def get_validation_result(self) -> Optional[ValidationResult]:
        """Get validation result"""
        return self.validation_result
    
    def get_next_operations(self, current_operation: str, component: str, 
                           sequence_no: int = 1) -> List[OperationNode]:
        """Get next possible operations for a component after current operation"""
        if not self.is_valid():
            return []
            
        lookup_key = (current_operation, component, sequence_no)
        
        if lookup_key not in self._operation_lookup:
            return []
        
        current_node = self._operation_lookup[lookup_key]
        return current_node.next_operations.copy()

    def get_next_operation(self, current_operation: str, component: str, 
                           sequence_no: int = 1) -> List[OperationNode]:
        next_operations = self.get_next_operations(current_operation, component, sequence_no)
        if next_operations:
            return next_operations[0]
        return None
    
    def get_previous_operations(self, current_operation: str, component: str,
                              sequence_no: int = 1) -> List[OperationNode]:
        """Get previous operations that lead to current operation"""
        if not self.is_valid():
            return []
            
        lookup_key = (current_operation, component, sequence_no)
        
        if lookup_key not in self._operation_lookup:
            return []
        
        current_node = self._operation_lookup[lookup_key]
        return current_node.previous_operations.copy()
    
    def get_previous_operation(self, current_operation: str, component: str, 
                           sequence_no: int = 1) -> List[OperationNode]:
        prev_operations = self.get_previous_operations(current_operation, component, sequence_no)
        if prev_operations:
            return prev_operations[0]
        return None
    
    def get_all_previous_operations(self, current_operation: str, component: str, 
                        sequence_no: int = 1) -> List[str]:
        """
        Recursively get all previous operations for a given operation.
        Returns a list of operation names (strings) from all previous operations
        in the dependency chain.
        """
        all_prev_operations = []
        visited = set()  # To prevent infinite loops in case of cycles
        
        def _collect_previous_recursive(op_name: str, comp_name: str, seq_no: int):
            # Create a unique identifier for this operation
            op_id = (op_name, comp_name, seq_no)
            
            # Skip if already visited (prevents infinite loops)
            if op_id in visited:
                return
            
            visited.add(op_id)
            
            # Get immediate previous operations for current operation
            prev_operations = self.get_previous_operations(op_name, comp_name, seq_no)
            
            # Process each previous operation
            for prev_op in prev_operations:
                # Add the operation name to our result list
                all_prev_operations.append(prev_op.operation)
                
                # Recursively get previous operations for this operation
                _collect_previous_recursive(prev_op.operation, prev_op.component, prev_op.sequence_no)
        
        # Start the recursive collection from the given operation
        _collect_previous_recursive(current_operation, component, sequence_no)
        
        return all_prev_operations
    
    def get_component_operations(self, component: str) -> List[OperationNode]:
        """Get all operations for a specific component"""
        if not self.is_valid():
            return []
        
        return self._component_operations.get(component, [])
    
    def get_skipped_operations(self, component: str, last_operation: str, 
                              current_operation: str) -> List[OperationNode]:
        """Get operations that were skipped between last and current operation"""
        if not self.is_valid():
            return []
        
        # Find nodes for last and current operations
        last_nodes = [n for n in self._nodes.values() 
                     if n.operation == last_operation and n.component == component]
        current_nodes = [n for n in self._nodes.values()
                        if n.operation == current_operation and n.component == component]
        
        if not last_nodes or not current_nodes:
            return []
        
        # Find path and identify skipped operations
        skipped = []
        for last_node in last_nodes:
            for current_node in current_nodes:
                path = self._find_shortest_path(last_node, current_node)
                if path and len(path) > 2:  # More than direct connection
                    skipped.extend(path[1:-1])  # Exclude start and end
        
        return list(set(skipped))  # Remove duplicates
    
    def is_valid_transition(self, component: str, from_operation: str, 
                           to_operation: str) -> bool:
        """Check if transition from one operation to another is valid"""
        if not self.is_valid():
            return False
            
        next_ops = self.get_next_operations(from_operation, component)
        return any(op.operation == to_operation for op in next_ops)
    
    def get_starting_operations(self, component: str) -> List[OperationNode]:
        """Get operations that can be starting points for a component"""
        if not self.is_valid():
            return []
        
        # Use cache if available
        if component in self._starting_operations_cache:
            return self._starting_operations_cache[component]
        
        component_ops = self._component_operations.get(component, [])
        starting_ops = [op for op in component_ops if not op.previous_operations]
        
        self._starting_operations_cache[component] = starting_ops
        return starting_ops
    
    def get_final_operations(self, component: str) -> List[OperationNode]:
        """Get final operations for a component"""
        if not self.is_valid():
            return []
        
        # Use cache if available
        if component in self._final_operations_cache:
            return self._final_operations_cache[component]
        
        component_ops = self._component_operations.get(component, [])
        final_ops = [op for op in component_ops if not op.next_operations]
        
        self._final_operations_cache[component] = final_ops
        return final_ops
    
    def is_final_operation(self, current_operation: str, component: str) -> bool:
        
        if self.get_next_operation(current_operation=current_operation, component=component) == None:
            return True
        
        return False
    
    def get_final_production_operation(self):
        if not self._components:
            return None

        only_component = next(iter(self._components))
        final_operations = self.get_final_operations(only_component)

        if not final_operations:
            return None

        final_operation = final_operations[0]
        if final_operation.operation_type == OperationType.UNLINK:
            if final_operation.previous_operations:
                return final_operation.previous_operations[0].operation
            else:
                return final_operation.operation
        return final_operation.operation

    
    def get_operation_flow(self, component: str) -> List[List[OperationNode]]:
        """Get all possible operation flows for a component"""
        if not self.is_valid():
            return []
        
        # Use cache if available
        if component in self._flow_paths_cache:
            return self._flow_paths_cache[component]
        
        start_ops = self.get_starting_operations(component)
        final_ops = self.get_final_operations(component)
        
        all_paths = []
        for start_op in start_ops:
            for final_op in final_ops:
                path = self._find_shortest_path(start_op, final_op)
                if path:
                    all_paths.append(path)
        
        self._flow_paths_cache[component] = all_paths
        return all_paths
    
    def get_all_components(self) -> List[str]:
        """Get all components in the operation map"""
        return list(self._components)
    
    def get_operation_node(self, operation: str, component: str, 
                          sequence_no: int = 1) -> Optional[OperationNode]:
        """Get specific operation node"""
        if not self.is_valid():
            return None
            
        lookup_key = (operation, component, sequence_no)
        return self._operation_lookup.get(lookup_key)
    
    def get_operations_by_type(self, operation_type: OperationType) -> List[OperationNode]:
        """Get all operations of a specific type"""
        if not self.is_valid():
            return []
        
        return [node for node in self._nodes.values() 
                if node.operation_type == operation_type]
    
    def get_component_current_status(self, component: str, 
                                   last_completed_operation: str) -> Dict[str, Any]:
        """Get current status and next possible operations for a component"""
        if not self.is_valid():
            return {'error': 'Operation map not valid'}
        
        next_ops = self.get_next_operations(last_completed_operation, component)
        
        return {
            'component': component,
            'last_completed_operation': last_completed_operation,
            'next_operations': [op.operation for op in next_ops],
            'is_completed': len(next_ops) == 0,
            'possible_transitions': [(op.operation, op.sequence_no) for op in next_ops]
        }
    
    def export_structure(self) -> Dict[str, Any]:
        """Export operation map structure for serialization"""
        if not self.is_valid():
            return {}
        
        return {
            'tracking_order_number': self.tracking_order_number,
            'components': list(self._components),
            'nodes': [node.to_dict() for node in self._nodes.values()],
            'validation_result': {
                'is_valid': self.validation_result.is_valid,
                'errors': self.validation_result.errors,
                'warnings': self.validation_result.warnings
            } if self.validation_result else None
        }
    
    def get_operation_stats(self) -> Dict[str, Any]:
        """Get statistics about the operation map"""
        if not self.is_valid():
            return {}
        
        operation_types = defaultdict(int)
        for node in self._nodes.values():
            operation_types[node.operation_type.value] += 1
        
        return {
            'total_operations': len(self._nodes),
            'total_components': len(self._components),
            'operation_types': dict(operation_types),
            'components_list': list(self._components),
            'has_activation': any(node.operation_type == OperationType.ACTIVATION 
                                 for node in self._nodes.values()),
            'has_unlink_operations': any(node.operation_type == OperationType.UNLINK_LINK 
                                        for node in self._nodes.values())
        }


import threading
# Utility class for managing multiple OperationMapData instances
class OperationMapManager:
    """
    Manager class for handling multiple OperationMapData instances
    keyed by tracking order numbers
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock: # Ensure only one thread can create the instance
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                # Initialize attributes here if needed, or in __init__
                # cls._instance._settings = {} 
            return cls._instance

    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._operation_maps: Dict[str, OperationMapData] = {}
            print("OperationMapManager initialized.")
            self._initialized = True
    
    def _create_operation_map(self, tracking_order_number: str, 
                           operation_map_data: List[Dict]) -> ValidationResult:
        """Create and build operation map for a tracking order"""
        op_map = OperationMapData(tracking_order_number)
        result = op_map.build_from_operation_map(operation_map_data)
        
        if result.is_valid:
            self._operation_maps[tracking_order_number] = op_map
        
        return result
    
    def get_operation_map(self, tracking_order_number: str) -> Optional[OperationMapData]:
        """Get operation map for a tracking order"""
        map_from_cache = self._operation_maps.get(tracking_order_number)
        if map_from_cache:
            return map_from_cache
        
        operation_data = []
        import frappe
        tracking_order_doc = frappe.get_doc("Tracking Order", tracking_order_number)
        for row in tracking_order_doc.operation_map:
            operation = row.operation
            component = row.component
            next_operation = row.next_operation
            seq_no = row.sequence_no
            configs = row.configs
            operation_data.append({
                'operation': operation,
                'component': component,
                'next_operation': next_operation,
                'sequence_no': seq_no or 1,
                'configs': configs or {}
            })
        result = self._create_operation_map(tracking_order_number, operation_data)
        if not result.is_valid:
            raise Exception("Invalid Operation map")
        
        return self._operation_maps.get(tracking_order_number)
        
        

    
    def remove_operation_map(self, tracking_order_number: str) -> bool:
        """Remove operation map for a tracking order"""
        if tracking_order_number in self._operation_maps:
            del self._operation_maps[tracking_order_number]
            return True
        return False
    
    def get_all_tracking_orders(self) -> List[str]:
        """Get all tracking order numbers with operation maps"""
        return list(self._operation_maps.keys())
    
    def clear_all(self):
        """Clear all operation maps"""
        self._operation_maps.clear()


# Example usage
if __name__ == "__main__":
    # Sample operation map data for tracking order
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
    
    # Create operation map for tracking order
    tracking_order = "TRK-ORD-2025-001"
    op_map_data = OperationMapData(tracking_order)
    
    # Build operation map
    result = op_map_data.build_from_operation_map(operation_data)
    print(f"Validation Result: {result.is_valid}")
    
    if result.is_valid:
        # Test public API methods
        print(f"Components: {op_map_data.get_all_components()}")
        
        # Get next operations
        next_ops = op_map_data.get_next_operations('Fabric Cutting', 'Body')
        print(f"Next operations after Fabric Cutting: {[op.operation for op in next_ops]}")
        
        # Get component status
        status = op_map_data.get_component_current_status('Body', 'Sewing')
        print(f"Component status: {status}")
        
        # Get operation stats
        stats = op_map_data.get_operation_stats()
        print(f"Operation stats: {stats}")

