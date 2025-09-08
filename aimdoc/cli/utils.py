"""
CLI utilities and helpers
"""

import re
from urllib.parse import urlparse
from pathlib import Path
from rich.console import Console

console = Console()

def extract_domain_name(url: str) -> str:
    """Extract a clean domain name from URL for use as project name"""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # Remove www prefix if present
        domain = re.sub(r'^www\.', '', domain)
        
        # Remove common TLD extensions for cleaner names
        domain = re.sub(r'\.(com|org|net|io|dev|tech|ai)$', '', domain)
        
        # Convert to a safe filesystem name
        domain = re.sub(r'[^a-zA-Z0-9\-_]', '_', domain)
        
        return domain or "docs"
    except Exception:
        return "docs"

def is_valid_url(url: str) -> bool:
    """Check if URL is valid"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False

def ensure_output_dir(output_dir: str) -> Path:
    """Ensure output directory exists and is writable"""
    path = Path(output_dir).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path