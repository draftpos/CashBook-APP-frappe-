// Copyright (c) 2026, munyaradzi chirove and contributors
// For license information, please see license.txt

frappe.query_reports["Cost of Sales Report"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.year_start(),
			reqd: 1
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.year_end(),
			reqd: 1
		},
		{
			fieldname: "compare_with_previous_year",
			label: __("Compare with Prior Period"),
			fieldtype: "Check",
			default: 1
		}
	],
	formatter: function (value, row, column, data, default_formatter) {
		// Empty row
		if (!data || !data.item_name || !data.item_name.trim()) {
			return "";
		}

		// If amount column is null/undefined, do not display 0.00
		if (column.fieldname.indexOf("amount") !== -1) {
			if (data[column.fieldname] === null || data[column.fieldname] === undefined || data[column.fieldname] === "") {
				return "";
			}
		}

		value = default_formatter(value, row, column, data);
		if (data && data.is_bold) {
			value = $(`<span>${value}</span>`).css("font-weight", "bold").wrap("<p>").parent().html();
		}
		if (data && data.is_heading) {
			value = $(`<span>${value}</span>`).css({
				"font-weight": "800",
				"color": "#111827",
				"font-size": "1.05em"
			}).wrap("<p>").parent().html();
		}
		if (data && data.is_less && column.fieldname.indexOf("amount") !== -1 && data[column.fieldname] > 0) {
			let formatted_val = frappe.format(data[column.fieldname], { fieldtype: "Currency" }, { inline: 1 });
			value = `<span style="color: #dc2626; font-weight: 600;">(${formatted_val})</span>`;
		}
		return value;
	}
};
