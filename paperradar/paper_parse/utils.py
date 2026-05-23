"""
This file is adapted from the original implementation by Jiong Wang (PJLAB).
"""

import hashlib
import os
import shutil
import time
import uuid
import zipfile
import fitz
import requests
from typing import List

CROSSREF_HEADERS = {"mailto": os.getenv("CROSSREF_MAILTO", "")}


def pdf_to_unique_uuid(pdf_path, namespace=uuid.NAMESPACE_OID):
    """Generate a unique and stable UUID identifier for a PDF (same PDF returns the same UUID).

    :param pdf_path: Path to the PDF file (local file)
    :param namespace: UUID namespace (fixed value to ensure consistent conversion rules)
    :return: Standard UUID string (e.g., "b56254e7-88ab-4301-a7ae-dada0ac8e063")
    """

    # Step 1: Calculate file hash (SHA-256) of the PDF content
    def calculate_file_hash(file_path, chunk_size=1024 * 1024):
        """Read file in chunks & calculate SHA-256 hash
        (avoids high memory use for large files)."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(chunk_size):
                sha256.update(chunk)
        return sha256.hexdigest()  # Returns 64 char hex string of hash

    # Check if file exists
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file does not exist: {pdf_path}")

    # Calculate PDF content hash (content being the same will yield the same hash)
    file_hash = calculate_file_hash(pdf_path)

    # Step 2: Convert the stable hash string to a UUIDv5 identifier.
    unique_uuid = uuid.uuid5(namespace, file_hash)

    # Return as standard UUID string (with hyphens)
    return str(unique_uuid)


def extract_title_from_metadata(pdf_path):
    """Extract the title and metadata from a PDF file.

    Args:
        pdf_path (str): The path to the PDF file.

    Returns:
        tuple: A tuple containing the title (str) and metadata (dict) of the PDF.
    """
    doc = fitz.open(pdf_path)
    # Possible keys: 'format', 'title', 'author', 'subject', 'keywords', 'creator',
    # 'producer', 'creationDate', 'modDate', 'trapped', 'encryption'
    metadata = doc.metadata
    title = metadata.get("title", "").strip()
    doc.close()
    return title, metadata


def get_references_from_crossref(doi):
    """Retrieve references for a given DOI from the CrossRef API.

    Args:
        doi (str): The DOI of the resource to fetch references for.

    Returns:
        list or str: A list of references if found, otherwise a message indicating no references or an error.

    Raises:
        requests.exceptions.HTTPError: If an HTTP error occurs during the API request.
        Exception: For other exceptions during the API request.
    """
    url = f"https://api.crossref.org/works/{doi}"
    headers = {"Accept": "application/json"}

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()["message"]

        references = data.get("reference", [])
        if not references:
            return f"No references found for scholar [{doi}] [Not Provided]"

        ref_list = []
        for idx, ref in enumerate(references):
            ref_info = {
                "index": idx,
                "reference DOI": ref.get("DOI", ""),
                "title": ref.get("title", [""])[0],
                "author": ref.get("author", ""),
                "container": ref.get("container-title", [""])[0],
                "Year": ref.get("issued", {}).get("date-parts", [[]])[0][0] or None,
            }
            ref_list.append(ref_info)
        return ref_list
    except requests.exceptions.HTTPError as e:
        if response.status_code == 404:
            return f"DOI not exist or not included by CrossRef: {doi}"
        return f"HTTP Error: {e}"
    except Exception as e:
        return f"Search failed: {e}"


def safe_extract_zip(zip_path: str, extract_dir: str) -> None:
    """Safely extract a zip file to prevent Zip Slip vulnerability.

    Extracts the contents of a zip file to the specified directory. If the directory
    already exists, files with the same name will be overwritten (default behavior).

    Args:
        zip_path (str): The path to the zip file to be extracted.
        extract_dir (str): The directory where the contents of the zip file will be extracted.

    Returns:
        Tuple[str, str]: The path to the zip file and the extraction directory.
    """
    os.makedirs(extract_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as z:
        for member in z.namelist():
            member_path = os.path.normpath(member)
            # Ignore absolute paths or members containing references to parent directories
            if member_path.startswith("..") or os.path.isabs(member_path):
                continue
            dest_path = os.path.abspath(os.path.join(extract_dir, member_path))
            if not dest_path.startswith(os.path.abspath(extract_dir) + os.sep) and os.path.abspath(
                dest_path
            ) != os.path.abspath(extract_dir):
                continue
            # If it's a directory, ensure it exists; else, write the file
            if member.endswith("/"):
                os.makedirs(dest_path, exist_ok=True)
            else:
                parent = os.path.dirname(dest_path)
                os.makedirs(parent, exist_ok=True)
                with z.open(member) as source, open(dest_path, "wb") as target:
                    shutil.copyfileobj(source, target)
    return zip_path, extract_dir


def extract_zip_to_named_folder(zip_path: str, output_parent: str = None, logger=None) -> str:
    """Extract the contents of a ZIP file to a named folder within the specified parent directory.

    Args:
        zip_path (str): The path to the ZIP file to be extracted.
        output_parent (str, optional): The parent directory where the extracted folder will be created.
            Defaults to the directory containing `zip_path`.
        logger (optional): A logger instance for logging warnings. If not provided, warnings are printed to the console.

    Returns:
        str: The path to the directory where the ZIP file was extracted.
    """
    output_parent = output_parent if output_parent is not None else os.path.dirname(output_parent)
    base = os.path.basename(zip_path)
    name, ext = os.path.splitext(base)
    if not ext.lower() == ".zip":
        if logger is not None:
            logger.warning("File does not appear to be a .zip: %s (Still trying to extract)", zip_path)
        else:
            print("File does not appear to be a .zip: %s (Still trying to extract)", zip_path)
    dest = os.path.join(output_parent, name)
    safe_extract_zip(zip_path, dest)
    return dest


def doi2dict(doi: str, max_try=1):
    """Fetch metadata for a given DOI from the CrossRef API.

    Args:
        doi (str): The DOI of the resource to fetch metadata for.
        max_try (int): The maximum number of retry attempts in case of failure.

    Returns:
        dict or None: The metadata dictionary if the request is successful, otherwise None.
    """
    url = f"https://api.crossref.org/works/{doi}"

    for try_idx in range(max_try):
        try:
            response = requests.get(url, CROSSREF_HEADERS)
            response.raise_for_status()
            data = response.json()
            return data["message"]
        except requests.exceptions.RequestException:
            if try_idx < (max_try - 1):
                time.sleep(0.2)

    return None


def doi2html(doi: str, max_try=3):
    """Fetch the HTML content of a DOI URL.

    Args:
        doi (str): The DOI of the resource to fetch.
        max_try (int): The maximum number of retry attempts in case of failure.

    Returns:
        str or None: The HTML content of the DOI URL if successful, otherwise None.
    """
    url = f"https://doi.org/{doi}"

    for try_idx in range(max_try):
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException:
            if try_idx < (max_try - 1):
                time.sleep(0.2)

    return None


def doi2journal(doi: str, max_try=1):
    """Retrieve the journal name associated with a given DOI.

    Args:
        doi (str): The DOI of the resource.
        max_try (int): The maximum number of retry attempts in case of failure.

    Returns:
        str: The name of the journal if found, otherwise "None".
    """
    data = doi2dict(doi, max_try)
    if isinstance(data, dict) and isinstance(data["container-title"], list) and len(data["container-title"]) > 0:
        journal_name = data["container-title"][0]
        return journal_name
    return "None"


def doi2cite(doi: str, max_try=1):
    """Retrieve the citation count for a given DOI.

    Args:
        doi (str): The DOI of the resource.
        max_try (int): The maximum number of retry attempts in case of failure.

    Returns:
        int or None: The citation count if successful, otherwise None.
    """
    url = f"https://api.crossref.org/works/{doi}/transform/application/vnd.citationstyles.csl+json"

    for try_idx in range(max_try):
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            return int(data["is-referenced-by-count"])
        except requests.exceptions.RequestException:
            if try_idx < (max_try - 1):
                time.sleep(0.2)

    return None

def validate_pdf_files(pdf_files: List[str], data_dir: str) -> List[str]:
    """Validate that specified PDF files exist in data directory.

    Args:
        pdf_files: List of PDF filenames to validate
        data_dir: Directory containing PDF files

    Returns:
        List of valid PDF file paths

    Raises:
        FileNotFoundError: If any specified PDF doesn't exist
    """
    valid_files = []
    missing_files = []

    for pdf_file in pdf_files:
        # Normalize path
        pdf_path = os.path.join(data_dir, pdf_file)
        if not os.path.exists(pdf_path):
            missing_files.append(pdf_file)
        else:
            valid_files.append(pdf_file)

    if missing_files:
        raise FileNotFoundError(
            f"The following PDF files were not found in {data_dir}:\n" + "\n".join(f"  - {f}" for f in missing_files)
        )

    return valid_files
