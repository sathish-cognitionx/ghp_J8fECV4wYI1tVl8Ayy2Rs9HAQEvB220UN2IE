frappe.pages['aql-audit-page'].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
	  parent: wrapper,
	//   title: 'AQL Audit Dashboard',
	  single_column: true
	});
  
	// Inject HTML structure
	// $(frappe.render_template('aql_audit_dashboard', {})).appendTo(page.main);
  
	// OR if you’re not using Jinja templates, directly set HTML:
	page.main.html(`
	  <div class="aql-dashboard">
		<h2 style="margin-bottom: 8px;">AQL Audit Dashboard</h2>
  
		<div class="aql-header">
		  <div class="aql-search">
			<input id="searchBox" type="text" placeholder="Search Work Orders, Style, Vendor..." aria-label="Search Work Orders">
		  </div>
		  <div class="aql-actions">
			<button id="refreshBtn" class="btn-select" style="background:#0b5fff">Refresh</button>
		  </div>
		</div>
  
		<div class="list-header">
		  <div>Work Order</div>
		  <div>Style</div>
		  <div>Color</div>
		  <div class="center">Order Qty</div>
		  <div class="center">Received Qty</div>
		  <div>Vendor</div>
		  <div>Audit Date</div>
		  <div>Audit Result</div>
		  <div>Inspected By</div>
		  <div class="center">Action</div>
		</div>
  
		<div id="woList" class="wo-list" aria-live="polite"></div>
	  </div>
	`);
  
	// Load custom CSS
	const style = document.createElement('style');
	style.textContent = `
	.fail-row {
		background-color: #ffe5e5 !important;
		border-left: 4px solid #ff4d4d;
		}
		.fail-row:hover {
		background-color: #ffcccc !important;
		}

	  /* --- AQL Dashboard Styling --- */
	  .aql-dashboard {
		max-width: 1200px;
		margin: 0 auto 40px;
		padding: 16px;
		font-family: "Inter", "Helvetica Neue", Arial, sans-serif;
	  }
	  .aql-header { display: flex; gap: 12px; align-items: center; margin-bottom: 18px; }
	  .aql-search { flex: 1; min-width: 220px; display: flex; gap: 8px; }
	  .aql-search input { flex: 1; padding: 8px 12px; border: 1px solid #e0e6ef; border-radius: 6px; font-size: 14px; }
	  .aql-actions { display:flex; gap:8px; }
	  .list-header {
		display: grid; grid-template-columns: 2fr 1fr 1fr 100px 110px 1fr 150px 120px 140px 80px;
		gap: 12px; padding: 10px 12px; border-bottom: 1px solid #eef2fb; color: #505f79;
		font-size: 13px; font-weight: 600; background: #fafcff; align-items: center; border-radius: 6px 6px 0 0;
	  }
	  .wo-list { display: flex; flex-direction: column; gap: 6px; margin-top: 8px; }
	  .wo-row {
		display: grid; grid-template-columns: 2fr 1fr 1fr 100px 110px 1fr 150px 120px 140px 80px;
		gap: 12px; padding: 10px 12px; background: #fff; border: 1px solid #f0f3fb; border-radius: 6px;
		align-items: center; transition: transform .08s ease, box-shadow .08s ease; cursor: pointer;
	  }
	  .wo-row:hover { transform: translateY(-3px); box-shadow: 0 6px 18px rgba(30,50,90,0.06); }
	  .wo-link { color: #0b5fff; text-decoration: none; font-weight: 600; display: inline-block; }
	  .center { text-align: center; }
	  .btn-select { padding: 6px 10px; border-radius: 6px; border: none; background: #0b5fff; color: #fff; font-weight: 600; cursor: pointer; }
	  .btn-select[disabled] { background: #cbd7ff; cursor: default; opacity: 0.8; }
	  select.form-control {
		width: 100%; padding: 6px; border-radius: 6px; border: 1px solid #dce3f0; font-size: 13px; background: #fff;
	  }
	`;
	document.head.appendChild(style);
  
	// -------------------
	// JS Functionality
	// -------------------
  
	let usersList = [];
  
	function debounce(fn, wait = 250) {
	  let t;
	  return (...args) => {
		clearTimeout(t);
		t = setTimeout(() => fn(...args), wait);
	  };
	}
  
	function loadUsersList() {
	  return new Promise((resolve) => {
		frappe.call({
		  method: "frappe.client.get_list",
		  args: {
			doctype: "User",
			filters: { enabled: 1 },
			fields: ["name", "full_name"],
			limit_page_length: 1000
		  },
		  callback(r) {
			usersList = (r.message || []).map(u => ({
			  name: u.name,
			  full_name: u.full_name || u.name
			}));
			resolve(usersList);
		  }
		});
	  });
	}
  
	function renderRow(row) {
		const result = (row.audit_result || "").toLowerCase();
		let badgeClass = "badge-pending";
		if (result === "pass") badgeClass = "badge-pass";
		else if (result === "fail") badgeClass = "badge-fail";
	  
		const disabled = (row.audit_result === "Pass" || row.audit_result === "pass") ? "disabled" : "";
	  
		const auditOptions = `
		  <select id="auditResult-${row.work_order}" class="form-control">
			<option value="">Select Status</option>
			<option value="Pass" ${row.audit_result === "Pass" ? "selected" : ""}>Pass</option>
			<option value="Fail" ${row.audit_result === "Fail" ? "selected" : ""}>Fail</option>
		  </select>
		`;
	  
		const inspectedBySelect = `<select id="inspectedBy-${row.work_order}" class="form-control"><option value="">Select QC</option></select>`;
	  
		// ✅ Apply red background class if audit result = Fail
		const rowClass = result === "fail" ? "fail-row" : "";
	  
		return `
		  <div class="wo-row ${rowClass}" data-wo="${row.work_order}">
			<div><a class="wo-link" href="/app/work-order/${row.work_order}" target="_blank">${row.work_order}</a></div>
			<div>${row.style || "-"}</div>
			<div>${row.color || "-"}</div>
			<div class="center">${row.order_qty ?? "-"}</div>
			<div class="center">${row.received_qty ?? "-"}</div>
			<div>${row.vendor || "-"}</div>
			<div>${row.audit_date || "-"}</div>
			<div>${auditOptions}</div>
			<div>${inspectedBySelect}</div>
			<div class="center">
			  <button class="btn-select" ${disabled} onclick="createAQLAudit(event, '${row.work_order}')">Submit</button>
			</div>
		  </div>`;
	  }
	  
  
	function populateUserDropdowns(rows) {
		const currentUser = frappe.session.user; // get logged-in user
		rows.forEach(row => {
		  const select = document.getElementById(`inspectedBy-${row.work_order}`);
		  if (!select) return;
		  usersList.forEach(user => {
			const option = document.createElement("option");
			option.value = user.name;
			option.textContent = user.full_name;
			// Set default: logged-in user
			if (row.inspected_by) {
			  if (user.name === row.inspected_by) option.selected = true;
			} else {
			  if (user.name === currentUser) option.selected = true;
			}
			select.appendChild(option);
		  });
		});
	  }
	  
  
	async function loadWorkOrders(query = "") {
	  const listContainer = document.getElementById("woList");
	  listContainer.innerHTML = `<div style="padding:12px;color:#7d8797">Loading...</div>`;
  
	  if (!usersList.length) await loadUsersList();
  
	  frappe.call({
		method: "trackerx_live.trackerx_live.doctype.aql_audit.aql_audit.get_work_orders",
		args: { search: query },
		callback(r) {
		  const rows = r.message || [];
		  if (!rows.length) {
			listContainer.innerHTML = `<div style="padding:12px;color:#7d8797">No work orders found.</div>`;
			return;
		  }
		  listContainer.innerHTML = rows.map(renderRow).join("");
		  populateUserDropdowns(rows);
		},
		error: () => {
		  listContainer.innerHTML = `<div style="padding:12px;color:#b42b3a">Error loading work orders</div>`;
		}
	  });
	}
  
	window.createAQLAudit = function (ev, wo) {
		ev.stopPropagation();
	  
		// Get values from row
		const audit_result = document.getElementById(`auditResult-${wo}`).value;
		const inspected_by = document.getElementById(`inspectedBy-${wo}`).value;
	  
		// ✅ fetch visible row values from DOM directly
		const row = document.querySelector(`.wo-row[data-wo="${wo}"]`);
		if (!row) return;
	  
		const cells = row.querySelectorAll("div");
		const style = cells[1]?.innerText.trim() || "";
		const color = cells[2]?.innerText.trim() || "";
		const order_qty = cells[3]?.innerText.trim() || "";
		const audit_date = cells[3]?.innerText.trim() || "";
	  
		if (!audit_result) {
		  frappe.show_alert({ message: "Please select Audit Result", indicator: "orange" });
		  return;
		}
	  
		frappe.call({
		  method: "trackerx_live.trackerx_live.doctype.aql_audit.aql_audit.create_aql_audit",
		  args: {
			work_order: wo,
			audit_result,
			inspected_by,
			style,
			color,
			order_qty,
			audit_date,
		  },
		  callback(r) {
			if (r.message.status === "success") {
			  frappe.show_alert({ message: r.message.message, indicator: "green" });
			  loadWorkOrders();
			} else {
			  frappe.show_alert({ message: r.message.message, indicator: "red" });
			}
		  },
		});
	  };
	  
  
	// Bind search and refresh
	document.getElementById("searchBox").addEventListener("input", debounce((e) => {
	  loadWorkOrders(e.target.value.trim());
	}, 300));
	document.getElementById("refreshBtn").addEventListener("click", () => loadWorkOrders());
  
	// Initial load
	loadWorkOrders();
  };
  