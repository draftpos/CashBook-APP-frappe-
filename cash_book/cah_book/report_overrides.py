import frappe
from frappe import _

def apply_gl_report_enhancements():
    """
    Patches ERPNext General Ledger report to include custom_type filter,
    column, and query conditions.
    """
    try:
        import erpnext.accounts.report.general_ledger.general_ledger as gl_report

        if getattr(gl_report, "_custom_type_patched", False):
            return

        original_get_columns = gl_report.get_columns
        original_get_conditions = gl_report.get_conditions

        def custom_get_columns(filters):
            columns = original_get_columns(filters)
            # Add Type column
            has_type = any(c.get("fieldname") == "custom_type" for c in columns if isinstance(c, dict))
            if not has_type:
                columns.append({
                    "label": _("Type"),
                    "fieldname": "custom_type",
                    "fieldtype": "Data",
                    "width": 140
                })
            return columns

        def custom_get_conditions(filters):
            conditions = original_get_conditions(filters)
            if filters and filters.get("custom_type"):
                if frappe.db.has_column("GL Entry", "custom_type"):
                    conditions.append("custom_type = %(custom_type)s")
            return conditions

        gl_report.get_columns = custom_get_columns
        gl_report.get_conditions = custom_get_conditions
        gl_report._custom_type_patched = True

    except Exception as e:
        frappe.log_error(f"Failed to patch General Ledger report: {str(e)}", "Cash Book Report Patch")
