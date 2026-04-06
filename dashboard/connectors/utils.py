import re
import hashlib
from datetime import datetime
from typing import Any, Optional, List

def html_to_plain_text(html: str) -> str:
    """
    Strips HTML tags and decodes common entities, 
    mimicking the JS logic in port_js_connectors/utils.ts.
    """
    # Strip HTML tags
    text = re.sub(r'<[^>]*>', ' ', html)
    # Decode common HTML entities
    entities = {
        '&nbsp;': ' ',
        '&lt;': '<',
        '&gt;': '>',
        '&quot;': '"',
        '&#39;': "'",
        '&amp;': '&',
    }
    for entity, char in entities.items():
        text = text.replace(entity, char)
    
    # Normalize whitespace and trim
    return re.sub(r'\s+', ' ', text).strip()

def compute_content_hash(content: str) -> str:
    """
    Computes SHA-256 hash of content string.
    """
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def parse_tag_date(value: Any) -> Optional[datetime]:
    """
    Parses metadata value as a datetime for tag mapping.
    Returns datetime if valid, None otherwise.
    """
    if not isinstance(value, str):
        return None
    try:
        # Tries ISO format (common for JS Date.toISOString())
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None

def join_tag_array(value: Any) -> Optional[str]:
    """
    Joins array metadata value into a comma-separated string.
    """
    if not isinstance(value, list):
        return None
    
    # Filter non-empty strings and join
    parts = [str(v) for v in value if v is not None]
    return ', '.join(parts) if parts else None
