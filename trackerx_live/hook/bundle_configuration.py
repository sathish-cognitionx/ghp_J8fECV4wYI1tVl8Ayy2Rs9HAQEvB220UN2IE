# -*- coding: utf-8 -*-
# Copyright (c) 2025, Your Company
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt

def cuttingx_bundle_configuration_on_submit(doc, method=None):
    create_tracking_order_from_bundle_creation(doc, method=None)

def cuttingx_bundle_configuration_before_cancel(doc, method=None):
    check_tracking_order_status_before_cancel(doc, method)
    pass
    

def cuttingx_bundle_configuration_before_on_cancel(doc, method=None):
    cancel_tracking_order(doc, method)

def cuttingx_bundle_configuration_before_delete(doc, method=None):
    delete_tracking_order(doc,method)

def create_tracking_order_from_bundle_creation(doc, method=None):
    """
    Auto-create Tracking Order when Bundle Creation is submitted
    This function should be called via a hook in hooks.py
    """
    try:
        # Create new Tracking Order document
        tracking_order = frappe.new_doc("Tracking Order")
        
        # Set basic fields
        tracking_order.reference_order_type = "Cut Order"  # Based on Bundle Creation coming from Cut Docket
        tracking_order.reference_order_number = doc.name  # Bundle Creation ID
        tracking_order.item = doc.fg_item
        tracking_order.production_type = "Bundle"  # Since this is from Bundle Creation
        tracking_order.order_status = "Created"
        tracking_order.activation_status = "Ready"
        current_company = frappe.defaults.get_user_default("company")
        tracking_order.company = current_company


        
        # Calculate total quantity from Bundle Creation Items
        total_quantity = 0
        for item in doc.table_bundle_creation_item:
            if item.unitsbundle and item.no_of_bundles:
                total_quantity += item.no_of_bundles * item.unitsbundle
        
        tracking_order.quantity = total_quantity
        tracking_order.pending_production_quantity = total_quantity

        main_component = None
        fg_item = frappe.get_doc("Item", tracking_order.item )
        if fg_item.custom_fg_components:
            for fg_component in fg_item.custom_fg_components:
                if fg_component.is_main_component:
                    main_component = fg_component.component_name

        
        # Create Bundle Configurations from Bundle Creation Items
        for bundle_item in doc.table_bundle_creation_item:
            if bundle_item.no_of_bundles and bundle_item.unitsbundle:
                # Use proper child table creation method
                bundle_config_row = frappe.new_doc("Tracking Order Bundle Configuration")
                bundle_config_row.bc_name = f"BC-{bundle_item.size}-{bundle_item.shade}"
                bundle_config_row.size = bundle_item.size
                bundle_config_row.bundle_quantity = bundle_item.unitsbundle
                bundle_config_row.number_of_bundles = bundle_item.no_of_bundles
                bundle_config_row.component = "__Default__"
                bundle_config_row.production_type = "Bundle"
                bundle_config_row.parent = tracking_order.name
                bundle_config_row.parenttype = "Tracking Order"
                bundle_config_row.parentfield = "bundle_configurations"
                bundle_config_row.source = "Configuration"
                
                # Append to the parent document
                tracking_order.bundle_configurations.append(bundle_config_row)
        
        # Create Tracking Components based on Bundle Details
        components_added = set()  # To avoid duplicate components
        
        for bundle_detail in doc.table_bundle_details:
            component_key = bundle_detail.component if bundle_detail.component else "__Default__"
            
            if component_key not in components_added:
                component_row = frappe.new_doc("Tracking Component")
                component_row.component_name = component_key
                component_row.is_main = 1 if component_key == main_component else 0
                component_row.parent = tracking_order.name
                component_row.parenttype = "Tracking Order"
                component_row.parentfield = "tracking_components"
                
                tracking_order.tracking_components.append(component_row)
                components_added.add(component_key)
        
        # If no components found, add default
        if not components_added:
            component_row = frappe.new_doc("Tracking Component")
            component_row.component_name = "__Default__"
            component_row.is_main = 1
            component_row.parent = tracking_order.name
            component_row.parenttype = "Tracking Order"
            component_row.parentfield = "tracking_components"
            
            tracking_order.tracking_components.append(component_row)
        
        from trackerx_live.trackerx_live.utils.process_map_to_operation_map_util import generate_operation_map_from_item
        # Create basic operation map
        result = generate_operation_map_from_item(doc.fg_item)
        for entry in result["operation_map_entries"]:
            operation_row = frappe.new_doc("Operation Map")
            operation_row.operation = entry["operation"]
            operation_row.component = entry["component"]
            operation_row.next_operation = entry["next_operation"]
            operation_row.sequence_no = entry["sequence_no"]
            operation_row.configs = entry["configs"]
            operation_row.parent = tracking_order.name
            operation_row.parenttype = "Tracking Order"
            operation_row.parentfield = "operation_map"
        
            tracking_order.operation_map.append(operation_row)

        
        # Insert the document
        tracking_order.insert(ignore_permissions=True)
        
        # Submit the Tracking Order
        tracking_order.submit()

        try:
            from trackerx_live.trackerx_live.utils.operation_map_util import OperationMapManager
            operation_map_manager = OperationMapManager()
            operation_map = operation_map_manager.get_operation_map(tracking_order.name)
            validation_result = operation_map.get_validation_result
        except Exception as e:
            if "Invalid Operation map" == str(e):
                frappe.throw(f"Invalid process map {result.get('map_name','')} for Item {doc.fg_item}")
    

        is_auto_activation_required = doc.tracking_tech in ('Barcode', 'QR Code')

        if is_auto_activation_required:
            create_production_items(doc, tracking_order)
        
        # Add a comment or log
        frappe.msgprint(f"Tracking Order {tracking_order.name} created successfully from Bundle Creation {doc.name}")
        
        # Log the creation
        frappe.logger().info(f"Auto-created Tracking Order {tracking_order.name} from Bundle Creation {doc.name}")
        
    except Exception as e:
        
        frappe.log_error(f"Error creating Tracking Order from Bundle Creation {doc.name}:")
        frappe.log_error(f"{str(e)}")
        frappe.throw(f"Failed to submit Bundle Configuration: {str(e)}")


