frappe.provide("frappe.query_reports");

function add_type_filter_to_general_ledger() {
    if (!frappe.query_reports || !frappe.query_reports["General Ledger"]) {
        return;
    }

    let gl_report = frappe.query_reports["General Ledger"];
    if (!gl_report.filters) return;

    let has_type_filter = gl_report.filters.some(f => f.fieldname === "custom_type");
    if (!has_type_filter) {
        gl_report.filters.push({
            fieldname: "custom_type",
            label: __("Type"),
            fieldtype: "Select",
            options: [
                "",
                "Direct Cost",
                "Indirect Cost",
                "Direct Income",
                "Indirect Income",
                "Distribution costs",
                "Administrative expenses",
                "Other expenses",
                "Purchases"
            ]
        });
    }
}

$(document).on("app_ready page-change", function() {
    add_type_filter_to_general_ledger();
});

if (frappe.router) {
    frappe.router.on("change", function() {
        if (frappe.get_route()[1] === "General Ledger") {
            add_type_filter_to_general_ledger();
        }
    });
}

add_type_filter_to_general_ledger();
