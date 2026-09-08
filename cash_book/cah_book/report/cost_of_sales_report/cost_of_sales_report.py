# Copyright (c) 2026, munyaradzi chirove and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate, add_years, formatdate, nowdate

def execute(filters=None):
	if not filters:
		filters = {}

	company = filters.get("company") or frappe.defaults.get_user_default("Company")
	curr_date = getdate(nowdate())
	default_from = f"{curr_date.year}-01-01"
	default_to = f"{curr_date.year}-12-31"

	from_date = getdate(filters.get("from_date") or default_from)
	to_date = getdate(filters.get("to_date") or default_to)
	compare_prev = filters.get("compare_with_previous_year") if filters.get("compare_with_previous_year") is not None else 1

	prev_from_date = add_years(from_date, -1)
	prev_to_date = add_years(to_date, -1)

	company_currency = frappe.get_cached_value("Company", company, "default_currency") if company else "USD"

	# Dynamically fetch the formal company name from the selected Company document
	company_title = ""
	if company:
		company_title = (
			frappe.get_cached_value("Company", company, "company_name")
			or frappe.get_cached_value("Company", company, "name")
			or company
		).upper()

	# Define columns
	current_label = f"{formatdate(from_date)} - {formatdate(to_date)}"
	prev_label = f"{formatdate(prev_from_date)} - {formatdate(prev_to_date)}"

	columns = [
		{
			"label": _("Notes to Manufacturing Account / Cost of Sales"),
			"fieldname": "item_name",
			"fieldtype": "Data",
			"width": 380,
		},
		{
			"label": current_label,
			"fieldname": "current_amount",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 170,
		}
	]

	if compare_prev:
		columns.append({
			"label": prev_label,
			"fieldname": "previous_amount",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 170,
		})

	# Calculate statement data
	data = build_cost_of_sales_data(company, from_date, to_date, prev_from_date, prev_to_date, compare_prev, company_currency, company_title)

	# Build report summary cards
	report_summary = []
	for row in data:
		if row.get("summary_key"):
			report_summary.append({
				"value": row.get("current_amount"),
				"label": row.get("summary_key"),
				"datatype": "Currency",
				"currency": company_currency
			})

	# Dynamically generated header banner using the selected company's registered name
	header_message = ""
	if company_title:
		formatted_date_str = to_date.strftime("%B %d, %Y")
		header_message = f"""
		<div style="text-align: center; margin: 15px auto 25px auto; padding: 15px; max-width: 800px; background: #ffffff; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); border: 1px solid #e5e7eb;">
			<div style="font-size: 18px; font-weight: 800; text-transform: uppercase; color: #111827; letter-spacing: 0.5px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
				{company_title}
			</div>
			<div style="font-size: 15px; font-weight: 700; text-transform: uppercase; color: #1f2937; margin: 4px 0;">
				NOTES TO THE FINANCIAL STATEMENTS
			</div>
			<div style="font-size: 14px; font-weight: 600; color: #374151;">
				for the year ended {formatted_date_str}
			</div>
		</div>
		"""

	return columns, data, header_message, None, report_summary


