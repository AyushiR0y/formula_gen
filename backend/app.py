import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from pdfminer.high_level import extract_text as extract_text_from_pdf_lib
import google.generativeai as genai
import re
import requests
import json
import docx  # For Word documents
from PIL import Image
import pytesseract  # For OCR on images

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Extended file support
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'doc', 'txt', 'png', 'jpg', 'jpeg', 'tiff', 'bmp'}

# --- CONFIGURE YOUR GEMINI API KEY ---
API_KEY = "AIzaSyA5DrkoFJ_nUOpJV3E4mqx0B0hH-8DTCTU"  # Replace with your actual key

genai.configure(api_key=API_KEY)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_file(filepath):
    """Extract text from various file types"""
    try:
        file_extension = os.path.splitext(filepath)[1].lower()
        
        if file_extension == '.pdf':
            return extract_text_from_pdf_lib(filepath)
        
        elif file_extension in ['.docx', '.doc']:
            doc = docx.Document(filepath)
            text = '\n'.join([paragraph.text for paragraph in doc.paragraphs])
            return text
        
        elif file_extension == '.txt':
            with open(filepath, 'r', encoding='utf-8') as file:
                return file.read()
        
        elif file_extension in ['.png', '.jpg', '.jpeg', '.tiff', '.bmp']:
            # OCR for images
            image = Image.open(filepath)
            text = pytesseract.image_to_string(image)
            return text
        
        else:
            return ""
            
    except Exception as e:
        print(f"Error extracting text from file: {e}")
        return ""

def call_gemini_llm(prompt):
    try:
        print("⚙️ Calling Google Gemini with prompt...")
        model_names = ['gemini-1.5-flash', 'gemini-pro', 'gemini-1.0-pro']
        
        for model_name in model_names:
            try:
                print(f"Trying model: {model_name}")
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)
                generated_text = response.text
                print(f"✅ Gemini returned output using model: {model_name}")
                print("Response Text:", generated_text[:500] + "..." if len(generated_text) > 500 else generated_text)
                return generated_text
            except Exception as model_error:
                print(f"❌ Model {model_name} failed: {model_error}")
                continue
        
        print("🔄 Falling back to HuggingFace API...")
        return call_huggingface_llm(prompt)
        
    except Exception as e:
        print(f"❌ All Gemini models failed: {e}")
        return call_huggingface_llm(prompt)

def call_huggingface_llm(prompt):
    try:
        print("⚙️ Calling HuggingFace API...")
        
        # Try multiple HuggingFace models
        models = [
            "microsoft/DialoGPT-medium",
            "google/flan-t5-base",
            "facebook/blenderbot-400M-distill"
        ]
        
        for model in models:
            try:
                api_url = f"https://api-inference.huggingface.co/models/{model}"
                
                headers = {"Content-Type": "application/json"}
                
                simplified_prompt = f"""
                Extract insurance formulas from text. Format as:
                1. [Acronym]: [Full Name] - [Description] = [Formula]
                
                Example:
                1. AP: Annual Premium - Yearly insurance cost = Base Rate × Coverage Amount × Risk Factor
                
                Text: {prompt[:800]}...
                """
                
                payload = {
                    "inputs": simplified_prompt,
                    "parameters": {
                        "max_length": 300,
                        "temperature": 0.2,
                        "do_sample": True,
                    }
                }
                
                response = requests.post(api_url, headers=headers, json=payload, timeout=30)
                
                if response.status_code == 200:
                    result = response.json()
                    if isinstance(result, list) and len(result) > 0:
                        generated_text = result[0].get('generated_text', '')
                        if generated_text.strip():
                            print(f"✅ HuggingFace returned output using {model}")
                            return generated_text
                
            except Exception as model_error:
                print(f"❌ HuggingFace model {model} failed: {model_error}")
                continue
                
        return "No suitable model available for processing."
        
    except Exception as e:
        print(f"❌ HuggingFace API error: {e}")
        return f"HuggingFace API error: {e}"

def extract_formulas_locally(text):
    """Enhanced local extraction with acronym generation"""
    print("⚙️ Using enhanced local pattern matching...")
    
    formulas = []
    
    # Enhanced patterns for insurance formulas
    patterns = [
        (r'Premium\s*=\s*([^.]+)', 'AP', 'Annual Premium', 'Total yearly insurance cost'),
        (r'Rate\s*=\s*([^.]+)', 'IR', 'Insurance Rate', 'Cost per unit of coverage'),
        (r'Coverage\s*=\s*([^.]+)', 'CA', 'Coverage Amount', 'Total insured value'),
        (r'Deductible\s*=\s*([^.]+)', 'DED', 'Deductible', 'Amount paid before insurance coverage'),
        (r'Commission\s*=\s*([^.]+)', 'COM', 'Commission', 'Agent compensation amount'),
        (r'Risk\s*Factor\s*=\s*([^.]+)', 'RF', 'Risk Factor', 'Multiplier based on risk assessment'),
        (r'([A-Za-z\s]+)\s*=\s*([^.]+)', 'GF', 'General Formula', 'Mathematical relationship'),
    ]
    
    for pattern, acronym, full_name, description in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            if isinstance(match, str):
                formula = f"{acronym} = {match.strip()}"
                if len(formula) > 5 and len(formula) < 150:
                    formulas.append({
                        'acronym': acronym,
                        'full_name': full_name,
                        'description': description,
                        'formula': formula
                    })
    
    # Remove duplicates
    seen = set()
    unique_formulas = []
    for formula in formulas:
        key = formula['formula']
        if key not in seen:
            seen.add(key)
            unique_formulas.append(formula)
    
    if unique_formulas:
        print(f"✅ Local extraction found {len(unique_formulas)} potential formulas")
        return unique_formulas
    else:
        return []

