"""Keep only the current processing results in one visitor's session."""

CACHE_KEY = "supplier_processing_v1"


def result_signature(state, slot):
    entry = state.get(CACHE_KEY, {}).get(slot)
    return entry["signature"] if entry is not None else None


def reuse_result(state, slot, signature, calculate):
    results = state.setdefault(CACHE_KEY, {})
    entry = results.get(slot)
    if entry is not None and entry["signature"] == signature:
        return entry["value"]
    # Replace the previous value; never accumulate historical uploads.
    results.pop(slot, None)
    value = calculate()
    results[slot] = {"signature": signature, "value": value}
    return value


def discard_results(state, *slots):
    results = state.get(CACHE_KEY, {})
    for slot in slots:
        results.pop(slot, None)


def discard_source(state, side):
    discard_results(state, f"sheets_{side}", f"frame_{side}",
                    f"products_{side}", "comparison")
