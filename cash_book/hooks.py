app_name = "cash_book"
app_title = "Cah Book"
app_publisher = "munyaradzi chirove"
app_description = "custom cash book"
app_email = "chirovemunyaradzi@gmail.com"
app_license = "mit"

app_include_js = "cash_book.bundle.js"

doctype_js = {"Journal Entry": "public/js/journal_entry_custom.js"}

override_whitelisted_methods = {
    "frappe.desk.query_report.get_script": "cash_book.cah_book.report_overrides.custom_get_script"
}

after_install = "cash_book.setup_custom_fields.setup_all_custom_fields"

fixtures = [
    {
        "dt": "Custom Field",
        "filters": [
            ["dt", "in", ["Cash Book Entry", "Cash Book Account", "Journal Entry", "Journal Entry Account", "GL Entry", "Account"]]
        ]
    },
    {
        "dt": "Client Script",
        "filters": [
            ["dt", "in", ["Cash Book Entry", "Cash Book Account"]]
        ]
    }
]

doc_events = {
    "*": {
        "before_print": "cash_book.patches.before_print_patch.safe_before_print"
    },
    "GL Entry": {
        "before_insert": "cash_book.cah_book.api.set_gl_entry_type"
    }
}

after_migrate = "cash_book.setup_custom_fields.setup_all_custom_fields"
