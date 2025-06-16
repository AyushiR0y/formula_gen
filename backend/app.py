import os
import re
import json
from typing import List, Dict, Tuple
from flask import Flask, request, jsonify
from flask_cors import CORS
from pdfminer.high_level import extract_text as extract_text_from_pdf_lib
import google.generativeai as genai
import requests
from dotenv import load_dotenv
import spacy
from dataclasses import dataclass

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {'pdf', 'txt', 'docx'}

# --- API KEY CONFIGURATION ---
API_KEY = os.getenv('GEMINI_API_KEY')
if not API_KEY:
    print("❌ ERROR: GEMINI_API_KEY environment variable not set!")
    print("Please create a .env file with your API key")
    exit(1)

genai.configure(api_key=API_KEY)

@dataclass
class ExtractedFormula:
    acronym: str
    full_name: str
    description: str
    formula: str
    confidence: float
    source_method: str
    variables: List[str]

class InsuranceFormulaExtractor:
    """Advanced formula extractor for insurance documents"""
    
    def __init__(self):
        self.insurance_terms = self._load_insurance_vocabulary()
        self.business_logic_patterns = self._load_business_logic_patterns()
        self.mathematical_operators = {
            'percentage of': ' × ',
            'percent of': ' × ',
            'multiplied by': ' × ',
            'times': ' × ',
            'divided by': ' ÷ ',
            'plus': ' + ',
            'minus': ' - ',
            'added to': ' + ',
            'subtracted from': ' - ',
            'sum of': 'Σ(',
            'total of': 'Σ(',
            'maximum of': 'max(',
            'minimum of': 'min(',
            'whichever is higher': 'max(',
            'whichever is lower': 'min(',
            'greater of': 'max(',
            'lesser of': 'min('
        }
    
    def _load_insurance_vocabulary(self) -> Dict[str, str]:
        """Load insurance-specific term mappings"""
        return {
            'sum assured': 'SA',
            'sum insured': 'SI',
            'annual premium': 'AP',
            'total premium': 'TP',
            'premiums paid': 'PP',
            'maturity benefit': 'MB',
            'death benefit': 'DB',
            'surrender value': 'SV',
            'guaranteed surrender value': 'GSV',
            'special surrender value': 'SSV',
            'paid up value': 'PUV',
            'policy year': 'n',
            'premium paying term': 'PPT',
            'policy term': 'PT',
            'bonus': 'B',
            'loyalty addition': 'LA',
            'terminal bonus': 'TB',
            'reversionary bonus': 'RB',
            'surrender charge': 'SC',
            'mortality charge': 'MC',
            'administration charge': 'AC',
            'fund value': 'FV',
            'net asset value': 'NAV',
            'allocation rate': 'AR',
            'risk factor': 'RF',
            'loading factor': 'LF',
            'discount factor': 'DF',
            'interest rate': 'r',
            'inflation rate': 'i',
            'commission': 'COM',
            'brokerage': 'BROK',
            'coverage amount': 'CA',
            'insured amount': 'IA',
            'claim amount': 'CLA',
            'deductible': 'DED',
            'co-payment': 'COPAY',
            'waiting period': 'WP',
            'age': 'AGE',
            'gender factor': 'GF',
            'medical loading': 'ML',
            'occupational loading': 'OL'
        }
    
    def _load_business_logic_patterns(self) -> List[Dict]:
        """Load patterns for converting business logic to formulas"""
        return [
            {
                'pattern': r'(\w+(?:\s+\w+)*)\s+is\s+(\d+(?:\.\d+)?)\s*%\s+of\s+(.+?)(?:\.|,|$)',
                'template': '{var1} = {var3} × {percentage}',
                'type': 'percentage_calculation'
            },
            {
                'pattern': r'whichever\s+is\s+(?:higher|highest|greater|maximum)\s+(?:among|between)\s+(.+?)(?:\.|,|$)',
                'template': 'Result = max({variables})',
                'type': 'maximum_selection'
            },
            {
                'pattern': r'whichever\s+is\s+(?:lower|lowest|smaller|minimum)\s+(?:among|between)\s+(.+?)(?:\.|,|$)',
                'template': 'Result = min({variables})',
                'type': 'minimum_selection'
            },
            {
                'pattern': r'(?:sum|total)\s+of\s+(.+?)\s+and\s+(.+?)(?:\.|,|$)',
                'template': 'Total = {var1} + {var2}',
                'type': 'addition'
            },
            {
                'pattern': r'(?:ratio|proportion)\s+of\s+(.+?)\s+to\s+(.+?)(?:\.|,|$)',
                'template': 'Ratio = {var1} ÷ {var2}',
                'type': 'ratio_calculation'
            },
            {
                'pattern': r'reduced\s+(?:by|to)\s+(\d+(?:\.\d+)?)\s*%',
                'template': 'Result = Original × (1 - {percentage})',
                'type': 'percentage_reduction'
            },
            {
                'pattern': r'increased\s+(?:by|to)\s+(\d+(?:\.\d+)?)\s*%',
                'template': 'Result = Original × (1 + {percentage})',
                'type': 'percentage_increase'
            },
            {
                'pattern': r'based\s+on\s+(?:the\s+)?(?:ratio|proportion)\s+of\s+(.+?)\s+to\s+(.+?)(?:\.|,|$)',
                'template': 'Result = Base_Amount × ({var1} ÷ {var2})',
                'type': 'proportional_calculation'
            }
        ]
    
    def extract_variables_from_text(self, text: str) -> List[str]:
        """Extract potential variables from text"""
        variables = set()
        
        # Extract insurance terms
        for term, abbreviation in self.insurance_terms.items():
            if term.lower() in text.lower():
                variables.add(abbreviation)
        
        # Extract numerical values
        numerical_patterns = [
            r'\d+(?:\.\d+)?%',  # Percentages
            r'\d+(?:,\d{3})*(?:\.\d+)?',  # Numbers with commas
            r'[A-Z]{2,5}',  # Abbreviations
        ]
        
        for pattern in numerical_patterns:
            matches = re.findall(pattern, text)
            variables.update(matches)
        
        return list(variables)
    
    def convert_descriptive_to_formula(self, text: str) -> List[ExtractedFormula]:
        """Convert descriptive business logic to mathematical formulas"""
        formulas = []
        
        for pattern_info in self.business_logic_patterns:
            pattern = pattern_info['pattern']
            template = pattern_info['template']
            formula_type = pattern_info['type']
            
            matches = re.finditer(pattern, text, re.IGNORECASE)
            
            for match in matches:
                try:
                    # Extract matched groups
                    groups = match.groups()
                    
                    if formula_type == 'percentage_calculation':
                        var1 = self._standardize_term(groups[0])
                        percentage = float(groups[1]) / 100
                        var3 = self._standardize_term(groups[2])
                        
                        formula = template.format(
                            var1=var1,
                            var3=var3,
                            percentage=percentage
                        )
                        
                        formulas.append(ExtractedFormula(
                            acronym=var1,
                            full_name=groups[0],
                            description=f"Percentage calculation: {groups[0]} as {groups[1]}% of {groups[2]}",
                            formula=formula,
                            confidence=0.85,
                            source_method='pattern_matching',
                            variables=[var1, var3]
                        ))
                    
                    elif formula_type in ['maximum_selection', 'minimum_selection']:
                        variables_text = groups[0]
                        variables = self._parse_variable_list(variables_text)
                        
                        formula = template.format(variables=', '.join(variables))
                        
                        formulas.append(ExtractedFormula(
                            acronym='SEL',
                            full_name='Selection Formula',
                            description=f"Selection of {'maximum' if 'max' in template else 'minimum'} value",
                            formula=formula,
                            confidence=0.80,
                            source_method='pattern_matching',
                            variables=variables
                        ))
                    
                    elif formula_type == 'addition':
                        var1 = self._standardize_term(groups[0])
                        var2 = self._standardize_term(groups[1])
                        
                        formula = template.format(var1=var1, var2=var2)
                        
                        formulas.append(ExtractedFormula(
                            acronym='SUM',
                            full_name='Sum Calculation',
                            description=f"Addition of {groups[0]} and {groups[1]}",
                            formula=formula,
                            confidence=0.90,
                            source_method='pattern_matching',
                            variables=[var1, var2]
                        ))
                    
                    elif formula_type == 'ratio_calculation':
                        var1 = self._standardize_term(groups[0])
                        var2 = self._standardize_term(groups[1])
                        
                        formula = template.format(var1=var1, var2=var2)
                        
                        formulas.append(ExtractedFormula(
                            acronym='RATIO',
                            full_name='Ratio Calculation',
                            description=f"Ratio of {groups[0]} to {groups[1]}",
                            formula=formula,
                            confidence=0.85,
                            source_method='pattern_matching',
                            variables=[var1, var2]
                        ))
                    
                    elif formula_type in ['percentage_reduction', 'percentage_increase']:
                        percentage = float(groups[0]) / 100
                        operation = '+' if 'increase' in formula_type else '-'
                        
                        formula = template.format(percentage=percentage)
                        
                        formulas.append(ExtractedFormula(
                            acronym='PCT',
                            full_name='Percentage Adjustment',
                            description=f"Percentage {'increase' if operation == '+' else 'reduction'} by {groups[0]}%",
                            formula=formula,
                            confidence=0.85,
                            source_method='pattern_matching',
                            variables=['Original']
                        ))
                    
                    elif formula_type == 'proportional_calculation':
                        var1 = self._standardize_term(groups[0])
                        var2 = self._standardize_term(groups[1])
                        
                        formula = template.format(var1=var1, var2=var2)
                        
                        formulas.append(ExtractedFormula(
                            acronym='PROP',
                            full_name='Proportional Calculation',
                            description=f"Proportional calculation based on {groups[0]} to {groups[1]}",
                            formula=formula,
                            confidence=0.80,
                            source_method='pattern_matching',
                            variables=[var1, var2, 'Base_Amount']
                        ))
                        
                except Exception as e:
                    print(f"Error processing pattern {formula_type}: {e}")
                    continue
        
        return formulas
    
    def _standardize_term(self, term: str) -> str:
        """Convert insurance terms to standard abbreviations"""
        term_lower = term.lower().strip()
        
        # Direct lookup
        if term_lower in self.insurance_terms:
            return self.insurance_terms[term_lower]
        
        # Partial matching
        for full_term, abbrev in self.insurance_terms.items():
            if full_term in term_lower or term_lower in full_term:
                return abbrev
        
        # Generate abbreviation from term
        words = term.split()
        if len(words) == 1:
            return words[0][:3].upper()
        else:
            return ''.join(word[0].upper() for word in words if word)
    
    def _parse_variable_list(self, variables_text: str) -> List[str]:
        """Parse a list of variables from text"""
        # Split by common delimiters
        variables = re.split(r'[,;]|\s+and\s+|\s+or\s+', variables_text)
        
        # Clean and standardize each variable
        cleaned_variables = []
        for var in variables:
            var = var.strip().strip('()[]{}')
            if var:
                standardized = self._standardize_term(var)
                cleaned_variables.append(standardized)
        
        return cleaned_variables

