"""Utility functions"""
from pathlib import Path
from datetime import datetime
import json


def sanitize_filename(filename: str, max_length: int = 80) -> str:
    """Convert string to safe filename"""
    # Remove or replace unsafe characters
    unsafe_chars = ['<', '>', ':', '"', '|', '?', '*', '/', '\\']
    for char in unsafe_chars:
        filename = filename.replace(char, '_')
    
    # Replace spaces and multiple underscores
    filename = filename.replace(' ', '_')
    while '__' in filename:
        filename = filename.replace('__', '_')
    
    # Trim length and remove leading/trailing underscores
    return filename.strip('_')[:max_length]


def save_json_file(data: dict, filepath: Path, indent: int = 2) -> bool:
    """Save data to JSON file safely"""
    try:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=False, default=str)
        return True
    except Exception as e:
        print(f"Error saving JSON file {filepath}: {e}")
        return False


def load_json_file(filepath: Path) -> dict:
    """Load data from JSON file safely"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading JSON file {filepath}: {e}")
        return {}


def create_timestamp() -> str:
    """Generate consistent timestamp string"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def url_to_filename(url: str) -> str:
    """Convert URL to safe filename"""
    clean = url.replace("https://", "").replace("http://", "")
    clean = clean.replace("/", "_").replace("?", "_").replace("&", "_")
    clean = clean.replace("=", "_").replace("#", "_").replace(":", "_")
    return sanitize_filename(clean)
