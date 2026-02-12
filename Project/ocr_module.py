import requests
import os

OCR_API_KEY = "K85109652988957"  
OCR_URL = "https://api.ocr.space/parse/image"


def extract_text_from_image(file_path):


    if not os.path.exists(file_path):
        raise FileNotFoundError("File not found.")

    with open(file_path, 'rb') as file:
        response = requests.post(
            OCR_URL,
            files={"file": file},
            data={
                "apikey": OCR_API_KEY,
                "language": "eng",
                "isOverlayRequired": False
            }
        )

    result = response.json()

    if result.get("IsErroredOnProcessing"):
        raise Exception("OCR Error: " + str(result.get("ErrorMessage")))

    try:
        extracted_text = result["ParsedResults"][0]["ParsedText"]
        return extracted_text.strip()
    except (KeyError, IndexError):
        return ""