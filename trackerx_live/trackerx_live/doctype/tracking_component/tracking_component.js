// Copyright (c) 2025, CognitionX and contributors
// For license information, please see license.txt

frappe.ui.form.on('Tracking Component', {
    component_name: function(frm, cdt, cdn) {
        let current_row = locals[cdt][cdn];

        // Get all component names except the current row
        let options = [];

        if (frm && frm.doc && frm.doc.tracking_components) {
            frm.doc.tracking_components.forEach(row => {
                if (row.name !== current_row.name && row.component_name) {
                    options.push(row.component_name);
                }
            });

            // Set options for parent_component for this field only (not globally)
            frappe.meta.get_docfield('Tracking Component', 'parent_component', frm.doc.name).options = options.join('\n');

            // Re-render field dropdown in grid
            frm.fields_dict["tracking_components"].grid.update_docfield_property(
                "parent_component", "options", options.join('\n')
            );

            frm.refresh_field("tracking_components");
        }
        console.log("added new component");
    }
});
