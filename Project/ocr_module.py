import requests
import os

OCR_API_KEY = "K85109652988957"  
OCR_URL = "https://api.ocr.space/parse/image"


def extract_text(file_path):
    """Send file (image or PDF) to OCR.space and return parsed text.

    The free tier allows PDFs (up to 3 pages) so there is no need to
    split the document into individual images first.
    """

    if not os.path.exists(file_path):
        raise FileNotFoundError("File not found.")

    # Build request parameters. Do NOT send invalid parameters like 'isPdf'.
    data = {
        "apikey": OCR_API_KEY,
        "language": "eng",
        "isOverlayRequired": False,
    }

    # Hint to API for PDF files
    if file_path.lower().endswith('.pdf'):
        data["filetype"] = "pdf"

    with open(file_path, 'rb') as f:
        try:
            response = requests.post(
                OCR_URL,
                files={"file": f},
                data=data,
                timeout=60,
            )
        except requests.RequestException as re:
            raise Exception(f"OCR request failed: {re}")

    # Ensure we got JSON back
    try:
        result = response.json()
    except ValueError:
        raise Exception(f"Unexpected OCR response (non-JSON): {response.status_code} {response.text}")
    print(result)
    if result.get("IsErroredOnProcessing"):
        raise Exception("OCR Error: " + str(result.get("ErrorMessage")))

    try:
        parsed = result.get("ParsedResults") or []
        # combine text from all pages (each result element corresponds to a page)
        texts = [p.get("ParsedText", "") for p in parsed]
        return "\n".join(texts).strip()
    except (KeyError, IndexError):
        return ""