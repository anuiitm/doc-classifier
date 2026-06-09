import os
import json
from google import genai
from google.genai import types

PROMPT = """
You are a strict document classification and extraction AI.
Analyze the provided document and extract information based on its type.

First, identify the document as one of these exact types (this is the `decision`):
["AADHAAR", "PAN", "VOTER_ID", "DL", "PASSPORT", "BANK_STATEMENT", "BANK_PASSBOOK", "CHEQUE", "INVOICE", "INSURANCE", "ROAD_TAX", "UNKNOWN"]

Also provide a human-readable `display_name` for the document (e.g. "Aadhaar Card", "Bank Passbook", "Unknown / Needs Review").

If the document is UNKNOWN, return decision "UNKNOWN" and empty fields.

If the document is recognized, extract the following fields exactly depending on the type:
- AADHAAR: Name, DOB, Gender, Address, and Aadhaar Number (store the number as `identifier`).
- PASSPORT: Name, DOB, Gender, Address, and Passport Number (store the number as `identifier`).
- DL: Name, DOB, Gender, Address, and DL Number (store the number as `identifier`).
- VOTER_ID: Name, DOB, Gender, Address, and Voter ID (store the id as `identifier`).
- PAN: Name, DOB, Father's Name, and PAN Number (store the number as `identifier`).
- BANK_STATEMENT, BANK_PASSBOOK, CHEQUE: Bank Name, IFSC, and Account No (store the Account No as `identifier`).
- INVOICE, INSURANCE, ROAD_TAX: No extra fields needed.

Return the result as a valid JSON object matching this schema:
{
    "decision": "<DOC_TYPE>",
    "display_name": "<Human readable name>",
    "confidence": <float between 0.0 and 1.0 representing your confidence>,
    "identifier": "<the main identifier string, or null>",
    "extracted_fields": {
        "<Field Name>": "<Field Value>",
        ...
    }
}

Important Rules:
1. Do NOT wrap the JSON in markdown blocks like ```json ... ```. Output raw JSON only.
2. If a required field is not found in the document, map its value to "Not Found".
3. For identifiers, clean up whitespace or special characters if appropriate (e.g. standardizing PAN/Aadhaar formats).
"""

def classify_file_gemini(path: str) -> dict:
    """
    Takes a file path (image or PDF), sends it to Gemini 2.5 Flash,
    and returns a normalized classification dictionary.
    """
    import dotenv
    dotenv.load_dotenv()
    
    # Ensure GEMINI_API_KEY is in environment
    if not os.environ.get("GEMINI_API_KEY"):
        return {
            "ok": False,
            "error": "GEMINI_API_KEY is not set in the environment.",
            "decision": "ERROR"
        }
        
    try:
        client = genai.Client()
        
        # Upload the file using the Gemini File API (supports Images and PDFs well)
        uploaded_file = client.files.upload(file=path)
        
        # Call the model
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[uploaded_file, PROMPT],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.0,
            )
        )
        
        # Clean up the file from Google's servers
        try:
            client.files.delete(name=uploaded_file.name)
        except Exception:
            pass # Best effort cleanup
            
        result_json = json.loads(response.text)
        decision = result_json.get("decision", "UNKNOWN")
        display_name = result_json.get("display_name", "Unknown / Needs Review")
        
        result = {
            "ok": True,
            "decision": decision,
            "display_name": display_name,
            "confidence": result_json.get("confidence", 0.0),
            "identifier": result_json.get("identifier"),
            "needs_human_review": result_json.get("confidence", 0.0) < 0.8,
            "extracted_fields": result_json.get("extracted_fields", {}),
            # Pass a mock raw_text so api.py doesn't crash or behave weirdly if stitched later
            "raw_text": "Extracted via Gemini API"
        }
        
        return result
        
    except Exception as e:
        return {
            "ok": False,
            "error": f"Gemini API Error: {str(e)}",
            "decision": "ERROR"
        }
