"""Persoonlijke kolomkoppelingen; uitsluitend per bezoekerssessie."""

import json

from converter import FIELDS

PROFILE_KEY = "supplier_profiles"
MAX_PROFILE_BYTES = 256 * 1024
MAX_PROFILES = 100


def validate_profiles(profiles):
    if not isinstance(profiles, dict) or len(profiles) > MAX_PROFILES:
        raise ValueError("Gebruik een instellingenbestand met maximaal 100 leveranciers.")
    result = {}
    for name, mapping in profiles.items():
        if not isinstance(name, str) or not name.strip() or len(name) > 80:
            raise ValueError("Een leveranciersnaam moet 1 tot 80 tekens bevatten.")
        if not isinstance(mapping, dict):
            raise ValueError("Elke leverancier moet vier kolomkoppelingen bevatten.")
        columns = [mapping.get(field) for field in FIELDS]
        if any(not isinstance(column, str) or not column.strip() for column in columns):
            raise ValueError("Koppel voor iedere leverancier alle vier velden.")
        if len(set(columns)) != len(FIELDS):
            raise ValueError("Kies voor ieder veld een verschillende kolom.")
        result[name] = dict(zip(FIELDS, columns))
    return result


def get_profiles(state):
    if PROFILE_KEY not in state:
        state[PROFILE_KEY] = {}
    return state[PROFILE_KEY]


def save_profile(state, name, mapping, overwrite=False):
    name = name.strip()
    current = get_profiles(state)
    if name in current and not overwrite:
        raise ValueError("Bevestig eerst dat je deze leverancier wilt vervangen.")
    state[PROFILE_KEY] = validate_profiles({**current, name: mapping})


def decode_profiles(data):
    if len(data) > MAX_PROFILE_BYTES:
        raise ValueError("Het instellingenbestand is te groot (maximaal 256 KB).")
    try:
        payload = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        raise ValueError("Dit is geen geldig instellingenbestand in UTF-8.") from error
    return validate_profiles(payload)


def encode_profiles(profiles):
    return json.dumps(validate_profiles(profiles), ensure_ascii=False, indent=2).encode("utf-8")