# Initialize the extractor
formula_extractor = InsuranceFormulaExtractor()

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_file(filepath):
    """Extract text from supported file formats"""
    try:
        file_extension = os.path.splitext(filepath)[1].lower()
        
        if file_extension == '.pdf':
            return extract_text_from_pdf_lib(filepath)
        
        elif file_extension == '.txt':
            with open(filepath, 'r', encoding='utf-8') as file:
                return file.read()
        
        elif file_extension == '.docx':
            try:
                import docx
                doc = docx.Document(filepath)
                return '\n'.join([paragraph.text for paragraph in doc.paragraphs])
            except ImportError:
                print("python-docx not installed. Install with: pip install python-docx")
                return ""
        
        else:
            return ""
            
    except Exception as e:
        print(f"Error extracting text from file: {e}")
        return ""

def call_enhanced_gemini_llm(text: str) -> str:
    """Enhanced Gemini call with better prompting for descriptive text"""
    try:
        print("⚙️ Calling Enhanced Gemini with improved prompt...")
        
        enhanced_prompt = f"""
        You are an expert insurance mathematician. Convert the following descriptive insurance text into mathematical formulas.

        INSTRUCTIONS:
        1. Look for descriptive calculations like "percentage of", "whichever is higher", "sum of", etc.
        2. Convert business logic into mathematical notation
        3. Use standard insurance abbreviations: SA (Sum Assured), AP (Annual Premium), GSV (Guaranteed Surrender Value), etc.
        4. Format as: [ACRONYM]: [Full Name] - [Description] = [Mathematical Formula]

        EXAMPLES:
        Text: "The surrender value is 80% of total premiums paid"
        Output: SV: Surrender Value - Amount received on policy surrender = TP × 0.80

        Text: "Death benefit is whichever is higher among sum assured and total premiums paid"
        Output: DB: Death Benefit - Amount paid on death = max(SA, TP)

        TEXT TO ANALYZE:
        \"\"\"{text[:1500]}\"\"\"

        Convert ALL descriptive calculations to mathematical formulas. If no calculations found, return "No mathematical relationships found."
        """
        
        model_names = ['gemini-1.5-flash', 'gemini-pro', 'gemini-1.0-pro']
        
        for model_name in model_names:
            try:
                print(f"Trying model: {model_name}")
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(enhanced_prompt)
                generated_text = response.text
                print(f"✅ Enhanced Gemini returned output using model: {model_name}")
                return generated_text
            except Exception as model_error:
                print(f"❌ Model {model_name} failed: {model_error}")
                continue
        
        return "All Gemini models failed"
        
    except Exception as e:
        print(f"❌ Enhanced Gemini failed: {e}")
        return f"Enhanced Gemini error: {e}"

