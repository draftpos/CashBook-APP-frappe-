# Copyright (c) 2026, munyaradzi chirove and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate, add_years, formatdate, nowdate
from cash_book.cah_book.report.cost_of_sales_report.cost_of_sales_report import (
	get_gl_entries_by_account,
	query_account_balance,
	build_cost_of_sales_data
)

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
	show_inflation = filters.get("show_inflation_adjusted") if filters.get("show_inflation_adjusted") is not None else 1

	inflation_factor_curr = flt(filters.get("inflation_factor_current")) or 1.015
	inflation_factor_prev = flt(filters.get("inflation_factor_prior")) or 1.580

	prev_from_date = add_years(from_date, -1)
	prev_to_date = add_years(to_date, -1)

	company_currency = frappe.get_cached_value("Company", company, "default_currency") if company else "USD"

	# Dynamic company formal name
	company_title = ""
	if company:
		company_title = (
			frappe.get_cached_value("Company", company, "company_name")
			or frappe.get_cached_value("Company", company, "name")
			or company
		).upper()

	curr_year_str = str(to_date.year)
	prev_year_str = str(prev_to_date.year)

	# Columns structure
	columns = [
		{
			"label": _("Statement of Profit or Loss"),
			"fieldname": "item_name",
			"fieldtype": "Data",
			"width": 320,
		},
		{
			"label": _("Note"),
			"fieldname": "note",
			"fieldtype": "Data",
			"width": 60,
		}
	]

	if show_inflation:
		columns.append({
			"label": _("Inflation {0} ({1})").format(curr_year_str, company_currency),
			"fieldname": "inflation_curr",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 160,
		})
		if compare_prev:
			columns.append({
				"label": _("Inflation {0} ({1})").format(prev_year_str, company_currency),
				"fieldname": "inflation_prev",
				"fieldtype": "Currency",
				"options": "currency",
				"width": 160,
			})

	columns.append({
		"label": _("Historical {0} ({1})").format(curr_year_str, company_currency),
		"fieldname": "historical_curr",
		"fieldtype": "Currency",
		"options": "currency",
		"width": 160,
	})

	if compare_prev:
		columns.append({
			"label": _("Historical {0} ({1})").format(prev_year_str, company_currency),
			"fieldname": "historical_prev",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 160,
		})

	data = build_profit_loss_data(
		company=company,
		from_date=from_date,
		to_date=to_date,
		prev_from_date=prev_from_date,
		prev_to_date=prev_to_date,
		compare_prev=compare_prev,
		show_inflation=show_inflation,
		inflation_factor_curr=inflation_factor_curr,
		inflation_factor_prev=inflation_factor_prev,
		currency=company_currency,
		company_title=company_title
	)

	report_summary = []
	for row in data:
		if row.get("summary_key"):
			report_summary.append({
				"value": row.get("historical_curr"),
				"label": row.get("summary_key"),
				"datatype": "Currency",
				"currency": company_currency
			})

	formatted_date_str = to_date.strftime("%B %d, %Y")
	header_message = f"""
	<div style="text-align: center; margin: 15px auto 25px auto; padding: 16px; max-width: 900px; background: #ffffff; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); border: 1px solid #e5e7eb;">
		<div style="font-size: 19px; font-weight: 800; text-transform: uppercase; color: #111827; letter-spacing: 0.5px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
			{company_title}
		</div>
		<div style="font-size: 15px; font-weight: 700; text-transform: uppercase; color: #1f2937; margin: 4px 0;">
			STATEMENT OF PROFIT OR LOSS AND COMPREHENSIVE INCOME
		</div>
		<div style="font-size: 14px; font-weight: 600; color: #374151;">
			for the year ended {formatted_date_str}
		</div>
	</div>
	"""

	return columns, data, header_message, None, report_summary


