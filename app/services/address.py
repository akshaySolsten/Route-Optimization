import re


def normalize_to_single_line(text: str) -> str:
    if not text:
        return ""
    flattened = re.sub(r"[\r\n\t]+", " ", text)
    return re.sub(r"\s+", " ", flattened).strip()


def clean_address_for_geocoding(text: str) -> str:
    if not text:
        return ""

    text = text.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s*,\s*", ", ", text)
    text = re.sub(r"\s*;\s*", "; ", text)
    text = re.sub(r",{2,}", ",", text)
    text = re.sub(r"-{2,}", "-", text)
    text = re.sub(r"\.{2,}", ".", text)

    parts = [p.strip() for p in text.split(",") if p.strip()]
    text = ", ".join(parts)
    text = text.strip(" ,.-;")
    return re.sub(r"\s+", " ", text).strip()


def format_geocode_address(receiver_name: str, receiver_address: str) -> str:
    name = str(receiver_name or "").strip()
    addr = str(receiver_address or "").strip()

    if name and addr:
        pattern = r"\b" + re.escape(name) + r"\b"
        if re.search(pattern, addr, re.IGNORECASE):
            return addr
        return f"{name}, {addr}"

    return addr or name