def create_production_items(doc, tracking_order):
    try:
        # Create bundle configurations for each component
        component_bc_dict = {}
        
        for bundle_configuration in tracking_order.bundle_configurations:
            for component in tracking_order.tracking_components:
                key = f'{bundle_configuration.size}---{component.component_name}'
                
                # Check if this combination already exists
                if key not in component_bc_dict:
                    component_bundle_configuration = frappe.new_doc("Tracking Order Bundle Configuration")
                    component_bundle_configuration.bc_name = bundle_configuration.bc_name
                    component_bundle_configuration.size = bundle_configuration.size
                    component_bundle_configuration.bundle_quantity = bundle_configuration.bundle_quantity
                    component_bundle_configuration.number_of_bundles = bundle_configuration.number_of_bundles
                    component_bundle_configuration.production_type = bundle_configuration.production_type
                    component_bundle_configuration.component = component.component_name  # Fixed this
                    component_bundle_configuration.parent_component = bundle_configuration.name
                    component_bundle_configuration.parent = tracking_order.name
                    component_bundle_configuration.parenttype = "Tracking Order"
                    component_bundle_configuration.parentfield = "component_bundle_configuration"
                    component_bundle_configuration.source = "Activation"

                    component_bundle_configuration.insert(ignore_permissions=True)
                    component_bc_dict[key] = component_bundle_configuration

        component_by_name = {}

        for comp in tracking_order.tracking_components:
            component_by_name[comp.component_name] = comp.name

        for bundle in doc.table_bundle_details:
            # Create tracking tag
            tag = frappe.new_doc("Tracking Tag")
            tag.tag_number = bundle.bundle_id
            tag.tag_type = doc.tracking_tech
            tag.status = 'Active'
            tag.activation_time = frappe.utils.now()
            tag.last_used_on = frappe.utils.now()
            tag.remarks = None
            tag.activation_source = 'Cut Bundle'
            tag.insert(ignore_permissions=True)

            # Build the key for component lookup
            key = f'{bundle.size}---{bundle.component}'
            
            # Check if the key exists in our dictionary
            if key not in component_bc_dict:
                frappe.log_error(f"Component bundle configuration not found for key: {key}")
                continue  # Skip this bundle or handle the error as appropriate
            
            # Create production item
            production_item = frappe.new_doc("Production Item")
            production_item.production_item_number = bundle.bundle_id
            production_item.tracking_order = tracking_order.name
            production_item.bundle_configuration = component_bc_dict[key].name  # Use .name
            production_item.tracking_tag = tag.name
            production_item.component = component_by_name[bundle.component]
            production_item.device_id = 'None'
            production_item.size = bundle.size
            production_item.quantity = bundle.unitsbundle
            production_item.status = 'Activated'
            production_item.current_operation = 'Activation'
            production_item.next_operation = 'Activation'
            production_item.current_workstation = 'Activation WS'
            production_item.next_workstation = 'Activation WS'

            production_item.insert(ignore_permissions=True)

            # Create production item tag map
            production_item_tag_map = frappe.new_doc("Production Item Tag Map")
            production_item_tag_map.production_item = production_item.name
            production_item_tag_map.tracking_tag = tag.name
            production_item_tag_map.linked_on = frappe.utils.now()
            production_item_tag_map.is_active = True
            production_item_tag_map.activated_source = 'Cut Bundle'
            production_item_tag_map.insert(ignore_permissions=True)

            item_scan_log = frappe.new_doc("Item Scan Log")
            item_scan_log.production_item = production_item.name
            item_scan_log.workstation = None
            item_scan_log.operation = None
            item_scan_log.physical_cell = None
            item_scan_log.scanned_by = frappe.session.user
            item_scan_log.scan_time = frappe.utils.now_datetime()
            item_scan_log.logged_time = frappe.utils.now_datetime()
            item_scan_log.status = 'Activated'
            item_scan_log.log_status = 'Completed'
            item_scan_log.log_type = 'Auto'
            item_scan_log.production_item_type = 'Bundle'
            item_scan_log.dut = None
            item_scan_log.insert(ignore_permissions=True)

            production_item.last_scan_log(item_scan_log.name)
            production_item.save()
     

        tracking_order.activation_status = "Completed"
        tracking_order.save()
            
    except Exception as e:
        frappe.log_error(f"Error in create_production_items: {str(e)}")
        frappe.throw(f"Failed to create production items: {str(e)}")

        