def get_cost_of_sales_accounts(company):
	"""
	Returns all accounts associated with Cost of Sales, Direct Cost, Indirect Cost, and Production:
	Filters by GL Entry tags, Cash Book tags, and account name/type.
	These accounts and entries MUST NEVER appear in Profit & Loss general expenses.
	"""
	cos_accounts = set()
	if not company:
		return cos_accounts

	# 1. Accounts with GL Entries tagged as Direct Cost, Indirect Cost, Purchases
	try:
		if frappe.db.has_column("GL Entry", "custom_type"):
			gl_accs = frappe.db.sql("""
				SELECT DISTINCT account
				FROM `tabGL Entry`
				WHERE (company = %s OR %s = '')
				  AND is_cancelled = 0
				  AND custom_type IN ('Direct Cost', 'Indirect Cost', 'Purchases')
			""", (company, company), as_dict=1)
			for r in gl_accs:
				if r.account:
					cos_accounts.add(r.account)
	except Exception:
		pass

	# 2. Any account linked on Cash Book Entries with type Direct Cost, Indirect Cost, Purchases
	try:
		cb_accs = frappe.db.sql("""
			SELECT DISTINCT cba.account
			FROM `tabCash Book Account` cba
			LEFT JOIN `tabCash Book Entry` cbe ON cba.parent = cbe.name
			WHERE (cbe.company = %s OR cbe.company IS NULL OR %s = '')
			  AND cba.type IN ('Direct Cost', 'Indirect Cost', 'Purchases')
		""", (company, company), as_dict=1)
		for r in cb_accs:
			if r.account:
				cos_accounts.add(r.account)
	except Exception:
		pass

	# 3. Accounts marked with custom_cost_type in Direct Cost, Indirect Cost, Purchases
	try:
		if frappe.db.has_column("Account", "custom_cost_type"):
			acc_res = frappe.db.sql("""
				SELECT name FROM `tabAccount`
				WHERE (company = %s OR %s = '')
				  AND custom_cost_type IN ('Direct Cost', 'Indirect Cost', 'Purchases')
			""", (company, company), as_dict=1)
			for r in acc_res:
				cos_accounts.add(r.name)
	except Exception:
		pass

	# 4. Any account with Direct, Indirect, Production, Factory, Manufacturing, Stock, or COGS in name/type
	try:
		name_accs = frappe.db.sql("""
			SELECT name FROM `tabAccount`
			WHERE (company = %s OR %s = '')
			  AND (
			      account_type IN ('Stock', 'Stock Received But Not Billed', 'Cost of Goods Sold')
			      OR LOWER(name) LIKE '%%direct labour%%'
			      OR LOWER(name) LIKE '%%direct labor%%'
			      OR LOWER(name) LIKE '%%direct expense%%'
			      OR LOWER(name) LIKE '%%direct material%%'
			      OR LOWER(name) LIKE '%%- direct%%'
			      OR LOWER(name) LIKE '%%direct -%%'
			      OR LOWER(name) LIKE '%%indirect labour%%'
			      OR LOWER(name) LIKE '%%indirect labor%%'
			      OR LOWER(name) LIKE '%%indirect expense%%'
			      OR LOWER(name) LIKE '%%factory overhead%%'
			      OR LOWER(name) LIKE '%%repairs and maintenance%%'
			      OR LOWER(name) LIKE '%%repair%%'
			      OR LOWER(name) LIKE '%%maintenance%%'
			      OR LOWER(name) LIKE '%%production%%'
			      OR LOWER(name) LIKE '%%manufacturing%%'
			      OR LOWER(name) LIKE '%%raw material%%'
			      OR LOWER(name) LIKE '%%stock in hand%%'
			      OR LOWER(name) LIKE '%%work in progress%%'
			  )
		""", (company, company), as_dict=1)
		for r in name_accs:
			cos_accounts.add(r.name)
	except Exception:
		pass

	return cos_accounts


