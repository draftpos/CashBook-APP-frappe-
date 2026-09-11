import frappe
from frappe import _

def apply_gl_report_enhancements():
    """
    Patches ERPNext General Ledger report to include custom_type filter,
    column right after account, and query conditions.
    """
    try:
        import erpnext.accounts.report.general_ledger.general_ledger as gl_report

        if getattr(gl_report, "_custom_type_patched", False):
            return

        original_get_columns = gl_report.get_columns
        original_get_conditions = gl_report.get_conditions
        original_execute = gl_report.execute

        def custom_get_columns(filters):
            columns = original_get_columns(filters)
            has_type = any(c.get("fieldname") == "custom_type" for c in columns if isinstance(c, dict))
            if not has_type:
                type_col = {
                    "label": _("Type"),
                    "fieldname": "custom_type",
                    "fieldtype": "Data",
                    "width": 140
                }
                account_idx = -1
                for idx, col in enumerate(columns):
                    if isinstance(col, dict) and col.get("fieldname") == "account":
                        account_idx = idx
                        break
                if account_idx != -1:
                    columns.insert(account_idx + 1, type_col)
                else:
                    columns.append(type_col)
            return columns

        def custom_get_conditions(filters):
            conditions = original_get_conditions(filters)
            if filters and filters.get("custom_type"):
                if frappe.db.has_column("GL Entry", "custom_type"):
                    type_cond = "custom_type = %(custom_type)s"
                    if isinstance(conditions, str):
                        if conditions.strip():
                            conditions = f"{conditions} and {type_cond}"
                        else:
                            conditions = f"and {type_cond}"
                    elif isinstance(conditions, list):
                        conditions.append(type_cond)
            return conditions

        def custom_execute(filters=None):
            if not filters:
                filters = {}
            res_tuple = original_execute(filters)
            if isinstance(res_tuple, (list, tuple)) and len(res_tuple) >= 2:
                columns = custom_get_columns(filters)
                res = res_tuple[1]
                if res and frappe.db.has_column("GL Entry", "custom_type"):
                    gl_names = [r.get("gl_entry") for r in res if isinstance(r, dict) and r.get("gl_entry")]
                    if gl_names:
                        gl_types = dict(frappe.db.sql("""
                            SELECT name, custom_type
                            FROM `tabGL Entry`
                            WHERE name IN %s
                        """, [tuple(gl_names)]))
                        
                        for row in res:
                            if isinstance(row, dict):
                                gle_name = row.get("gl_entry")
                                if gle_name and gle_name in gl_types:
                                    row["custom_type"] = gl_types[gle_name]
                
                new_tuple = list(res_tuple)
                new_tuple[0] = columns
                new_tuple[1] = res
                return tuple(new_tuple)
            return res_tuple

        gl_report.get_columns = custom_get_columns
        gl_report.get_conditions = custom_get_conditions
        gl_report.execute = custom_execute
        gl_report._custom_type_patched = True

    except Exception as e:
        frappe.log_error(f"Failed to patch General Ledger report: {str(e)}", "Cash Book Report Patch")


@frappe.whitelist()
def custom_get_script(report_name: str):
    """
    Overrides frappe.desk.query_report.get_script to ensure
    the Type filter is always embedded directly in General Ledger report JS.
    """
    from frappe.desk.query_report import (
        get_report_doc,
        get_module_path,
        scrub,
        get_html_format,
        render_include
    )
    import os

    report = get_report_doc(report_name)
    module = report.module or frappe.db.get_value("DocType", report.ref_doctype, "module")
    is_custom_module = frappe.get_cached_value("Module Def", module, "custom")
    module_path = "" if is_custom_module else get_module_path(module)
    report_folder = module_path and os.path.join(module_path, "report", scrub(report.name))
    script_path = report_folder and os.path.join(report_folder, scrub(report.name) + ".js")
    print_path = report_folder and os.path.join(report_folder, scrub(report.name) + ".html")

    script = None
    if os.path.exists(script_path):
        with open(script_path) as f:
            script = f.read()
            script += f"\n\n//# sourceURL={scrub(report.name)}.js"

    html_format = get_html_format(print_path)

    if not script and report.javascript:
        script = report.javascript
        script += f"\n\n//# sourceURL={scrub(report.name)}__custom"

    if not script:
        script = "frappe.query_reports['{}']={{}}".format(report_name)

    if report_name == "General Ledger" and script:
        injection = """
        (function() {
            if (typeof frappe !== 'undefined' && frappe.query_reports && frappe.query_reports['General Ledger']) {
                var gl = frappe.query_reports['General Ledger'];
                if (gl.filters && Array.isArray(gl.filters)) {
                    var exists = gl.filters.some(function(f) { return f.fieldname === 'custom_type'; });
                    if (!exists) {
                        var pIdx = gl.filters.findIndex(function(f) { return f.fieldname === 'project'; });
                        var insIdx = pIdx !== -1 ? pIdx + 1 : 10;
                        gl.filters.splice(insIdx, 0, {
                            fieldname: 'custom_type',
                            label: __('Type'),
                            fieldtype: 'Select',
                            options: [
                                '',
                                'Direct Cost',
                                'Indirect Cost',
                                'Distribution costs',
                                'Administrative expenses',
                                'Other expenses'
                            ],
                            width: '140px'
                        });
                    }
                }
            }
        })();
        """
        script = script + "\n" + injection

    return {
        "script": render_include(script),
        "html_format": html_format,
        "execution_time": frappe.cache.hget("report_execution_time", report_name) or 0,
        "filters": report.filters,
        "custom_report_name": report.name if report.get("is_custom_report") else None,
    }
