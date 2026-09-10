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
		if row.get("summary_key") and row.get("current_amount") is not None:
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


def get_raw_materials_stock(company, date_ref, is_opening=False):
	"""
	Calculates the valuation balance of Raw Materials at date_ref.
	First queries the Stock Ledger for items in 'Raw Material' Item Group.
	Falls back to GL Entry accounts matching raw material or stock in hand.
	"""
	if not company or not date_ref:
		return 0.0

	operator = "<" if is_opening else "<="

	# 1. Stock Ledger for items belonging to Raw Material item group
	sle_res = frappe.db.sql(f"""
		SELECT SUM(sle.stock_value_difference) as val
		FROM `tabStock Ledger Entry` sle
		INNER JOIN `tabItem` item ON sle.item_code = item.name
		WHERE sle.company = %s
		  AND sle.posting_date {operator} %s
		  AND (item.item_group = 'Raw Material' OR LOWER(item.item_group) LIKE '%%raw%%')
		  AND sle.is_cancelled = 0
	""", (company, date_ref), as_dict=1)

	if sle_res and sle_res[0].get("val") is not None and abs(flt(sle_res[0].val)) > 0:
		return abs(flt(sle_res[0].val))

	# 2. Fallback: GL Entry cumulative balance on accounts matching raw material or stock in hand
	gl_res = frappe.db.sql(f"""
		SELECT SUM(gl.debit - gl.credit) as balance
		FROM `tabGL Entry` gl
		INNER JOIN `tabAccount` acc ON gl.account = acc.name
		WHERE gl.company = %s
		  AND gl.posting_date {operator} %s
		  AND gl.is_cancelled = 0
		  AND (LOWER(acc.name) LIKE '%%raw material%%' OR LOWER(acc.name) LIKE '%%stock in hand%%')
	""", (company, date_ref), as_dict=1)

	if gl_res and gl_res[0].get("balance") is not None:
		return abs(flt(gl_res[0].balance))

	return 0.0


def get_purchases_total(company, from_date, to_date):
	"""
	Calculates purchases for the period:
	1. From submitted Purchase Invoices (focusing on Raw Material items, then all items).
	2. From Cash Book entries (Type = 'Purchases' or account name matching purchase).
	3. Fallback to GL entries on purchase accounts.
	"""
	if not company:
		return 0.0

	total_purchases = 0.0

	# 1. Purchase Invoices specifically for Raw Material items
	pi_raw = frappe.db.sql("""
		SELECT SUM(pii.base_net_amount) as total
		FROM `tabPurchase Invoice Item` pii
		INNER JOIN `tabPurchase Invoice` pi ON pii.parent = pi.name
		WHERE pi.company = %s
		  AND pi.posting_date BETWEEN %s AND %s
		  AND pi.docstatus = 1
		  AND (pii.item_group = 'Raw Material' OR LOWER(pii.item_group) LIKE '%%raw%%')
	""", (company, from_date, to_date), as_dict=1)

	if pi_raw and pi_raw[0].get("total") is not None and flt(pi_raw[0].total) > 0:
		total_purchases += flt(pi_raw[0].total)
	else:
		# If no specific Raw Material lines, sum all submitted Purchase Invoices in the period
		pi_all = frappe.db.sql("""
			SELECT SUM(pii.base_net_amount) as total
			FROM `tabPurchase Invoice Item` pii
			INNER JOIN `tabPurchase Invoice` pi ON pii.parent = pi.name
			WHERE pi.company = %s
			  AND pi.posting_date BETWEEN %s AND %s
			  AND pi.docstatus = 1
		""", (company, from_date, to_date), as_dict=1)
		if pi_all and pi_all[0].get("total") is not None and flt(pi_all[0].total) > 0:
			total_purchases += flt(pi_all[0].total)

	# 2. Add Cash Purchases from Cash Book entries
	cb_purchases = frappe.db.sql("""
		SELECT SUM(CASE WHEN cba.debit > 0 THEN cba.debit ELSE cba.credit END) as total
		FROM `tabCash Book Account` cba
		INNER JOIN `tabCash Book Entry` cbe ON cba.parent = cbe.name
		WHERE cbe.company = %s
		  AND cba.post_date BETWEEN %s AND %s
		  AND cbe.docstatus = 1
		  AND (cba.type = 'Purchases' OR LOWER(cba.account) LIKE '%%purchase%%')
	""", (company, from_date, to_date), as_dict=1)

	if cb_purchases and cb_purchases[0].get("total") is not None and flt(cb_purchases[0].total) > 0:
		total_purchases += flt(cb_purchases[0].total)

	# 3. Fallback to GL Entry purchases if still zero
	if total_purchases == 0.0:
		gl_purchases = frappe.db.sql("""
			SELECT SUM(gl.debit - gl.credit) as balance
			FROM `tabGL Entry` gl
			INNER JOIN `tabAccount` acc ON gl.account = acc.name
			WHERE gl.company = %s
			  AND gl.posting_date BETWEEN %s AND %s
			  AND gl.is_cancelled = 0
			  AND (LOWER(acc.name) LIKE '%%purchase%%' OR LOWER(acc.name) LIKE '%%stock received but not billed%%')
		""", (company, from_date, to_date), as_dict=1)
		if gl_purchases and gl_purchases[0].get("balance") is not None:
			total_purchases += abs(flt(gl_purchases[0].balance))

	return total_purchases


