import requests
import re
import os
import logging
from pathlib import Path
from urllib.parse import urlparse, unquote
import mimetypes
import uuid
import shutil

logger = logging.getLogger(__name__)

def get_filename_from_cd(cd):
    """Get filename from content-disposition"""
    if not cd:
        return None
    fname = re.findall('filename=(.+)', cd)
    if len(fname) == 0:
        return None
    return fname[0].strip('"')

def get_extension_from_mime(mime_type):
    return mimetypes.guess_extension(mime_type) or ".bin"

def download_file(url, output_dir):
    """
    Download file from URL handling common cloud providers.
    Returns (file_path, filename, mime_type, size)
    """
    session = requests.Session()
    download_url = url
    provider = "GENERIC"
    
    domain = urlparse(url).netloc.lower()
    
    # Google Drive Logic
    if "drive.google.com" in domain:
        provider = "GOOGLE_DRIVE"
        file_id = None
        patterns = [
            r'/file/d/([^/]+)',
            r'id=([^&]+)',
            r'/open\?id=([^&]+)'
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                file_id = match.group(1)
                break
        
        if file_id:
            download_url = "https://docs.google.com/uc?export=download"
            params = {'id': file_id}
            response = session.get(download_url, params=params, stream=True)
            
            # recursive confirm token check
            token = get_confirm_token(response)
            if token:
                params = {'id': file_id, 'confirm': token}
                response = session.get(download_url, params=params, stream=True)
        else:
            # Fallback to direct GET if ID not found
            response = session.get(url, stream=True)
            
    # OneDrive Logic
    elif "1drv.ms" in domain or "onedrive.live.com" in domain or "sharepoint.com" in domain:
        provider = "ONEDRIVE"
        # Convert to download link
        if "1drv.ms" in domain:
            # Expand shortened link
            resp = session.head(url, allow_redirects=True)
            download_url = resp.url
        
        # Append download=1
        if "?" in download_url:
             if "download=1" not in download_url:
                download_url += "&download=1"
        else:
            download_url += "?download=1"
            
        response = session.get(download_url, stream=True)
    
    # Generic Logic
    else:
        response = session.get(url, stream=True)
    
    response.raise_for_status()

    # Determine filename/extension
    content_disposition = response.headers.get('content-disposition')
    filename = get_filename_from_cd(content_disposition)
    
    content_type = response.headers.get('content-type', '').split(';')[0].strip()
    
    if not filename:
        # Try from URL
        path = urlparse(unquote(response.url)).path
        filename = os.path.basename(path)
        if not filename or '.' not in filename:
            ext = get_extension_from_mime(content_type)
            filename = f"downloaded_resource{ext}"
    
    # Validate filename to be safe
    filename = re.sub(r'[\\/*?:"<>|]', "", filename)
    name, ext = os.path.splitext(filename)
    if not ext:
        ext = get_extension_from_mime(content_type)
        filename = f"{name}{ext}"
        
    unique_filename = f"{uuid.uuid4()}{ext}"
    final_path = output_dir / unique_filename

    total_size = 0
    with open(final_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
                total_size += len(chunk)
                
    return str(final_path), filename, content_type, total_size

def get_confirm_token(response):
    for key, value in response.cookies.items():
        if key.startswith('download_warning'):
            return value
    return None

if __name__ == "__main__":
    # Test
    # download_file("https://docs.google.com/uc?id=...", Path("."))
    pass