def build_cost_of_sales_data(company, from_date, to_date, prev_from_date, prev_to_date, compare_prev, currency, company_title=""):
	gl_map_curr = get_gl_entries_by_account(company, from_date, to_date)
	gl_map_prev = get_gl_entries_by_account(company, prev_from_date, prev_to_date) if compare_prev else {}

	def get_val(keywords, gl_map, is_opening=False, is_closing=False, date_ref=None):
		return query_account_balance(company, keywords, gl_map, is_opening, is_closing, date_ref)

	# 1. Raw Materials & Purchases
	open_inv_curr = get_val(["raw material", "stock in hand", "inventory"], gl_map_curr, is_opening=True, date_ref=from_date)
	open_inv_prev = get_val(["raw material", "stock in hand", "inventory"], gl_map_prev, is_opening=True, date_ref=prev_from_date) if compare_prev else 0.0

	purchases_curr = get_val(["purchase", "stock received but not billed", "raw materials purchase"], gl_map_curr)
	purchases_prev = get_val(["purchase", "stock received but not billed", "raw materials purchase"], gl_map_prev) if compare_prev else 0.0

	carriage_curr = get_val(["carriage inward", "freight", "inward transport"], gl_map_curr)
	carriage_prev = get_val(["carriage inward", "freight", "inward transport"], gl_map_prev) if compare_prev else 0.0

	subtotal_mat_curr = open_inv_curr + purchases_curr + carriage_curr
	subtotal_mat_prev = open_inv_prev + purchases_prev + carriage_prev

	close_inv_curr = get_val(["raw material", "stock in hand", "inventory"], gl_map_curr, is_closing=True, date_ref=to_date)
	close_inv_prev = get_val(["raw material", "stock in hand", "inventory"], gl_map_prev, is_closing=True, date_ref=prev_to_date) if compare_prev else 0.0

	cost_raw_consumed_curr = subtotal_mat_curr - close_inv_curr
	cost_raw_consumed_prev = subtotal_mat_prev - close_inv_prev

	# 2. Direct Costs
	direct_items = [
		("Direct labour", ["direct labour", "direct labor", "wages - direct", "factory wages"]),
		("Electricity", ["electricity - direct", "factory electricity", "electricity"]),
		("Generator fuel", ["generator fuel - direct", "generator fuel", "diesel - factory"]),
		("Water", ["water - direct", "factory water", "water charges"]),
	]

	direct_rows = []
	tot_direct_curr = 0.0
	tot_direct_prev = 0.0
	for label, kw in direct_items:
		v_curr = get_val(kw, gl_map_curr)
		v_prev = get_val(kw, gl_map_prev) if compare_prev else 0.0
		tot_direct_curr += v_curr
		tot_direct_prev += v_prev
		direct_rows.append((label, v_curr, v_prev))

	direct_cost_production_curr = cost_raw_consumed_curr + tot_direct_curr
	direct_cost_production_prev = cost_raw_consumed_prev + tot_direct_prev

	# 3. Factory Overheads (Indirect costs)
	overhead_items = [
		("Indirect labour", ["indirect labour", "indirect labor", "factory supervisor salary"]),
		("Water", ["water - indirect", "factory water overhead", "water overhead"]),
		("Electricity", ["electricity - indirect", "overhead electricity"]),
		("Cleaning materials", ["cleaning material", "cleaning supplies", "sanitation"]),
		("Closures", ["closures", "bottle closures", "corks", "caps"]),
		("Canteen expenses", ["canteen expense", "staff canteen", "canteen"]),
		("Protective clothing", ["protective clothing", "safety gear", "uniforms - factory"]),
		("Repairs and maintenance", ["repair", "repairs", "repairs and maintenance", "repairs & maintenance", "factory repairs", "plant maintenance"]),
		("Generator fuel", ["generator fuel - overhead", "generator fuel indirect"]),
		("Travelling and subsistence", ["travel and subsistence", "travelling and subsistence", "factory travel"]),
		("Depreciation charge", ["depreciation - factory", "depreciation of plant", "depreciation"]),
	]

	overhead_rows = []
	tot_overhead_curr = 0.0
	tot_overhead_prev = 0.0
	for label, kw in overhead_items:
		v_curr = get_val(kw, gl_map_curr)
		v_prev = get_val(kw, gl_map_prev) if compare_prev else 0.0
		tot_overhead_curr += v_curr
		tot_overhead_prev += v_prev
		overhead_rows.append((label, v_curr, v_prev))

	total_cost_production_curr = direct_cost_production_curr + tot_overhead_curr
	total_cost_production_prev = direct_cost_production_prev + tot_overhead_prev

	# 4. Finished Goods Adjustment
	close_fg_curr = get_val(["finished goods", "stock of finished goods"], gl_map_curr, is_closing=True, date_ref=to_date)
	close_fg_prev = get_val(["finished goods", "stock of finished goods"], gl_map_prev, is_closing=True, date_ref=prev_to_date) if compare_prev else 0.0

	cost_of_sales_curr = total_cost_production_curr - close_fg_curr
	cost_of_sales_prev = total_cost_production_prev - close_fg_prev

	# Construct structured output rows
	data = []

	def add_row(item_name, c_amt=None, p_amt=None, is_bold=False, is_heading=False, is_less=False, summary_key=None, indent=0):
		prefix = "    " * indent
		row = {
			"item_name": prefix + item_name,
			"current_amount": c_amt if c_amt is not None else 0.0,
			"currency": currency,
			"company_title": company_title,
			"is_bold": 1 if is_bold else 0,
			"is_heading": 1 if is_heading else 0,
			"is_less": 1 if is_less else 0,
		}
		if compare_prev:
			row["previous_amount"] = p_amt if p_amt is not None else 0.0
		if summary_key:
			row["summary_key"] = summary_key
		data.append(row)

	# Build rows exactly as in reference note
	add_row("19 Cost of sales", is_bold=True, is_heading=True)
	add_row("Opening inventory", open_inv_curr, open_inv_prev, indent=1)
	add_row("Add: Purchases", purchases_curr, purchases_prev, indent=1)
	add_row("Carriage inwards", carriage_curr, carriage_prev, indent=2)
	add_row("Subtotal", subtotal_mat_curr, subtotal_mat_prev, is_bold=True, indent=2)
	add_row("Less: Closing inventory", close_inv_curr, close_inv_prev, is_less=True, indent=1)
	add_row("Total cost of raw-materials consumed", cost_raw_consumed_curr, cost_raw_consumed_prev, is_bold=True, summary_key=_("Raw Materials Consumed"))

	add_row("", None, None)
	add_row("Add: Direct costs", tot_direct_curr, tot_direct_prev, is_bold=True)
	for label, v_c, v_p in direct_rows:
		add_row(label, v_c, v_p, indent=1)
	add_row("Total Direct costs", tot_direct_curr, tot_direct_prev, is_bold=True, indent=1)

	add_row("", None, None)
	add_row("Direct cost of production", direct_cost_production_curr, direct_cost_production_prev, is_bold=True, is_heading=True, summary_key=_("Direct Cost of Production"))

	add_row("", None, None)
	add_row("Add: Factory overheads", tot_overhead_curr, tot_overhead_prev, is_bold=True)
	for label, v_c, v_p in overhead_rows:
		add_row(label, v_c, v_p, indent=1)
	add_row("Total Factory overheads", tot_overhead_curr, tot_overhead_prev, is_bold=True, indent=1)

	add_row("", None, None)
	add_row("Total cost of production", total_cost_production_curr, total_cost_production_prev, is_bold=True, is_heading=True, summary_key=_("Total Cost of Production"))

	add_row("", None, None)
	add_row("Less closing stock of finished goods", close_fg_curr, close_fg_prev, is_less=True, indent=1)
	add_row("Cost of sales", cost_of_sales_curr, cost_of_sales_prev, is_bold=True, is_heading=True, summary_key=_("Cost of Sales"))

	return data


