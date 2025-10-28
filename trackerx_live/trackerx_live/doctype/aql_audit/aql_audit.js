// Copyright (c) 2025, CognitionX and contributors
// For license information, please see license.txt

frappe.ui.form.on("AQL Audit", {
    refresh(frm) {
        frm.add_custom_button("Get Work Order", function() {
            let d = new frappe.ui.Dialog({
                title: 'Select Work Order',
                fields: [
                    {
                        label: 'Work Order',
                        fieldname: 'work_order',
                        fieldtype: 'Link',
                        options: 'Work Order',
                        reqd: 1
                    }
                ],
                primary_action_label: 'Create AQL Audit',
                primary_action(values) {
                    if (!values.work_order) {
                        frappe.msgprint("Please select a Work Order.");
                        return;
                    }

                    frappe.call({
                        method: "frappe.client.insert",
                        args: {
                            doc: {
                                doctype: "AQL Audit",
                                work_order: values.work_order
                            }
                        },
                        callback: function(r) {
                            if (!r.exc) {
                                frappe.msgprint({
                                    title: "Success",
                                    message: `New AQL Audit created: <b>${r.message.name}</b>`,
                                    indicator: "green"
                                });
                                frappe.set_route("Form", "AQL Audit", r.message.name);
                            }
                        }
                    });

                    d.hide();
                }
            });

            d.show();
        });
    },
});

