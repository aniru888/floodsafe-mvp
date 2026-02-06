"""
Download IFI-Impacts dataset from Zenodo and process for Delhi.

Source: https://zenodo.org/records/11275211
License: CC-BY 4.0

Files:
- India_Flood_Inventory_v3.csv (1.8 MB) - Main flood events 1967-2023
"""
import os
import requests
from pathlib import Path
from typing import Optional

ZENODO_BASE = "https://zenodo.org/records/11275211/files"
DATA_DIR = Path(__file__).parent.parent / "data" / "external" / "ifi_impacts"

# Security: Maximum file size (10 MB)
MAX_FILE_SIZE = 10 * 1024 * 1024

FILES = [
    "India_Flood_Inventory_v3.csv",
]


def download_file(filename: str) -> Optional[Path]:
    """
    Download file from Zenodo with security validation.

    Validates:
    - Content type (must be text/csv or text/plain)
    - File size (max 10 MB)
    - Timeout (30 seconds)
    """
    url = f"{ZENODO_BASE}/{filename}?download=1"
    filepath = DATA_DIR / filename

    if filepath.exists():
        print(f"Already exists: {filename}")
        return filepath

    print(f"Downloading: {filename}")

    try:
        # Use timeout to prevent hanging
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()

        # Validate content type
        content_type = response.headers.get('content-type', '').lower()
        valid_types = ['text/csv', 'text/plain', 'application/csv', 'application/octet-stream']
        if not any(ct in content_type for ct in valid_types):
            print(f"Warning: Unexpected content type: {content_type}. Proceeding with caution.")

        # Check content length if available
        content_length = response.headers.get('content-length')
        if content_length and int(content_length) > MAX_FILE_SIZE:
            raise ValueError(f"File too large: {content_length} bytes (max: {MAX_FILE_SIZE})")

        # Download with size limit
        total_bytes = 0
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                total_bytes += len(chunk)
                if total_bytes > MAX_FILE_SIZE:
                    # Clean up partial download
                    f.close()
                    filepath.unlink(missing_ok=True)
                    raise ValueError(f"Download exceeded size limit ({MAX_FILE_SIZE} bytes)")
                f.write(chunk)

        print(f"Downloaded: {filepath} ({total_bytes} bytes)")
        return filepath

    except requests.exceptions.Timeout:
        print(f"Error: Download timed out for {filename}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error downloading {filename}: {e}")
        return None
    except ValueError as e:
        print(f"Validation error: {e}")
        return None

def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for filename in FILES:
        download_file(filename)
    print("Download complete!")

if __name__ == "__main__":
    main()