def get_gl_classified_totals(company, from_date, to_date, exclude_accounts=None):
	"""
	Calculates classified totals (Direct Income, Indirect Income, Distribution costs,
	Administrative expenses, Other expenses) directly from General Ledger (GL Entry).
	Strictly excludes any entries/accounts tagged as Direct Cost, Indirect Cost, or Purchases.
	"""
	if not company:
		return {}

	has_gle_custom_type = False
	has_acc_custom_cost_type = False
	try:
		has_gle_custom_type = frappe.db.has_column("GL Entry", "custom_type")
	except Exception:
		pass
	try:
		has_acc_custom_cost_type = frappe.db.has_column("Account", "custom_cost_type")
	except Exception:
		pass

	effective_type_expr = "COALESCE(NULLIF(gl.custom_type, ''), acc.custom_cost_type)" if (has_gle_custom_type and has_acc_custom_cost_type) else (
		"gl.custom_type" if has_gle_custom_type else ("acc.custom_cost_type" if has_acc_custom_cost_type else "''")
	)

	exclude_cond = ""
	if exclude_accounts:
		escaped = ", ".join([frappe.db.escape(a) for a in exclude_accounts])
		exclude_cond = f"AND gl.account NOT IN ({escaped})"

	query = f"""
		SELECT
			{effective_type_expr} as cost_type,
			SUM(gl.debit) as total_debit,
			SUM(gl.credit) as total_credit
		FROM
			`tabGL Entry` gl
		LEFT JOIN
			`tabAccount` acc ON gl.account = acc.name
		WHERE
			gl.company = %s
			AND gl.posting_date BETWEEN %s AND %s
			AND gl.is_cancelled = 0
			AND {effective_type_expr} IN ('Direct Income', 'Indirect Income', 'Distribution costs', 'Administrative expenses', 'Other expenses')
			AND {effective_type_expr} NOT IN ('Direct Cost', 'Indirect Cost', 'Purchases')
			{exclude_cond}
		GROUP BY
			cost_type
	"""

	entries = frappe.db.sql(query, (company, from_date, to_date), as_dict=1)
	totals = {}
	for r in entries:
		t = r.get("cost_type")
		if not t:
			continue
		if t in ["Direct Income", "Indirect Income"]:
			totals[t] = flt(r.get("total_credit")) - flt(r.get("total_debit"))
		else:
			totals[t] = flt(r.get("total_debit")) - flt(r.get("total_credit"))

	return totals


def get_gl_cost_of_sales(company, from_date, to_date):
	"""
	Calculates Cost of Sales for Profit and Loss directly from GL accounts (Cost of Goods Sold / Cost of Sales).
	Production entries (Direct Cost, Indirect Cost) are excluded since they belong to the Cost of Sales report.
	"""
	if not company:
		return 0.0

	res = frappe.db.sql("""
		SELECT SUM(gl.debit - gl.credit) as balance
		FROM `tabGL Entry` gl
		INNER JOIN `tabAccount` acc ON gl.account = acc.name
		WHERE gl.company = %s
		  AND gl.posting_date BETWEEN %s AND %s
		  AND gl.is_cancelled = 0
		  AND (
		      acc.account_type = 'Cost of Goods Sold'
		      OR LOWER(acc.name) LIKE '%%cost of sales%%'
		      OR LOWER(acc.name) LIKE '%%cost of goods sold%%'
		  )
	""", (company, from_date, to_date), as_dict=1)

	if res and res[0].balance:
		return abs(flt(res[0].balance))
	return 0.0


