frappe.pages['aql'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'AQL Audit',
		single_column: true
	});
}