def get_direct_materials_manufacture_cost(company, from_date, to_date):
	"""
	Calculates direct materials consumed in production from Stock Entry:
	Total outgoing value where stock_entry_type is Manufacture (or purpose is Manufacture)
	filtered by posting_date between from_date and to_date, docstatus = 1.
	"""
	if not company or not from_date or not to_date:
		return 0.0

	res = frappe.db.sql("""
		SELECT SUM(total_outgoing_value) as total_val
		FROM `tabStock Entry`
		WHERE company = %s
		  AND posting_date BETWEEN %s AND %s
		  AND (stock_entry_type = 'Manufacture' OR purpose = 'Manufacture')
		  AND docstatus = 1
	""", (company, from_date, to_date), as_dict=1)

	if res and res[0].get("total_val") is not None:
		return flt(res[0].total_val)

	return 0.0


def get_cash_book_cost_rows(company, cost_type, from_date, to_date, prev_from_date=None, prev_to_date=None, compare_prev=0):
	"""
	Fetches accounts linked in Cash Book Entries categorized by cost_type (e.g. 'Direct Cost', 'Indirect Cost').
	Returns a list of tuples: (account_display_name, current_amount, previous_amount)
	and totals.
	"""
	query = """
		SELECT
			cba.account,
			COALESCE(acc.account_name, cba.account) as account_name,
			SUM(CASE WHEN cba.debit > 0 THEN cba.debit ELSE cba.credit END) as amount
		FROM
			`tabCash Book Account` cba
		INNER JOIN
			`tabCash Book Entry` cbe ON cba.parent = cbe.name
		LEFT JOIN
			`tabAccount` acc ON cba.account = acc.name
		WHERE
			cbe.company = %s
			AND cba.post_date BETWEEN %s AND %s
			AND cbe.docstatus = 1
			AND cba.type = %s
		GROUP BY
			cba.account
		ORDER BY
			account_name ASC
	"""
	curr_entries = frappe.db.sql(query, (company, from_date, to_date, cost_type), as_dict=1)
	curr_map = {r.account: {"name": r.account_name, "amount": flt(r.amount)} for r in curr_entries}

	prev_map = {}
	if compare_prev and prev_from_date and prev_to_date:
		prev_entries = frappe.db.sql(query, (company, prev_from_date, prev_to_date, cost_type), as_dict=1)
		prev_map = {r.account: {"name": r.account_name, "amount": flt(r.amount)} for r in prev_entries}

	all_accounts = set(curr_map.keys()) | set(prev_map.keys())
	rows = []
	tot_curr = 0.0
	tot_prev = 0.0

	for acc in sorted(all_accounts, key=lambda a: (curr_map.get(a) or prev_map.get(a))["name"]):
		display_name = (curr_map.get(acc) or prev_map.get(acc))["name"]
		c_val = curr_map.get(acc, {}).get("amount", 0.0)
		p_val = prev_map.get(acc, {}).get("amount", 0.0)

		if c_val != 0.0 or p_val != 0.0:
			tot_curr += c_val
			tot_prev += p_val
			rows.append((display_name, c_val, p_val))

	return rows, tot_curr, tot_prev


