frappe.provide("frappe.query_reports");

const TYPE_OPTIONS = [
    "",
    "Direct Cost",
    "Indirect Cost",
    "Distribution costs",
    "Administrative expenses",
    "Other expenses"
];

function patch_gl_filters(filters) {
    if (!filters || !Array.isArray(filters)) return;
    let existing_idx = filters.findIndex(f => (f.fieldname || (f.df && f.df.fieldname)) === "custom_type");
    if (existing_idx !== -1) {
        filters.splice(existing_idx, 1);
    }
    let proj_idx = filters.findIndex(f => (f.fieldname || (f.df && f.df.fieldname)) === "project");
    let insert_idx = proj_idx !== -1 ? proj_idx + 1 : filters.length;
    
    filters.splice(insert_idx, 0, {
        fieldname: "custom_type",
        label: __("Type"),
        fieldtype: "Select",
        options: TYPE_OPTIONS,
        width: "140px"
    });
}

// 1. Wrap QueryReport prototype setup_filters
if (frappe.views && frappe.views.QueryReport) {
    let orig_setup_filters = frappe.views.QueryReport.prototype.setup_filters;
    frappe.views.QueryReport.prototype.setup_filters = function() {
        if (this.report_name === "General Ledger" && this.report_settings && this.report_settings.filters) {
            patch_gl_filters(this.report_settings.filters);
        }
        return orig_setup_filters.apply(this, arguments);
    };
}

// 2. Intercept report definition
let _gl_settings = frappe.query_reports["General Ledger"];
try {
    Object.defineProperty(frappe.query_reports, "General Ledger", {
        get: function() {
            return _gl_settings;
        },
        set: function(val) {
            if (val && val.filters) {
                patch_gl_filters(val.filters);
            }
            _gl_settings = val;
        },
        configurable: true,
        enumerable: true
    });
} catch(e) {}

if (_gl_settings && _gl_settings.filters) {
    patch_gl_filters(_gl_settings.filters);
}

// 3. Fallback on page render / route change
function ensure_type_filter_rendered() {
    let route = frappe.get_route ? frappe.get_route() : [];
    if (route && route[0] === "query-report" && route[1] === "General Ledger") {
        if (frappe.query_report && frappe.query_report.page) {
            let filter = frappe.query_report.get_filter("custom_type");
            if (!filter && frappe.query_report.filters) {
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

$(document).on("page-change app_ready", function() {
    ensure_type_filter_rendered();
});

if (frappe.router && frappe.router.on) {
    frappe.router.on("change", function() {
        setTimeout(ensure_type_filter_rendered, 300);
    });
}
