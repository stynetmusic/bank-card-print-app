"""Company / organization settings persistence."""

import json
import logging
import os

from ufprint.paths import get_app_dir

CONFIG_KEYS = ("company_name", "company_address", "company_phone", "company_logo")


def get_config_path():
    return os.path.join(get_app_dir(), "company_config.json")


def load_company_settings():
    config_path = get_config_path()
    empty = {key: "" for key in CONFIG_KEYS}
    if not os.path.exists(config_path):
        empty["company_address"] = "г. Москва, Стахановская 8"
        empty["company_phone"] = "8 (495) 946-21-86"
        return empty
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            "company_name": data.get("company_name", ""),
            "company_address": data.get("company_address", "г. Москва, Стахановская 8"),
            "company_phone": data.get("company_phone", "8 (495) 946-21-86"),
            "company_logo": data.get("company_logo", ""),
        }
    except Exception as exc:
        logging.error(f"Ошибка загрузки конфигурации: {exc}")
        return empty


def save_company_settings(name, address, phone, logo_path):
    data = {
        "company_name": name,
        "company_address": address,
        "company_phone": phone,
        "company_logo": logo_path,
    }
    try:
        with open(get_config_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return True
    except Exception as exc:
        logging.error(f"Ошибка сохранения конфигурации: {exc}")
        return False


def to_org_view(settings):
    """Map storage keys → dialog/org view dict (name/logo_path/address/phone)."""
    settings = settings or {}
    return {
        "name": settings.get("company_name", ""),
        "logo_path": settings.get("company_logo", ""),
        "address": settings.get("company_address", ""),
        "phone": settings.get("company_phone", ""),
    }


def from_org_view(org_data):
    """Map org view dict → storage kwargs for save_company_settings."""
    org_data = org_data or {}
    return {
        "name": org_data.get("name", ""),
        "address": org_data.get("address", ""),
        "phone": org_data.get("phone", ""),
        "logo_path": org_data.get("logo_path", ""),
    }
