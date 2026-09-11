frappe.provide("frappe.query_reports");

const TYPE_OPTIONS = [
    "",
    "Direct Cost",
    "Indirect Cost",
    "Direct Income",
    "Indirect Income",
    "Distribution costs",
    "Administrative expenses",
    "Other expenses",
    "Purchases"
];

function inject_type_filter(report_def) {
    if (!report_def || !report_def.filters) return report_def;
    
    let existing_idx = report_def.filters.findIndex(f => f.fieldname === "custom_type");
    if (existing_idx !== -1) {
        report_def.filters.splice(existing_idx, 1);
    }
    
    // Insert filter exactly after "project" filter
    let proj_idx = report_def.filters.findIndex(f => f.fieldname === "project");
    let insert_idx = proj_idx !== -1 ? proj_idx + 1 : 10;
    
    report_def.filters.splice(insert_idx, 0, {
        fieldname: "custom_type",
        label: __("Type"),
        fieldtype: "Select",
        options: TYPE_OPTIONS,
        width: "140px"
    });
    
    return report_def;
}

if (frappe.query_reports["General Ledger"]) {
    inject_type_filter(frappe.query_reports["General Ledger"]);
}

let _gl_report_def = frappe.query_reports["General Ledger"];
try {
    Object.defineProperty(frappe.query_reports, "General Ledger", {
        get: function() {
            return _gl_report_def;
        },
        set: function(val) {
            _gl_report_def = inject_type_filter(val);
        },
        configurable: true,
        enumerable: true
    });
} catch (e) {
    console.warn("Could not define property on frappe.query_reports['General Ledger']", e);
}

function ensure_filter_on_page() {
    let route = frappe.get_route ? frappe.get_route() : [];
    if (route && route[0] === "query-report" && route[1] === "General Ledger") {
        if (frappe.query_report && frappe.query_report.filters) {
            let filter = frappe.query_report.get_filter("custom_type");
            if (!filter && frappe.query_report.page) {
                let filter_def = {
                    fieldname: "custom_type",
                    label: __("Type"),
                    fieldtype: "Select",
                    options: TYPE_OPTIONS,
                    width: "140px"
                };
                
                let proj_idx = frappe.query_report.filters.findIndex(f => f.df && f.df.fieldname === "project");
                let insert_idx = proj_idx !== -1 ? proj_idx + 1 : frappe.query_report.filters.length;
                frappe.query_report.filters.splice(insert_idx, 0, filter_def);
                
                if (typeof frappe.query_report.make_filter === "function") {
                    frappe.query_report.make_filter(filter_def);
                }
            }
        }
    }
}

$(document).on("app_ready page-change", function() {
    ensure_filter_on_page();
});

if (frappe.router && frappe.router.on) {
    frappe.router.on("change", function() {
        setTimeout(ensure_filter_on_page, 200);
    });
}
