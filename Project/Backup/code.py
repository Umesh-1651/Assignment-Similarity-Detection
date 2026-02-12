import requests
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

def extract_text(image_path, api_key):
    # CORRECT ENDPOINT: Must end in /parse/image
    api_url = 'https://api.ocr.space/parse/image'
    
    payload = {
        'apikey': api_key,
        'OCREngine': 3,
        'language': 'eng',
    }
    
    try:
        with open(image_path, 'rb') as f:
            # Send file using the key 'file' as required by the API
            files = {'file': (image_path, f, 'image/jpeg')}
            response = requests.post(api_url, files=files, data=payload)
        
        if response.status_code != 200:
            print(f"Server Error: {response.status_code}")
            return ""

        result = response.json()
        if result.get('ParsedResults'):
            # Return text or empty string if no text found
            return result['ParsedResults'][0].get('ParsedText', "").strip()
        
        print(f"API Error: {result.get('ErrorMessage')}")
        return ""

    except Exception as e:
        print(f"Extraction Exception: {e}")
        return ""

def check_similarity(text1, text2):
    # Safety check: If either text is empty, avoid the ValueError crash
    if not text1.strip() or not text2.strip():
        print("Warning: One or both documents are empty. Cannot calculate similarity.")
        return 0.0
    
    vectorizer = TfidfVectorizer().fit_transform([text1, text2])
    vectors = vectorizer.toarray()
    return cosine_similarity(vectors)[0][1]

# Execution
API_KEY = 'K85109652988957'
student_a_text = extract_text('studentA.jpeg', API_KEY)
student_b_text = extract_text('studentA.jpeg', API_KEY)

# Display extracted text for debugging
print(f"Student A Text: {student_a_text[:50]}...")
print(f"Student B Text: {student_b_text[:50]}...")

score = check_similarity(student_a_text, student_b_text)
print(f"\nSimilarity Score: {score:.2f}")

if score > 0.85:
    print("RESULT: CRITICAL - Direct copying highly likely.")
elif score > 0.60:
    print("RESULT: WARNING - Phrasing is very similar.")
else:
    print("RESULT: PASS - Content appears original.")
