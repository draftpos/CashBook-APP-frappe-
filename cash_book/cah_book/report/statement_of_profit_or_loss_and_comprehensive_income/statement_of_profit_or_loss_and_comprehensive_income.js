// Copyright (c) 2026, munyaradzi chirove and contributors
// For license information, please see license.txt

frappe.query_reports["Statement of Profit or Loss and Comprehensive Income"] = {
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
		},
		{
			fieldname: "show_inflation_adjusted",
			label: __("Show Inflation Adjusted"),
			fieldtype: "Check",
			default: 1
		},
		{
			fieldname: "inflation_factor_current",
			label: __("Current Year Inflation Factor"),
			fieldtype: "Float",
			default: 1.015,
			depends_on: "eval:doc.show_inflation_adjusted"
		},
		{
			fieldname: "inflation_factor_prior",
			label: __("Prior Year Inflation Factor"),
			fieldtype: "Float",
			default: 1.580,
			depends_on: "eval:doc.show_inflation_adjusted"
		}
	],
	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data) return value;

		if (data.is_bold) {
			value = $(`<span>${value}</span>`).css("font-weight", "bold").wrap("<p>").parent().html();
		}
		if (data.is_heading) {
			value = $(`<span>${value}</span>`).css({
				"font-weight": "800",
				"color": "#111827",
				"font-size": "1.05em"
			}).wrap("<p>").parent().html();
		}
		if (data.is_final) {
			value = $(`<span>${value}</span>`).css({
				"font-weight": "800",
				"text-decoration": "underline double"
			}).wrap("<p>").parent().html();
		}
		if (data.is_less && column.fieldtype === "Currency" && data[column.fieldname] > 0) {
			let formatted_val = frappe.format(data[column.fieldname], { fieldtype: "Currency" }, { inline: 1 });
			value = `<span style="color: #dc2626; font-weight: 600;">(${formatted_val})</span>`;
		} else if (data[column.fieldname] < 0 && column.fieldtype === "Currency") {
			let abs_val = Math.abs(data[column.fieldname]);
			let formatted_val = frappe.format(abs_val, { fieldtype: "Currency" }, { inline: 1 });
			value = `<span style="color: #dc2626; font-weight: 600;">(${formatted_val})</span>`;
		}
		return value;
	}
};