def get_gl_entries_by_account(company, from_date, to_date):
	if not company:
		return {}

	entries = frappe.db.sql("""
		SELECT
			gl.account,
			acc.account_name,
			acc.root_type,
			acc.account_type,
			SUM(gl.debit - gl.credit) AS balance,
			SUM(gl.debit) as total_debit,
			SUM(gl.credit) as total_credit
		FROM
			`tabGL Entry` gl
		INNER JOIN
			`tabAccount` acc ON gl.account = acc.name
		WHERE
			gl.company = %s
			AND gl.posting_date BETWEEN %s AND %s
			AND gl.is_cancelled = 0
		GROUP BY
			gl.account
	""", (company, from_date, to_date), as_dict=1)

	result = {}
	for row in entries:
		result[row.account] = row
	return result


def query_account_balance(company, keywords, gl_map, is_opening=False, is_closing=False, date_ref=None):
	if not company:
		return 0.0

	total = 0.0

	# Check for Stock/Inventory balance at date if opening/closing stock
	if is_opening or is_closing:
		operator = "<" if is_opening else "<="
		kw_condition = " OR ".join([f"LOWER(acc.name) LIKE {frappe.db.escape('%' + k.lower() + '%')}" for k in keywords])

		res = frappe.db.sql(f"""
			SELECT
				SUM(gl.debit - gl.credit) as balance
			FROM
				`tabGL Entry` gl
			INNER JOIN
				`tabAccount` acc ON gl.account = acc.name
			WHERE
				gl.company = %s
				AND gl.posting_date {operator} %s
				AND gl.is_cancelled = 0
				AND ({kw_condition})
		""", (company, date_ref), as_dict=1)

		if res and res[0].balance:
			return abs(flt(res[0].balance))
		return 0.0

	# Period activity from preloaded GL map
	for acc_name, row in gl_map.items():
		acc_lower = acc_name.lower()
		for kw in keywords:
			if kw.lower() in acc_lower:
				total += flt(row.balance)
				break

	return abs(total)
