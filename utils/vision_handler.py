import requests

def extract_text_from_image(image_path):
    api_key = 'K88148553688957',  # Replace this with your actual API key from ocr.space

    with open(image_path, 'rb') as image_file:
        response = requests.post(
            'https://api.ocr.space/parse/image',
            files={'filename': image_file},
            data={
                'apikey': api_key,
                'language': 'eng',
                'isOverlayRequired': False,
            }
        )

    try:
        result = response.json()
        if result.get('IsErroredOnProcessing'):
            print("OCR API Error:", result.get("ErrorMessage"))
            return "Failed to extract text."
        parsed_results = result.get("ParsedResults")
        if not parsed_results:
            return "No text found."
        return parsed_results[0].get("ParsedText", "No text found.")
    except Exception as e:
        print("Exception occurred while parsing OCR response:", e)
        return "Failed to extract text."