def check_tracking_order_status_before_cancel(doc, method):
    """
    Hook that runs before canceling Bundle Creation
    Checks if related Tracking Order is in Production or Completed status
    """
    # Find related tracking order
    tracking_orders = frappe.get_all("Tracking Order", 
        filters={"reference_order_number": doc.name},
        fields=["name", "order_status", "produced_quantity", "quantity"]
    )
    
    if not tracking_orders:
        return
    
    tracking_order = tracking_orders[0]
    
    # Check if tracking order status requires confirmation
    if tracking_order.order_status in ["In Production", "Completed"]:
        # Get full tracking order document to get more details
        tracking_doc = frappe.get_doc("Tracking Order", tracking_order.name)
        
        produced_qty = flt(tracking_doc.get("produced_quantity", 0))
        total_qty = flt(tracking_doc.get("quantity", 0))
        
        # Create confirmation message
        if tracking_order.status == "Completed":
            message = f"This Bundle Creation has a completed Tracking Order ({tracking_order.name}). All {produced_qty or total_qty} units have been produced."
        else:
            message = f"This Bundle Creation has a Tracking Order ({tracking_order.name}) that is currently 'In Production'. {produced_qty} out of {total_qty} units have been produced."
        
        # Show confirmation dialog - this needs to be handled on the client side
        # We'll throw an exception with a specific message that can be caught by client-side JS
        frappe.throw(
            msg=message,
            title="Cancellation Not Allowed",
            exc=frappe.ValidationError
        )