def build_profit_loss_data(company, from_date, to_date, prev_from_date, prev_to_date, compare_prev, show_inflation, inflation_factor_curr, inflation_factor_prev, currency, company_title):
	gl_map_curr = get_gl_entries_by_account(company, from_date, to_date)
	gl_map_prev = get_gl_entries_by_account(company, prev_from_date, prev_to_date) if compare_prev else {}

	cos_accounts = get_cost_of_sales_accounts(company)

	# Strictly remove all production, direct cost, and indirect cost accounts from GL entries
	for a in list(gl_map_curr.keys()):
		if a in cos_accounts or gl_map_curr[a].get("account") in cos_accounts:
			gl_map_curr.pop(a, None)

	for a in list(gl_map_prev.keys()):
		if a in cos_accounts or gl_map_prev[a].get("account") in cos_accounts:
			gl_map_prev.pop(a, None)

	# Fetch General Ledger classified totals (excluding all production/direct/indirect cost accounts)
	gl_totals_curr = get_gl_classified_totals(company, from_date, to_date, exclude_accounts=cos_accounts)
	gl_totals_prev = get_gl_classified_totals(company, prev_from_date, prev_to_date, exclude_accounts=cos_accounts) if compare_prev else {}

	# Helper to sum balances by custom_cost_type (strictly excluding Direct Cost and Indirect Cost)
	def get_classified_total(cost_type, gl_map):
		tot = 0.0
		for acc, row in gl_map.items():
			if acc in cos_accounts or row.get("account") in cos_accounts:
				continue
			if row.get("custom_cost_type") == cost_type:
				tot += flt(row.get("balance"))
		return tot

	# 1. Note 12: Revenue (Direct Income)
	rev_curr = gl_totals_curr.get("Direct Income", 0.0)
	rev_prev = gl_totals_prev.get("Direct Income", 0.0)
	for acc, row in gl_map_curr.items():
		r_type = (row.get("root_type") or "").lower()
		c_type = row.get("custom_cost_type") or ""
		acc_name = (row.get("account_name") or "").lower()
		if c_type == "Direct Income" or (not c_type and r_type == "income" and any(k in acc_name for k in ["sales", "direct income", "revenue"])):
			bal = flt(row.total_credit) - flt(row.total_debit)
			if rev_curr == 0.0:
				rev_curr += bal
	for acc, row in gl_map_prev.items():
		r_type = (row.get("root_type") or "").lower()
		c_type = row.get("custom_cost_type") or ""
		acc_name = (row.get("account_name") or "").lower()
		if c_type == "Direct Income" or (not c_type and r_type == "income" and any(k in acc_name for k in ["sales", "direct income", "revenue"])):
			bal = flt(row.total_credit) - flt(row.total_debit)
			if rev_prev == 0.0:
				rev_prev += bal

	# 2. Note 19: Cost of sales (From Cost of Sales calculations / GL COGS)
	cos_curr = get_gl_cost_of_sales(company, from_date, to_date)
	if cos_curr == 0.0:
		cos_curr = query_account_balance(company, ["cost of goods sold", "cost of sales", "cogs"], gl_map_curr, exclude_accounts=cos_accounts)

	cos_prev = 0.0
	if compare_prev:
		cos_prev = get_gl_cost_of_sales(company, prev_from_date, prev_to_date)
		if cos_prev == 0.0:
			cos_prev = query_account_balance(company, ["cost of goods sold", "cost of sales", "cogs"], gl_map_prev, exclude_accounts=cos_accounts)

	# Gross Profit
	gp_curr = rev_curr - cos_curr
	gp_prev = rev_prev - cos_prev

	# 3. Note 13: Other income (Indirect Income)
	other_inc_curr = gl_totals_curr.get("Indirect Income", 0.0)
	other_inc_prev = gl_totals_prev.get("Indirect Income", 0.0)
	for acc, row in gl_map_curr.items():
		r_type = (row.get("root_type") or "").lower()
		c_type = row.get("custom_cost_type") or ""
		acc_name = (row.get("account_name") or "").lower()
		if c_type == "Indirect Income" or (not c_type and r_type == "income" and not any(k in acc_name for k in ["sales", "direct income", "revenue"])):
			bal = flt(row.total_credit) - flt(row.total_debit)
			if other_inc_curr == 0.0:
				other_inc_curr += bal
	for acc, row in gl_map_prev.items():
		r_type = (row.get("root_type") or "").lower()
		c_type = row.get("custom_cost_type") or ""
		acc_name = (row.get("account_name") or "").lower()
		if c_type == "Indirect Income" or (not c_type and r_type == "income" and not any(k in acc_name for k in ["sales", "direct income", "revenue"])):
			bal = flt(row.total_credit) - flt(row.total_debit)
			if other_inc_prev == 0.0:
				other_inc_prev += bal

	# Total Income
	total_inc_curr = gp_curr + other_inc_curr
	total_inc_prev = gp_prev + other_inc_prev

	# 4. Note 16: Distribution costs (Direct and Indirect costs strictly filtered out)
	dist_curr = gl_totals_curr.get("Distribution costs", 0.0)
	dist_prev = gl_totals_prev.get("Distribution costs", 0.0)
	if dist_curr == 0.0:
		dist_curr = get_classified_total("Distribution costs", gl_map_curr)
		if dist_curr == 0.0:
			dist_curr = query_account_balance(company, ["distribution", "freight", "forwarding", "delivery", "selling", "marketing", "carriage outward"], gl_map_curr, exclude_accounts=cos_accounts)
	if dist_prev == 0.0 and compare_prev:
		dist_prev = get_classified_total("Distribution costs", gl_map_prev)
		if dist_prev == 0.0:
			dist_prev = query_account_balance(company, ["distribution", "freight", "forwarding", "delivery", "selling", "marketing", "carriage outward"], gl_map_prev, exclude_accounts=cos_accounts)

	# 5. Note 15: Administrative expenses (Direct and Indirect costs strictly filtered out)
	admin_curr = gl_totals_curr.get("Administrative expenses", 0.0)
	admin_prev = gl_totals_prev.get("Administrative expenses", 0.0)
	if admin_curr == 0.0:
		admin_curr = get_classified_total("Administrative expenses", gl_map_curr)
		if admin_curr == 0.0:
			admin_curr = query_account_balance(company, ["administrative", "admin", "office", "stationery", "legal", "audit"], gl_map_curr, exclude_accounts=cos_accounts)
	if admin_prev == 0.0 and compare_prev:
		admin_prev = get_classified_total("Administrative expenses", gl_map_prev)
		if admin_prev == 0.0:
			admin_prev = query_account_balance(company, ["administrative", "admin", "office", "stationery", "legal", "audit"], gl_map_prev, exclude_accounts=cos_accounts)

	# 6. Note 17: Other expenses (Direct and Indirect costs strictly filtered out)
	other_exp_curr = gl_totals_curr.get("Other expenses", 0.0)
	other_exp_prev = gl_totals_prev.get("Other expenses", 0.0)
	if other_exp_curr == 0.0:
		other_exp_curr = get_classified_total("Other expenses", gl_map_curr)
		if other_exp_curr == 0.0:
			other_exp_curr = query_account_balance(company, ["other expense", "miscellaneous", "entertainment"], gl_map_curr, exclude_accounts=cos_accounts)
	if other_exp_prev == 0.0 and compare_prev:
		other_exp_prev = get_classified_total("Other expenses", gl_map_prev)
		if other_exp_prev == 0.0:
			other_exp_prev = query_account_balance(company, ["other expense", "miscellaneous", "entertainment"], gl_map_prev, exclude_accounts=cos_accounts)

	# Total expenses
	total_exp_curr = dist_curr + admin_curr + other_exp_curr
	total_exp_prev = dist_prev + admin_prev + other_exp_prev

	# 7. Profit / loss on net monetary position (IAS 29 monetary adjustment)
	monetary_pos_curr = query_account_balance(company, ["monetary gain", "monetary loss", "exchange gain/loss", "gain/loss on monetary"], gl_map_curr)
	monetary_pos_prev = query_account_balance(company, ["monetary gain", "monetary loss", "exchange gain/loss", "gain/loss on monetary"], gl_map_prev) if compare_prev else 0.0

	# Net profit / loss before tax
	net_before_tax_curr = total_inc_curr - total_exp_curr - monetary_pos_curr
	net_before_tax_prev = total_inc_prev - total_exp_prev - monetary_pos_prev

	# 8. Note 18: Tax expense / deferred tax
	tax_curr = query_account_balance(company, ["tax expense", "deferred tax", "income tax"], gl_map_curr)
	tax_prev = query_account_balance(company, ["tax expense", "deferred tax", "income tax"], gl_map_prev) if compare_prev else 0.0

	# Net profit / loss after tax
	net_after_tax_curr = net_before_tax_curr - tax_curr
	net_after_tax_prev = net_before_tax_prev - tax_prev

	data = []

	def add_statement_row(item_name, note="", hist_c=None, hist_p=None, is_bold=False, is_heading=False, is_less=False, is_final=False, summary_key=None):
		if not item_name:
			data.append({})
			return

		c_val = flt(hist_c) if hist_c is not None else 0.0
		p_val = flt(hist_p) if hist_p is not None else 0.0

		row = {
			"item_name": item_name,
			"note": str(note) if note else "",
			"historical_curr": c_val,
			"currency": currency,
			"company_title": company_title,
			"is_bold": 1 if is_bold else 0,
			"is_heading": 1 if is_heading else 0,
			"is_less": 1 if is_less else 0,
			"is_final": 1 if is_final else 0,
		}
		if compare_prev:
			row["historical_prev"] = p_val
		if show_inflation:
			row["inflation_curr"] = round(c_val * inflation_factor_curr, 2)
			if compare_prev:
				row["inflation_prev"] = round(p_val * inflation_factor_prev, 2)
		if summary_key:
			row["summary_key"] = summary_key
		data.append(row)

	# Build rows matching financial statements
	add_statement_row("Revenue", note="12", hist_c=rev_curr, hist_p=rev_prev, summary_key=_("Revenue"))
	add_statement_row("Cost of sales", note="19", hist_c=cos_curr, hist_p=cos_prev, is_less=True, summary_key=_("Cost of Sales"))
	gp_label = "Gross profit" if gp_curr >= 0 else "Gross loss"
	add_statement_row(gp_label, hist_c=gp_curr, hist_p=gp_prev, is_bold=True, summary_key=_("Gross Profit"))

	add_statement_row("", None, None)
	add_statement_row("Other income", note="13", hist_c=other_inc_curr, hist_p=other_inc_prev)
	add_statement_row("Total income", hist_c=total_inc_curr, hist_p=total_inc_prev, is_bold=True, summary_key=_("Total Income"))

	add_statement_row("", None, None)
	add_statement_row("Expenses", is_bold=True, is_heading=True)
	add_statement_row("    Distribution costs", note="16", hist_c=dist_curr, hist_p=dist_prev)
	add_statement_row("    Administrative expenses", note="15", hist_c=admin_curr, hist_p=admin_prev)
	add_statement_row("    Other expenses", note="17", hist_c=other_exp_curr, hist_p=other_exp_prev)
	add_statement_row("Total expenses", hist_c=total_exp_curr, hist_p=total_exp_prev, is_bold=True, summary_key=_("Total Expenses"))

	add_statement_row("", None, None)
	add_statement_row("Profit/ loss on net monetary position", hist_c=monetary_pos_curr, hist_p=monetary_pos_prev, is_less=(monetary_pos_curr > 0))

	add_statement_row("", None, None)
	nbt_label = "Net profit before tax" if net_before_tax_curr >= 0 else "Net loss before tax"
	add_statement_row(nbt_label, hist_c=net_before_tax_curr, hist_p=net_before_tax_prev, is_bold=True, summary_key=_("Net Profit/Loss Before Tax"))

	add_statement_row("", None, None)
	add_statement_row("Tax expense decrease in deferred tax liability", note="18", hist_c=tax_curr, hist_p=tax_prev)

	add_statement_row("", None, None)
	nat_label = "Net profit after tax" if net_after_tax_curr >= 0 else "Net loss after tax"
	add_statement_row(nat_label, hist_c=net_after_tax_curr, hist_p=net_after_tax_prev, is_bold=True, is_final=True, summary_key=_("Net Profit/Loss After Tax"))

	return data
