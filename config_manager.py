import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')

# NOTE: sheets_csv_url / sheets_spreadsheet_key / sheets_gid are intentionally
# NOT defaulted here. sheets_integration raises an explicit RuntimeError when one
# is missing, instead of silently falling back to an empty value.
DEFAULTS = {
    'sheets_credentials_path': '',
    'sheets_enabled': False,
    'last_sync': None,
}


def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return {**DEFAULTS, **data}
    return dict(DEFAULTS)


def save_config(config: dict):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
