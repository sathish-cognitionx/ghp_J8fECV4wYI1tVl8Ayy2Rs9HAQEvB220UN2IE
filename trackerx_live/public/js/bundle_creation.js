
frappe.ui.form.on('Bundle Creation', {
    before_cancel: function(frm) {
        // Check if we need confirmation for cancellation
        frappe.call({
            method: 'trackerx_live.hook.bundle_configuration.check_tracking_order_status',
            args: {
                bundle_creation_name: frm.doc.name
            },
            callback: function(r) {
                if (r.message && r.message.needs_confirmation) {
                    frappe.confirm(
                        r.message.confirmation_message,
                        function() {
                            // User confirmed - proceed with cancellation
                            frappe.call({
                                method: 'frappe.client.cancel',
                                args: {
                                    doctype: 'Bundle Creation',
                                    name: frm.doc.name
                                },
                                callback: function() {
                                    frm.reload_doc();
                                }
                            });
                        },
                        function() {
                            // User cancelled - do nothing
                            frappe.msgprint(__('Cancellation aborted'));
                        }
                    );
                    return false; // Prevent default cancellation
                }
            }
        });
    }
});