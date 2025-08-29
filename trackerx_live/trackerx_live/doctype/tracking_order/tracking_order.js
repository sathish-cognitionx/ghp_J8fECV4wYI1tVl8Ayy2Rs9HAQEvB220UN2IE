// Copyright (c) 2025, CognitionX and contributors
// For license information, please see license.txt
// This script runs on the client-side for the Tracking Order DocType.
frappe.ui.form.on('Tracking Order', {
    // This function is triggered when the form is refreshed or loaded.
    refresh: function(frm) {
        console.log("Tracking Order form refreshed."); // Debugging log
        // We no longer need to attach a handler here for bundle_configurations_add
        // as we'll use the child DocType's after_add event.
        set_reference_order_number_placeholder(frm);
    },
    reference_order_type: function(frm) {
        console.log("Reference Order Type changed.");
        set_reference_order_number_placeholder(frm);
    },
    // onload: function(frm) {
    //     frm.fields_dict['tracking_components'].grid.editable_fields = [
    //         'component_name',
    //         'parent_component',
    //         'is_main'
    //     ];
    // }
});


 // Event handler for when 'reference_order_type' field changes
    



function set_reference_order_number_placeholder(frm) {
    const referenceOrderType = frm.doc.reference_order_type;
    const referenceOrderNumberField = frm.get_field('reference_order_number');

    let placeholderText = "Enter Reference Order Number"; // Default

    if (referenceOrderType) {
        switch (referenceOrderType) {
            case "Sales Order":
                placeholderText = "Enter Sales Order Number (SO-XXXXX)";
                break;
            case "Work Order":
                placeholderText = "Enter Work Order Number (WO-XXXXX)";
                break;
            case "Cut Order":
                placeholderText = "Enter Cut Order Number (CO-XXXXX)";
                break;
            default:
                placeholderText = "Enter Reference Order Number";
        }
    }

    // Set the placeholder property
    // Directly target the input element and set its placeholder attribute
    if (referenceOrderNumberField && referenceOrderNumberField.$input) {
        referenceOrderNumberField.$input.attr('placeholder', placeholderText);
        console.log(`Placeholder set to: "${placeholderText}" via direct DOM manipulation.`);
    } else {
        console.warn("Reference Order Number field or its input element not found.");
    }
}




// Handle item location changes
frappe.ui.form.on('Tracking Component', {
    component_name: function(frm, cdt, cdn) {
        
        set_parent_component_options(frm, cdt, cdn);
    },
    
});

// A helper function to fetch the component names and set the options.
function set_parent_component_options(frm) {
    // Collect all the component names from the "custom_fg_components" child table.
    let component_names = frm.doc.tracking_components.filter(row => row.component_name).map(row => row.component_name)

    frm.doc.tracking_components.forEach(function(row, index) {
            let field = frm.fields_dict.tracking_components.grid.grid_rows[index].docfields.find(f => f.fieldname === 'parent_component');
            if (field) {
                field.options = [''].concat(component_names);
            }
        });

     frm.doc.operation_map.forEach(function(row, index) {
            let field = frm.fields_dict.operation_map.grid.grid_rows[index].docfields.find(f => f.fieldname === 'component');
            if (field) {
                field.options = component_names;
            }
        });
    
   
    frm.refresh_fields('operation_map');
}