def parse_enhanced_llm_response(response_text: str) -> List[Dict]:
    """Parse enhanced LLM response to extract structured formula data"""
    formulas = []
    lines = response_text.strip().splitlines()
    
    for line in lines:
        line = line.strip()
        if not line or "no mathematical relationships found" in line.lower():
            continue
            
        # Enhanced pattern matching for LLM output
        patterns = [
            r'(\w+):\s*([^-]+)\s*-\s*([^=]+)\s*=\s*(.+)',  # Standard format
            r'(\w+)\s*=\s*(.+)',  # Simple equation format
            r'Formula:\s*(.+)',  # Formula prefix
        ]
        
        for pattern in patterns:
            match = re.match(pattern, line)
            if match:
                if len(match.groups()) == 4:  # Standard format
                    acronym, full_name, description, formula = match.groups()
                    formulas.append({
                        'acronym': acronym.strip(),
                        'full_name': full_name.strip(),
                        'description': description.strip(),
                        'formula': f"{acronym.strip()} = {formula.strip()}",
                        'confidence': 0.85,
                        'source_method': 'enhanced_llm',
                        'variables': []
                    })
                elif len(match.groups()) == 2:  # Simple equation
                    var, equation = match.groups()
                    formulas.append({
                        'acronym': var.strip(),
                        'full_name': 'Mathematical Relationship',
                        'description': 'Formula extracted from descriptive text',
                        'formula': f"{var.strip()} = {equation.strip()}",
                        'confidence': 0.75,
                        'source_method': 'enhanced_llm',
                        'variables': []
                    })
                break
    
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

        # Extract text from file
        text = extract_text_from_file(filepath)
        if not text.strip():
            print("Extracted text is empty. Cannot process.")
            return jsonify({
                "message": "Could not extract text from file or file was empty.",
                "status": "error",
                "formulas": []
            }), 400

        print(f"Extracted text length: {len(text)} characters.")

        # Multi-step formula extraction
        all_formulas = []
        
        # Step 1: Enhanced pattern-based extraction
        print("🔍 Step 1: Pattern-based extraction...")
        pattern_formulas = formula_extractor.convert_descriptive_to_formula(text)
        all_formulas.extend([{
            'acronym': f.acronym,
            'full_name': f.full_name,
            'description': f.description,
            'formula': f.formula,
            'confidence': f.confidence,
            'source_method': f.source_method,
            'variables': f.variables
        } for f in pattern_formulas])
        
        # Step 2: Enhanced LLM extraction
        print("🤖 Step 2: Enhanced LLM extraction...")
        llm_response = call_enhanced_gemini_llm(text)
        llm_formulas = parse_enhanced_llm_response(llm_response)
        all_formulas.extend(llm_formulas)
        
        # Step 3: Remove duplicates and rank by confidence
        unique_formulas = []
        seen_formulas = set()
        
        for formula in sorted(all_formulas, key=lambda x: x.get('confidence', 0), reverse=True):
            formula_key = formula['formula'].lower().replace(' ', '')
            if formula_key not in seen_formulas:
                seen_formulas.add(formula_key)
                unique_formulas.append(formula)

        print(f"Final unique formulas: {len(unique_formulas)}")

        # Determine response status and message
        if not unique_formulas:
            message = "File processed successfully, but no mathematical formulas or convertible business logic were found."
            status = "warning"
        else:
            message = f"Successfully extracted and converted {len(unique_formulas)} formulas from {filename}."
            status = "success"

        return jsonify({
            "message": message,
            "raw_llm_output": llm_response.strip() if 'llm_response' in locals() else "",
            "formulas": unique_formulas,
            "status": status,
            "file_type": os.path.splitext(filename)[1].lower(),
            "extraction_methods": {
                "pattern_based": len(pattern_formulas),
                "llm_based": len(llm_formulas),
                "total_unique": len(unique_formulas)
            }
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

@app.route('/test-conversion', methods=['POST'])
def test_conversion():
    """Test endpoint for converting descriptive text to formulas"""
    data = request.get_json()
    if not data or 'text' not in data:
        return jsonify({"error": "No text provided"}), 400
    
    text = data['text']
    formulas = formula_extractor.convert_descriptive_to_formula(text)
    
    return jsonify({
        "input_text": text,
        "extracted_formulas": [{
            'acronym': f.acronym,
            'full_name': f.full_name,
            'description': f.description,
            'formula': f.formula,
            'confidence': f.confidence,
            'source_method': f.source_method,
            'variables': f.variables
        } for f in formulas]
    })

if __name__ == '__main__':
    app.run(debug=True)