// Custom Journal Entry behavior for Cash Book / Cost Type integration

frappe.ui.form.on('Journal Entry', {
    refresh(frm) {
        // Form refresh handler
    }
});

frappe.ui.form.on('Journal Entry Account', {
    account: function(frm, cdt, cdn) {
        var row = locals[cdt][cdn];
        if (row.account) {
            frappe.db.get_value('Account', row.account, 'custom_cost_type', function(value) {
                if (value && value.custom_cost_type && !row.custom_type) {
                    frappe.model.set_value(cdt, cdn, 'custom_type', value.custom_cost_type);
                }
            });
        }
    }
});
