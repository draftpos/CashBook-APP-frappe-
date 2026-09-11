# Cash Book App

Custom Cash Book and Financial Reporting extension for Frappe & ERPNext.

---

## Features
- **Line-Level Transaction Classification (`Type`)**: Classify transaction lines as Direct Cost, Indirect Cost, Direct Income, Indirect Income, Distribution costs, Administrative expenses, Other expenses, or Purchases.
- **Cash Book to Journal Entry Sync**: Automatically passes line types from Cash Book Entry rows to Journal Entry Account rows.
- **Direct Journal Entry Desk UI**: Select and adjust Type per account row directly on the Journal Entry grid, with auto-fetch from Account master defaults.
- **General Ledger Propagation & Filtering**: Stamps Type directly onto `GL Entry` records and provides a Type filter & column on the General Ledger report.
- **General Ledger-Powered Cost of Sales Report**: Calculates Note 19 Cost of Sales (Direct Costs, Factory Overheads, Purchases) directly from GL Entry records.
- **Statement of Profit or Loss and Comprehensive Income**: Calculates Revenue, Other Income, and Operating Expenses directly from GL Entry records with strict exclusion of Cost of Sales entries.

---

## Detailed Documentation
For complete technical documentation, architecture diagrams, and field mappings, please refer to:
👉 **[`DOCUMENTATION.md`](DOCUMENTATION.md)**

---

## Installation

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO
bench --site [site-name] install-app cash_book
bench --site [site-name] migrate
```

---

## License
MIT