def build_cost_of_sales_data(company, from_date, to_date, prev_from_date, prev_to_date, compare_prev, currency, company_title=""):
	gl_map_curr = get_gl_entries_by_account(company, from_date, to_date)
	gl_map_prev = get_gl_entries_by_account(company, prev_from_date, prev_to_date) if compare_prev else {}

	def get_val(keywords, gl_map, is_opening=False, is_closing=False, date_ref=None):
		return query_account_balance(company, keywords, gl_map, is_opening, is_closing, date_ref)

	# 1. Raw Materials & Purchases
	open_inv_curr = get_raw_materials_stock(company, from_date, is_opening=True)
	open_inv_prev = get_raw_materials_stock(company, prev_from_date, is_opening=True) if compare_prev else 0.0

	purchases_curr = get_purchases_total(company, from_date, to_date)
	purchases_prev = get_purchases_total(company, prev_from_date, prev_to_date) if compare_prev else 0.0

	carriage_curr = get_val(["carriage inward", "freight", "inward transport"], gl_map_curr)
	carriage_prev = get_val(["carriage inward", "freight", "inward transport"], gl_map_prev) if compare_prev else 0.0

	subtotal_mat_curr = open_inv_curr + purchases_curr + carriage_curr
	subtotal_mat_prev = open_inv_prev + purchases_prev + carriage_prev

	close_inv_curr = get_raw_materials_stock(company, to_date, is_opening=False)
	close_inv_prev = get_raw_materials_stock(company, prev_to_date, is_opening=False) if compare_prev else 0.0

	cost_raw_consumed_curr = subtotal_mat_curr - close_inv_curr
	cost_raw_consumed_prev = subtotal_mat_prev - close_inv_prev

	# 2. Direct Costs (Direct Materials from Stock Entry Manufacture + Cash Book Type = 'Direct Cost')
	direct_mat_curr = get_direct_materials_manufacture_cost(company, from_date, to_date)
	direct_mat_prev = get_direct_materials_manufacture_cost(company, prev_from_date, prev_to_date) if compare_prev else 0.0

	direct_rows, tot_direct_cb_curr, tot_direct_cb_prev = get_cash_book_cost_rows(
		company, "Direct Cost", from_date, to_date, prev_from_date, prev_to_date, compare_prev
	)

	tot_direct_curr = direct_mat_curr + tot_direct_cb_curr
	tot_direct_prev = direct_mat_prev + tot_direct_cb_prev

	direct_cost_production_curr = cost_raw_consumed_curr + tot_direct_curr
	direct_cost_production_prev = cost_raw_consumed_prev + tot_direct_prev

	# 3. Factory Overheads (Only accounts linked on Cash Book Entry with Type = 'Indirect Cost')
	overhead_rows, tot_overhead_curr, tot_overhead_prev = get_cash_book_cost_rows(
		company, "Indirect Cost", from_date, to_date, prev_from_date, prev_to_date, compare_prev
	)

	total_cost_production_curr = direct_cost_production_curr + tot_overhead_curr
	total_cost_production_prev = direct_cost_production_prev + tot_overhead_prev

	# 4. Finished Goods Adjustment (closing stock of finished goods)
	close_fg_curr = query_finished_goods_stock(company, to_date, gl_map_curr)
	close_fg_prev = query_finished_goods_stock(company, prev_to_date, gl_map_prev) if compare_prev else 0.0

	cost_of_sales_curr = total_cost_production_curr - close_fg_curr
	cost_of_sales_prev = total_cost_production_prev - close_fg_prev

	# Construct structured output rows
	data = []

	def add_row(item_name, c_amt=None, p_amt=None, is_bold=False, is_heading=False, is_less=False, summary_key=None, indent=0):
		prefix = "    " * indent if item_name else ""
		row = {
			"item_name": prefix + item_name if item_name else "",
			"current_amount": c_amt if c_amt is not None else None,
			"currency": currency,
			"company_title": company_title,
			"is_bold": 1 if is_bold else 0,
			"is_heading": 1 if is_heading else 0,
			"is_less": 1 if is_less else 0,
		}
		if compare_prev:
			row["previous_amount"] = p_amt if p_amt is not None else None
		if summary_key:
			row["summary_key"] = summary_key
		data.append(row)

	# Build rows: Section headings do NOT have amounts, only subtotal and item rows do!
	add_row("19 Cost of sales", None, None, is_bold=True, is_heading=True)
	add_row("Opening inventory", open_inv_curr, open_inv_prev, indent=1)
	add_row("Add: Purchases", purchases_curr, purchases_prev, indent=1)
	add_row("Carriage inwards", carriage_curr, carriage_prev, indent=2)
	add_row("Subtotal", subtotal_mat_curr, subtotal_mat_prev, is_bold=True, indent=2)
	add_row("Less: Closing inventory", close_inv_curr, close_inv_prev, is_less=True, indent=1)
	add_row("Total cost of raw-materials consumed", cost_raw_consumed_curr, cost_raw_consumed_prev, is_bold=True, summary_key=_("Raw Materials Consumed"))

	add_row("", None, None)
	add_row("Add: Direct costs", None, None, is_bold=True, is_heading=True)
	add_row("Direct Manufacture", direct_mat_curr, direct_mat_prev, indent=1)
	for label, v_c, v_p in direct_rows:
		add_row(label, v_c, v_p, indent=1)
	add_row("Total Direct costs", tot_direct_curr, tot_direct_prev, is_bold=True, indent=1)

	add_row("", None, None)
	add_row("Direct cost of production", direct_cost_production_curr, direct_cost_production_prev, is_bold=True, is_heading=True, summary_key=_("Direct Cost of Production"))

	add_row("", None, None)
	add_row("Add: Factory overheads", None, None, is_bold=True, is_heading=True)
	for label, v_c, v_p in overhead_rows:
		add_row(label, v_c, v_p, indent=1)
	add_row("Total Factory overheads", tot_overhead_curr, tot_overhead_prev, is_bold=True, indent=1)

	add_row("", None, None)
	add_row("Total cost of production", total_cost_production_curr, total_cost_production_prev, is_bold=True, is_heading=True, summary_key=_("Total Cost of Production"))

	add_row("", None, None)
	add_row("Less closing stock of finished goods", close_fg_curr, close_fg_prev, is_less=True, indent=1)
	add_row("Cost of sales", cost_of_sales_curr, cost_of_sales_prev, is_bold=True, is_heading=True, summary_key=_("Cost of Sales"))

	return data


