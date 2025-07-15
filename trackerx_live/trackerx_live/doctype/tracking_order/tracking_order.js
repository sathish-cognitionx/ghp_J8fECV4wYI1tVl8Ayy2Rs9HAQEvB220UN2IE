// Copyright (c) 2025, CognitionX and contributors
// For license information, please see license.txt
// This script runs on the client-side for the Tracking Order DocType.
frappe.ui.form.on('Tracking Order', {
    // This function is triggered when the form is refreshed or loaded.
    refresh: function(frm) {
        console.log("Tracking Order form refreshed."); // Debugging log
        // We no longer need to attach a handler here for bundle_configurations_add
        // as we'll use the child DocType's after_add event.
    }
});
