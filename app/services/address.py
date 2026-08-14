import re


def normalize_to_single_line(text: str) -> str:
    """Minimal normalization - preserve address structure."""
    if not text:
        return ""
    # Replace all newline/carriage-return/tab variants with a plain space.
    flattened = re.sub(r"[\r\n\t]+", " ", text)
    # Collapse any remaining multi-space runs (double spaces, etc.).
    single_line = re.sub(r"\s+", " ", flattened).strip()
    return single_line

def clean_address_for_geocoding(text: str) -> str:
    """
    MINIMAL cleaning - only handle whitespace and obvious issues.
    Do NOT destroy address structure.
    """
    if not text:
        return ""
    
    # Only clean whitespace and control characters
    text = text.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    text = re.sub(r"\s+", " ", text).strip()
    
    # Remove duplicate commas but KEEP the structure
    text = re.sub(r",\s*,", ",", text)
    
    # No space before comma/semicolon, exactly one space after.
    text = re.sub(r"\s*,\s*", ", ", text)
    text = re.sub(r"\s*;\s*", "; ", text)
    
    # Clean up empty segments (but don't remove too aggressively)
    parts = [p.strip() for p in text.split(",")]
    parts = [p for p in parts if p and p.lower() not in ['', 'n/a', 'na']]
    text = ", ".join(parts)
    
    return text

def extract_pincode(address: str) -> str:
    """Extract 6-digit pincode from address."""
    if not address:
        return None
    match = re.search(r'\b\d{6}\b', address)
    return match.group(0) if match else None


def format_geocode_address(receiver_name: str, receiver_address: str) -> str:
    name = str(receiver_name or "").strip()
    addr = str(receiver_address or "").strip()

    if name and addr:
        pattern = r"\b" + re.escape(name) + r"\b"
        if re.search(pattern, addr, re.IGNORECASE):
            return addr
        return f"{name}, {addr}"

    return addr or name