def cancel_tracking_order(doc, method):
    """
    Hook that runs after canceling Bundle Creation
    Cancels the related Tracking Order
    """
    # Find and cancel related tracking order
    tracking_orders = frappe.get_all("Tracking Order", 
        filters={"reference_order_number": doc.name, "docstatus": 1},
        fields=["name"]
    )
    
    for tracking_order in tracking_orders:
        tracking_doc = frappe.get_doc("Tracking Order", tracking_order.name)
        if tracking_doc.docstatus == 1:  # Only cancel if submitted
            tracking_doc.cancel()
            frappe.msgprint(f"Related Tracking Order {tracking_order.name} has been cancelled")

def delete_tracking_order(doc, method):
    """
    Hook that runs before deleting Bundle Creation
    Updates related Tracking Order status to 'Cancelled'
    """
    # Find related tracking orders
    tracking_orders = frappe.get_all("Tracking Order", 
        filters={"reference_order_number": doc.name},
        fields=["name", "docstatus"]
    )
    
    for tracking_order in tracking_orders:
        tracking_doc = frappe.get_doc("Tracking Order", tracking_order.name)
        
        # If tracking order is in draft, we can delete it
        if tracking_doc.docstatus == 0:
            frappe.delete_doc("Tracking Order", tracking_order.name)
            frappe.msgprint(f"Related draft Tracking Order {tracking_order.name} has been deleted")
        
        # If tracking order is submitted, we need to cancel it first, then we can set status
        elif tracking_doc.docstatus == 1:
            # Cancel if not already cancelled
            if tracking_doc.docstatus == 1:
                tracking_doc.cancel()
            
            # Update status to cancelled (this works even on cancelled docs)
            frappe.db.set_value("Tracking Order", tracking_order.name, "status", "Cancelled")
            frappe.msgprint(f"Related Tracking Order {tracking_order.name} status has been set to Cancelled")

# Alternative approach for client-side confirmation
# Create a client script for Bundle Creation doctype

# bundle_creation.js - Client Script for Bundle Creation doctype



# Additional server-side method for checking status
@frappe.whitelist()
def check_tracking_order_status(bundle_creation_name):
    """
    Method to check if confirmation is needed before cancelling
    """
    tracking_orders = frappe.get_all("Tracking Order", 
        filters={"reference_order_number": bundle_creation_name},
        fields=["name", "order_status", "produced_quantity", "quantity"]
    )
    
    if not tracking_orders:
        return {"needs_confirmation": False}
    
    tracking_order = tracking_orders[0]
    
    if tracking_order.order_status in ["In Production", "Completed"]:
        tracking_doc = frappe.get_doc("Tracking Order", tracking_order.name)
        produced_qty = flt(tracking_doc.get("produced_quantity", 0))
        total_qty = flt(tracking_doc.get("quantity", 0))
        
        if tracking_order.order_status == "Completed":
            message = f"This Bundle Creation has a completed Tracking Order ({tracking_order.name}). All {produced_qty or total_qty} units have been produced. Are you sure you want to cancel?"
        else:
            message = f"This Bundle Creation has a Tracking Order ({tracking_order.name}) that is currently 'In Production'. {produced_qty} out of {total_qty} units have been produced. Are you sure you want to cancel?"
        
        return {
            "needs_confirmation": True,
            "confirmation_message": message
        }
    
    return {"needs_confirmation": False}
    