def parse_llm_response(response_text):
    """Parse LLM response to extract structured formula data"""
    formulas = []
    lines = response_text.strip().splitlines()
    
    for line in lines:
        line = line.strip()
        if not line or "no formulas found" in line.lower():
            continue
            
        # Look for pattern: Acronym: Full Name - Description = Formula
        pattern = r'(\w+):\s*([^-]+)\s*-\s*([^=]+)\s*=\s*(.+)'
        match = re.match(pattern, line)
        
        if match:
            acronym, full_name, description, formula = match.groups()
            formulas.append({
                'acronym': acronym.strip(),
                'full_name': full_name.strip(),
                'description': description.strip(),
                'formula': f"{acronym.strip()} = {formula.strip()}"
            })
        else:
            # Fallback: look for any mathematical expression
            if any(char in line for char in ['=', '+', '-', '*', '/', '%', '(', ')']):
                formula_text = re.sub(r'^\d+\.\s*|^\s*[-*]\s*', '', line).strip()
                if formula_text and len(formula_text) > 3:
                    formulas.append({
                        'acronym': 'GF',
                        'full_name': 'General Formula',
                        'description': 'Mathematical relationship extracted from document',
                        'formula': formula_text
                    })
    
    return formulas

@app.route('/upload', methods=['POST'])
def upload_file():
    print("Received upload request.")
    if 'file' not in request.files:
        print("No file part in request.")
        return jsonify({"message": "No file part", "status": "error"}), 400

    file = request.files['file']
    if file.filename == '':
        print("No selected file.")
        return jsonify({"message": "No selected file", "status": "error"}), 400

    if file and allowed_file(file.filename):
        filename = file.filename
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        print(f"File saved to: {filepath}")

        # Step 1: Extract raw text from various file types
        text = extract_text_from_file(filepath)
        if not text.strip():
            print("Extracted text is empty. Cannot process.")
            return jsonify({
                "message": "Could not extract text from file or file was empty.",
                "status": "error",
                "formulas": []
            }), 400

        print(f"Extracted text length: {len(text)} characters.")

        # Step 2: Create enhanced prompt for formula extraction
        gemini_prompt = f"""
        You are an expert at extracting and structuring mathematical formulas from insurance and financial documents.
        
        Below is text from a document. Extract formulas and format them as:
        [ACRONYM]: [Full Name] - [Description] = [Mathematical Formula]
        
        Examples:
        AP: Annual Premium - Total yearly insurance cost = Base Rate × Coverage Amount × Risk Factor
        IR: Insurance Rate - Cost per unit of coverage = Premium ÷ Coverage Amount
        DED: Deductible - Amount paid before coverage = Fixed Amount or Percentage × Claim
        
        Text:
        \"\"\"{text[:2000]}\"\"\"
        
        Return only the formatted formulas, one per line. If no formulas found, return "No formulas found."
        """
        
        # Try LLM first, then fallback to local extraction
        response_from_llm = call_gemini_llm(gemini_prompt)
        
        # Parse LLM response
        structured_formulas = parse_llm_response(response_from_llm)
        
        # If LLM didn't find formulas, try local pattern matching
        if not structured_formulas and "API error" not in response_from_llm:
            print("🔄 LLM found no formulas, trying local pattern matching...")
            structured_formulas = extract_formulas_locally(text)

        print(f"Final structured formulas: {len(structured_formulas)}")

        # Determine response status and message
        if not structured_formulas:
            if "API error" in response_from_llm:
                message = "AI processing failed, but file was processed. Try again or check configuration."
                status = "warning"
            else:
                message = "File processed successfully, but no mathematical formulas were found."
                status = "success"
        else:
            message = f"Successfully extracted {len(structured_formulas)} formulas from {filename}."
            status = "success"

        return jsonify({
            "message": message,
            "raw_output": response_from_llm.strip(),
            "formulas": structured_formulas,
            "status": status,
            "file_type": os.path.splitext(filename)[1].lower()
        }), 200
        
    else:
        print("Unsupported file type received.")
        supported_types = ', '.join(ALLOWED_EXTENSIONS)
        return jsonify({
            "message": f"Unsupported file type. Supported types: {supported_types}", 
            "status": "error"
        }), 415

@app.route('/supported-formats', methods=['GET'])
def get_supported_formats():
    """Endpoint to get list of supported file formats"""
    return jsonify({
        "supported_formats": list(ALLOWED_EXTENSIONS),
        "message": "List of supported file formats for upload"
    })

if __name__ == '__main__':
    app.run(debug=True)