def query_finished_goods_stock(company, date_ref, gl_map):
	"""
	Calculates closing stock of finished goods from stock ledger or finished goods accounts.
	"""
	if not company or not date_ref:
		return 0.0

	# 1. Check Stock Ledger for Finished Goods category
	sle_res = frappe.db.sql("""
		SELECT SUM(sle.stock_value_difference) as val
		FROM `tabStock Ledger Entry` sle
		INNER JOIN `tabItem` item ON sle.item_code = item.name
		WHERE sle.company = %s
		  AND sle.posting_date <= %s
		  AND (item.item_group = 'Finished Goods' OR LOWER(item.item_group) LIKE '%%finished%%' OR item.item_group = 'Products')
		  AND sle.is_cancelled = 0
	""", (company, date_ref), as_dict=1)

	if sle_res and sle_res[0].get("val") is not None and abs(flt(sle_res[0].val)) > 0:
		return abs(flt(sle_res[0].val))

	# 2. Fallback to GL entries
	for acc_name, row in gl_map.items():
		acc_lower = acc_name.lower()
		if any(k in acc_lower for k in ["finished goods", "stock of finished goods"]):
			return abs(flt(row.get("balance", 0.0)))

	return 0.0


def get_gl_entries_by_account(company, from_date, to_date):
	if not company:
		return {}

	has_custom_cost_type = False
	try:
		has_custom_cost_type = frappe.db.has_column("Account", "custom_cost_type")
	except Exception:
		pass

	cost_type_col = "acc.custom_cost_type," if has_custom_cost_type else "'' as custom_cost_type,"

	entries = frappe.db.sql(f"""
		SELECT
			gl.account,
			acc.account_name,
			acc.root_type,
			acc.account_type,
			{cost_type_col}
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


def query_account_balance(company, keywords, gl_map, is_opening=False, is_closing=False, date_ref=None, exclude_accounts=None):
	if not company:
		return 0.0

	total = 0.0
	exclude_set = set(exclude_accounts) if exclude_accounts else set()

	if is_opening or is_closing:
		operator = "<" if is_opening else "<="
		kw_condition = " OR ".join([f"LOWER(acc.name) LIKE {frappe.db.escape('%' + k.lower() + '%')}" for k in keywords])
		exclude_cond = ""
		if exclude_set:
			escaped_accs = ", ".join([frappe.db.escape(a) for a in exclude_set])
			exclude_cond = f"AND acc.name NOT IN ({escaped_accs})"

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
				{exclude_cond}
		""", (company, date_ref), as_dict=1)

		if res and res[0].balance:
			return abs(flt(res[0].balance))
		return 0.0

	for acc_name, row in gl_map.items():
		if acc_name in exclude_set or row.get("account") in exclude_set:
			continue
		c_type = (row.get("custom_cost_type") or "").strip()
		if c_type in ["Direct Cost", "Indirect Cost", "Purchases"]:
			continue
		acc_lower = acc_name.lower()
		for kw in keywords:
			if kw.lower() in acc_lower:
				total += flt(row.balance)
				break

	return abs(total)