def create_tracking_order_from_bundle_creation_v2(doc, method=None):
    """
    Alternative approach using dictionary method but with proper initialization
    """
    try:
        # Create new Tracking Order document
        tracking_order = frappe.new_doc("Tracking Order")
        
        # Set basic fields
        tracking_order.reference_order_type = "Cut Order"
        tracking_order.reference_order_number = doc.name
        tracking_order.item = doc.fg_item
        tracking_order.production_type = "Bundle"
        
        # Calculate total quantity
        total_quantity = 0
        for item in doc.table_bundle_creation_item:
            if item.unitsbundle and item.no_of_bundles:
                total_quantity += item.no_of_bundles * item.unitsbundle
        
        tracking_order.quantity = total_quantity
        
        # Initialize child tables as empty lists first
        tracking_order.bundle_configurations = []
        tracking_order.tracking_components = []
        tracking_order.operation_map = []
        
        # Save the document first to get a name
        tracking_order.save(ignore_permissions=True)
        
        # Now add child table entries using append method
        for bundle_item in doc.table_bundle_creation_item:
            if bundle_item.no_of_bundles and bundle_item.unitsbundle:
                bundle_config = tracking_order.append("bundle_configurations")
                bundle_config.bc_name = f"BC-{bundle_item.size}-{bundle_item.shade}"
                bundle_config.size = bundle_item.size
                bundle_config.bundle_quantity = bundle_item.unitsbundle
                bundle_config.number_of_bundles = bundle_item.no_of_bundles
                bundle_config.component = "__Default__"
                bundle_config.production_type = "Bundle"
        
        # Add components
        components_added = set()
        for bundle_detail in doc.table_bundle_details:
            component_key = bundle_detail.component if bundle_detail.component else "__Default__"
            
            if component_key not in components_added:
                component = tracking_order.append("tracking_components")
                component.component_name = component_key
                component.is_main = 1 if component_key == "__Default__" else 0
                components_added.add(component_key)
        
        # If no components, add default
        if not components_added:
            component = tracking_order.append("tracking_components")
            component.component_name = "__Default__"
            component.is_main = 1
        
        # Add operation map
        operation = tracking_order.append("operation_map")
        operation.operation = "Sewing QC"
        operation.component = "__Default__"
        operation.next_operation = "Sewing QC"
        operation.sequence_no = 1
        
        # Save again with child tables
        tracking_order.save(ignore_permissions=True)
        
        # Submit the document
        tracking_order.submit()
        
        frappe.msgprint(f"Tracking Order {tracking_order.name} created successfully from Bundle Creation {doc.name}")
        frappe.logger().info(f"Auto-created Tracking Order {tracking_order.name} from Bundle Creation {doc.name}")
        
    except Exception as e:
        frappe.log_error(f"Error creating Tracking Order from Bundle Creation {doc.name}: {str(e)}")
        frappe.throw(f"Failed to create Tracking Order: {str(e)}")


# Alternative: If you want to add this as a custom method to Bundle Creation doctype
class BundleCreation(Document):
    def on_submit(self):
        """Override the on_submit method of Bundle Creation"""
        # Call the function to create Tracking Order
        create_tracking_order_from_bundle_creation_v2(self)


def validate_bundle_creation_data(doc):
    """
    Validation function to ensure Bundle Creation has required data
    """
    if not doc.fg_item:
        frappe.throw("FG Item is required to create Tracking Order")
    
    if not doc.table_bundle_creation_item:
        frappe.throw("Bundle Configuration items are required")
    
    # Validate that each bundle item has required fields
    for item in doc.table_bundle_creation_item:
        if not item.size:
            frappe.throw("Size is required for all bundle configuration items")
        if not item.unitsbundle or item.unitsbundle <= 0:
            frappe.throw("Units/Bundle must be greater than 0")
        if not item.no_of_bundles or item.no_of_bundles <= 0:
            frappe.throw("Number of Bundles must be greater than 0")


def create_tracking_order_with_validation(doc, method=None):
    """
    Enhanced version with validation and error handling
    """
    # Validate data first
    validate_bundle_creation_data(doc)
    
    try:
        # Check if Tracking Order already exists for this Bundle Creation
        existing_tracking_order = frappe.db.exists("Tracking Order", {
            "reference_order_number": doc.name,
            "reference_order_type": "Cut Order"
        })
        
        if existing_tracking_order:
            frappe.msgprint(f"Tracking Order already exists: {existing_tracking_order}")
            return
        
        # Use the v2 method which saves first then adds child tables
        create_tracking_order_from_bundle_creation_v2(doc, method)
        
    except Exception as e:
        frappe.log_error(f"Error in create_tracking_order_with_validation: {str(e)}")
        frappe.throw(f"Failed to create Tracking Order: {str(e)}")


# Hook configuration for hooks.py
"""
Add this to your app's hooks.py file:

doc_events = {
    "Bundle Creation": {
        "on_submit": "your_app.your_module.bundle_creation.create_tracking_order_with_validation"
    }
}

Replace 'your_app.your_module.bundle_creation' with the actual path to this file.
"""