import os
import re
import json
from typing import List, Dict, Tuple, Optional, Set
from flask import Flask, request, jsonify
from flask_cors import CORS
from pdfminer.high_level import extract_text as extract_text_from_pdf_lib
import google.generativeai as genai
import requests
from dotenv import load_dotenv
from dataclasses import dataclass, asdict
import hashlib
import time
import traceback
from werkzeug.utils import secure_filename

load_dotenv()

app = Flask(__name__)
CORS(app, origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:4200", "http://127.0.0.1:4200"])

# Configuration
UPLOAD_FOLDER = 'uploads'
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {'pdf', 'txt', 'docx'}

# --- API KEY CONFIGURATION ---
API_KEY = os.getenv('GEMINI_API_KEY')
if not API_KEY:
    print("⚠️  WARNING: GEMINI_API_KEY environment variable not set!")
    print("Please set your GEMINI_API_KEY to extract formulas from documents.")
    MOCK_MODE = True
else:
    genai.configure(api_key=API_KEY)
    MOCK_MODE = False

# --- GENERIC INSURANCE TERMS DICTIONARY ---
GENERIC_INSURANCE_TERMS = {
    'TERM_START_DATE': 'Policy commencement date',
    'DATE_OF_COMMENCEMENT': 'TERM_START_DATE',
    'ENTRY_AGE': 'Age of the policyholder at policy inception',
    'BENEFIT_TERM': 'Duration for which benefits are payable in months',
    'ISSUE_AGE': 'ENTRY_AGE',
    'PREMIUM': 'Premium amount (annual/monthly/quarterly)',
    'FULL_TERM_PREMIUM': 'PREMIUM',
    'ANNUALISED_PREMIUM': 'Annual premium amount',
    'POLICY_YEAR':'ROUND(YEARFRAC(TERM_START_DATE, DATE_OF_SURRENDER)+1,0)',
    'MONTHLY_PREMIUM': 'Monthly premium amount',
    'PREMIUM_FREQUENCY': 'Frequency of premium payment',
    'BOOKING_FREQUENCY': 'Frequency of premium booking',
    'BOOKING_TIME': 'Duration for premium booking in years',
    'POLICY_TERM': 'Total duration of the policy',
    'PREMIUM_TERM': 'Premium Paying Term - duration for paying premiums',
    'SA': 'Sum Assured - guaranteed amount on maturity/death',
    'SUM_ASSURED': 'Basic sum assured amount',
    'DEATH_BENEFIT': 'Benefit payable on death',
    'MATURITY_BENEFIT': 'Benefit payable on maturity',
    'INCOME_BENEFIT_AMOUNT': 'Amount of income benefit',
    'INCOME_BENEFIT_FREQUENCY': 'Frequency of income benefit payout',
    'SURRENDER_DATE': 'Date when policy is surrendered',
    'MATURITY_DATE': 'EDATE(TERM_START_DATE,(BENEFIT_TERM*12))',
    'FUP': 'First Unpaid Premium date',
    'FIRST_UNPAID_PREMIUM_DATE': 'Date of first unpaid premium',
    'NO_OF_PREMIUM_PAID': 'Number of premiums paid',
    'PREMIUMS_PAID_COUNT': 'Count of premiums paid',
    'POLICY_YEAR': 'Current policy year',
    'TOTAL_PREMIUM_PAID': 'Total amount of premiums paid',
    'GSV': 'Guaranteed Surrender Value',
    'SSV': 'Special Surrender Value',
    'SSV1_AMT': 'Special Surrender Value component 1',
    'SSV2_AMT': 'Special Surrender Value component 2', 
    'SSV3_AMT': 'Special Surrender Value component 3',
    'PAID_UP_SA': 'Paid-up Sum Assured',
    'PAID_UP_VALUE': 'Paid-up policy value',
    'LOYALTY_ADDITION': 'Loyalty addition amount',
    'BONUS': 'Bonus amount',
    'CASH_VALUE': 'Cash value of the policy',
    'SURRENDER_CHARGE': 'Charges applicable on surrender',
    'MORTALITY_CHARGE': 'Mortality charges',
    'ADMIN_CHARGE': 'Administration charges',
    'FUND_VALUE': 'Current fund value',
    'NAV': 'Net Asset Value',
    'UNITS': 'Number of units allocated',
    'UNIT_PRICE': 'Price per unit',
    'TOP_UP_PREMIUM': 'Additional premium paid',
    'PARTIAL_WITHDRAWAL': 'Amount withdrawn partially',
    'LOAN_AMOUNT': 'Policy loan amount',
    'INTEREST_RATE': 'Interest rate applicable',
    'DISCOUNT_RATE': 'Discount rate for calculations',
    'MORTALITY_RATE': 'Mortality rate factor',
    'LAPSE_RATE': 'Policy lapse rate',
    'GUARANTEED_RATE': 'Guaranteed interest rate',
    'CURRENT_RATE': 'Current interest rate',
    'PROJECTED_RATE': 'Projected interest rate'
    'SV_FACTOR: Surrender Value Factoradditional factor (sometimes policy-specific) used to adjust GSV or non-guaranteed components.', 
    'SSV2_FACTOR': 'Special Surrender Value Factor - additional factor used to adjust SSV component based on ROP or additional benefits.',
    'SSV3_FACTOR': 'Special Surrender Value Factor - additional factor used to adjust SSV component based on paid-up income benefits or survival benefits.'
}   

@dataclass
class ExtractedFormula:
    formula_name: str
    formula_expression: str
    variants_info: str
    business_context: str
    confidence: float
    source_method: str
    document_evidence: str
    specific_variables: Dict[str, str]
    variant_specific: bool = False
    applicable_variants: List[str] = None
    
    def __post_init__(self):
        if self.applicable_variants is None:
            self.applicable_variants = []
    
    def to_dict(self):
        return asdict(self)

@dataclass
class DocumentExtractionResult:
    input_variables: Dict[str, str]
    output_variables: List[str]
    extracted_formulas: List[ExtractedFormula]
    extraction_summary: str
    overall_confidence: float
    surrender_formula_found: bool
    variants_detected: List[str]
    
    def to_dict(self):
        return asdict(self)

class DocumentFormulaExtractor:
    """Extracts formulas from document content using custom variables"""
    
    def __init__(self):
        self.generic_terms = GENERIC_INSURANCE_TERMS
        self.input_variables = {}
        self.output_variables = []
        self.variants_detected = []
        
    def set_custom_variables(self, input_vars: Dict[str, str], output_vars: List[str]):
        """Set custom input and output variables"""
        self.input_variables = input_vars
        self.output_variables = output_vars
        print(f"📝 Custom variables set: {len(input_vars)} inputs, {len(output_vars)} outputs")
        
    def extract_formulas_from_document(self, text: str) -> DocumentExtractionResult:
        """Extract all formulas from document text using custom variables"""
        
        if MOCK_MODE or not API_KEY:
            return self._explain_no_extraction()
        
        try:
            print("🔍 Starting document-based formula extraction with custom variables...")
            
            # First detect variants in the document
            self.variants_detected = self._detect_variants(text)
            print(f"🔍 Variants detected: {self.variants_detected}")
            
            # Identify formula sections
            formula_sections = self._identify_formula_sections(text)
            
            # Extract all formulas
            extracted_formulas = []
            
            for formula_name in self.output_variables:
                print(f"🔍 Extracting: {formula_name}")
                
                # Check if this formula might be variant-specific
                formula_results = self._extract_formula_with_variants(text, formula_name, formula_sections)
                
                if formula_results:
                    extracted_formulas.extend(formula_results)
                
                time.sleep(0.2)  # Rate limiting
            
            surrender_found = any(f.formula_name.lower() == 'surrender_value' for f in extracted_formulas)
            
            return DocumentExtractionResult(
                input_variables=self.input_variables,
                output_variables=self.output_variables,
                extracted_formulas=extracted_formulas,
                extraction_summary=f"Document analysis complete. Extracted {len(extracted_formulas)} formulas using custom variables.",
                overall_confidence=sum(f.confidence for f in extracted_formulas) / len(extracted_formulas) if extracted_formulas else 0.0,
                surrender_formula_found=surrender_found,
                variants_detected=self.variants_detected
            )
            
        except Exception as e:
            print(f"❌ Document extraction failed: {e}")
            print(f"Traceback: {traceback.format_exc()}")
            return self._explain_no_extraction()
    
    def _detect_variants(self, text: str) -> List[str]:
        """Detect product variants in the document"""
        
        prompt = f"""
        Analyze this insurance document to identify different product variants or options.
        
        DOCUMENT: {text}
        
        Look for:
        1. Different product plans (Plan A, Plan B, Option 1, Option 2, etc.)
        2. Different benefit structures
        3. Different calculation methods for the same benefit
        4. Age-based variations
        5. Premium-based variations
        6. Any mentions of "variant", "option", "plan", "type"
        
        Return ONLY the variant names/identifiers found, one per line.
        If no clear variants are found, return "STANDARD"
        
        Examples:
        Plan A
        Plan B
        Regular Option
        Premium Option
        """
        
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(prompt)
            
            variants = [line.strip() for line in response.text.split('\n') if line.strip()]
            return variants if variants else ["STANDARD"]
            
        except Exception as e:
            print(f"Error detecting variants: {e}")
            return ["STANDARD"]
    
    def _extract_formula_with_variants(self, text: str, formula_name: str, formula_sections: List[str]) -> List[ExtractedFormula]:
        """Extract formula considering variants"""
        
        search_text = "\n".join(formula_sections) if formula_sections else text
        
        # Create variable mapping prompt
        variable_context = self._create_variable_context()
        
        prompt = f"""
        Extract the formula for "{formula_name}" from this insurance document.
        
        DOCUMENT CONTENT: {search_text}
        
        CUSTOM INPUT VARIABLES: {self.input_variables}
        
        VARIABLE MAPPING CONTEXT: {variable_context}
        
        DETECTED VARIANTS: {self.variants_detected}
        
        INSTRUCTIONS:
        1. Find how "{formula_name}" is calculated in this document
        2. Use ONLY the custom input variable names provided above
        3. Keep variable names in EXACT format as provided (e.g., ENTRY_AGE, not entry_age)
        4. If formula differs by variant, extract each variant separately
        5. If no variant-specific differences, extract one formula for all variants
        6. Map document terms to custom variables using the context provided
        
        RESPONSE FORMAT for each variant (if applicable):
        VARIANT: [variant name or "ALL" if applies to all]
        FORMULA: [mathematical expression using custom variable names]
        VARIABLES_USED: [comma-separated list of custom variables actually used]
        DOCUMENT_EVIDENCE: [exact text that supports this]
        CONTEXT: [business explanation]
        CONFIDENCE: [0.1-1.0]
        VARIANT_SPECIFIC: [YES/NO]
        ---
        
        If formula not found, return "NOT_FOUND"
        """
        
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(prompt)
            
            if "NOT_FOUND" in response.text:
                return []
                
            return self._parse_variant_formula_response(response.text, formula_name)
            
        except Exception as e:
            print(f"Error extracting {formula_name}: {e}")
            return []
    
    def _create_variable_context(self) -> str:
        """Create context for variable mapping"""
        context = "VARIABLE MAPPING CONTEXT:\n"
        
        # Add custom variables
        for var_name, description in self.input_variables.items():
            context += f"{var_name}: {description}\n"
        
        # Add generic terms for reference
        context += "\nGENERIC INSURANCE TERMS (for reference):\n"
        for term, desc in self.generic_terms.items():
            context += f"{term}: {desc}\n"
            
        return context
    
    def _parse_variant_formula_response(self, response_text: str, formula_name: str) -> List[ExtractedFormula]:
        """Parse variant-aware formula response"""
        
        extracted_formulas = []
        
        # Split by variant sections
        sections = response_text.split('---')
        
        for section in sections:
            if not section.strip():
                continue
                
            try:
                # Extract variant
                variant_match = re.search(r'VARIANT:\s*(.+?)(?=\nFORMULA|$)', section, re.IGNORECASE)
                variant = variant_match.group(1).strip() if variant_match else "ALL"
                
                # Extract formula
                formula_match = re.search(r'FORMULA:\s*(.+?)(?=\nVARIABLES_USED|$)', section, re.DOTALL | re.IGNORECASE)
                formula_expression = formula_match.group(1).strip() if formula_match else "Formula not found"
                
                # Extract variables used
                variables_match = re.search(r'VARIABLES_USED:\s*(.+?)(?=\nDOCUMENT_EVIDENCE|$)', section, re.IGNORECASE)
                variables_str = variables_match.group(1).strip() if variables_match else ""
                specific_variables = self._parse_specific_variables(variables_str)
                
                # Extract document evidence
                evidence_match = re.search(r'DOCUMENT_EVIDENCE:\s*(.+?)(?=\nCONTEXT|$)', section, re.DOTALL | re.IGNORECASE)
                document_evidence = evidence_match.group(1).strip() if evidence_match else "No evidence found"
                
                # Extract context
                context_match = re.search(r'CONTEXT:\s*(.+?)(?=\nCONFIDENCE|$)', section, re.DOTALL | re.IGNORECASE)
                business_context = context_match.group(1).strip() if context_match else f"Calculation for {formula_name}"
                
                # Extract confidence
                confidence_match = re.search(r'CONFIDENCE:\s*([0-9]*\.?[0-9]+)', section, re.IGNORECASE)
                confidence = float(confidence_match.group(1)) if confidence_match else 0.5
                
                # Extract variant specific flag
                variant_specific_match = re.search(r'VARIANT_SPECIFIC:\s*(YES|NO)', section, re.IGNORECASE)
                variant_specific = variant_specific_match.group(1).upper() == "YES" if variant_specific_match else False
                
                # Create formula name with variant if applicable
                final_formula_name = f"{formula_name}" if variant == "ALL" else f"{formula_name}_{variant}"
                applicable_variants = [variant] if variant != "ALL" else self.variants_detected
                
                extracted_formula = ExtractedFormula(
                    formula_name=final_formula_name,
                    formula_expression=formula_expression,
                    variants_info=f"Variant: {variant}",
                    business_context=business_context,
                    confidence=confidence,
                    source_method='document_extraction',
                    document_evidence=document_evidence,
                    specific_variables=specific_variables,
                    variant_specific=variant_specific,
                    applicable_variants=applicable_variants
                )
                
                extracted_formulas.append(extracted_formula)
                
            except Exception as e:
                print(f"Error parsing formula section: {e}")
                continue
        
        return extracted_formulas
    
    def _identify_formula_sections(self, text: str) -> List[str]:
        """Identify sections of document that contain formulas"""
        
        prompt = f"""
        Analyze this insurance document and identify all sections that contain mathematical formulas, calculations, or benefit computations.
        
        DOCUMENT: {text}
        
        TASK: Extract ONLY the text sections that contain:
        1. Mathematical formulas (with = signs, calculations)
        2. Benefit calculations (surrender value, maturity value, etc.)
        3. Premium calculations
        4. Any text that shows how values are computed
        5. Variant-specific calculations
        
        Return each relevant section as a separate block.
        
        FORMAT: Return sections separated by "---SECTION---"
        """
        
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(prompt)
            
            sections = response.text.split("---SECTION---")
            return [section.strip() for section in sections if section.strip()]
            
        except Exception as e:
            print(f"Error identifying formula sections: {e}")
            return [text]
    
    def _parse_specific_variables(self, variables_str: str) -> Dict[str, str]:
        """Parse specific variables from comma-separated string"""
        
        specific_variables = {}
        if variables_str:
            var_names = [var.strip() for var in variables_str.split(',')]
            
            for var_name in var_names:
                if var_name in self.input_variables:
                    specific_variables[var_name] = self.input_variables[var_name]
                else:
                    specific_variables[var_name] = f"Variable: {var_name}"
        
        return specific_variables
    
    def _explain_no_extraction(self) -> DocumentExtractionResult:
        """Explain that extraction cannot be performed without API key"""
        
        return DocumentExtractionResult(
            input_variables=self.input_variables,
            output_variables=self.output_variables,
            extracted_formulas=[],
            extraction_summary="Cannot extract formulas from document - GEMINI_API_KEY required for document analysis.",
            overall_confidence=0.0,
            surrender_formula_found=False,
            variants_detected=[]
        )

# Initialize the document extractor
document_extractor = DocumentFormulaExtractor()

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

@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "Enhanced Document Formula Extractor",
        "version": "8.0",
        "api_key_configured": not MOCK_MODE,
        "supported_formats": list(ALLOWED_EXTENSIONS),
        "generic_terms_count": len(GENERIC_INSURANCE_TERMS),
        "features": [
            "Custom input/output variables",
            "Consistent variable formatting",
            "Variant-specific formula extraction",
            "Editable formulas",
            "Generic insurance terms dictionary"
        ]
    })

@app.route('/generic-terms', methods=['GET'])
def get_generic_terms():
    """Get the generic insurance terms dictionary"""
    return jsonify({
        "generic_terms": GENERIC_INSURANCE_TERMS,
        "count": len(GENERIC_INSURANCE_TERMS)
    })

@app.route('/upload', methods=['POST'])
def upload_file():
    """Enhanced document-based formula extraction with custom variables"""
    try:
        print("📋 Starting enhanced document-based formula extraction...")
        
        # Get form data
        if 'file' not in request.files:
            return jsonify({"message": "No file part", "status": "error"}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({"message": "No selected file", "status": "error"}), 400

        if not file or not allowed_file(file.filename):
            supported_types = ', '.join(ALLOWED_EXTENSIONS)
            return jsonify({
                "message": f"Unsupported file type. Supported types: {supported_types}", 
                "status": "error"
            }), 400

        # Get custom variables from form data
        input_variables_json = request.form.get('input_variables', '{}')
        output_variables_json = request.form.get('output_variables', '[]')
        
        try:
            input_variables = json.loads(input_variables_json)
            output_variables = json.loads(output_variables_json)
        except json.JSONDecodeError:
            return jsonify({
                "message": "Invalid JSON in variables data",
                "status": "error"
            }), 400

        # Set custom variables in extractor
        document_extractor.set_custom_variables(input_variables, output_variables)

        # Process file
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        print(f"📄 File saved: {filepath}")

        # Extract text
        text = extract_text_from_file(filepath)
        if not text.strip():
            return jsonify({
                "message": "Could not extract text from file or file was empty.",
                "status": "error",
                "formulas": []
            }), 400

        print(f"📝 Extracted text: {len(text)} characters")

        # Extract formulas from document
        extraction_result = document_extractor.extract_formulas_from_document(text)
        
        # Clean up uploaded file
        try:
            os.remove(filepath)
        except:
            pass

        # Convert to frontend format
        frontend_formulas = []
        for formula in extraction_result.extracted_formulas:
            frontend_formulas.append({
                "id": f"{formula.formula_name}_{hash(formula.formula_expression) % 10000}",
                "term_description": formula.formula_name,
                "mathematical_relationship": formula.formula_expression,
                "business_context": formula.business_context,
                "formula_explanation": formula.document_evidence,
                "confidence": formula.confidence,
                "reasoning_steps": [formula.variants_info],
                "variables_explained": formula.specific_variables,
                "source_method": formula.source_method,
                "variant_specific": formula.variant_specific,
                "applicable_variants": formula.applicable_variants,
                "editable": True
            })

        # Determine status
        if not MOCK_MODE and extraction_result.extracted_formulas:
            message = f"Successfully extracted {len(extraction_result.extracted_formulas)} formulas from document."
            status = "success"
        elif not MOCK_MODE and not extraction_result.extracted_formulas:
            message = "Document processed but no clear formulas found."
            status = "warning"
        else:
            message = "API key required for document analysis."
            status = "error"

        return jsonify({
            "message": message,
            "formulas": frontend_formulas,
            "status": status,
            "file_type": os.path.splitext(filename)[1].lower(),
            "extraction_method": "Enhanced Document Analysis",
            "total_formulas": len(frontend_formulas),
            "variants_detected": extraction_result.variants_detected,
            "input_variables": input_variables,
            "output_variables": output_variables,
            "api_key_configured": not MOCK_MODE
        }), 200
        
    except Exception as e:
        print(f"❌ Upload processing failed: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            "message": f"Processing failed: {str(e)}",
            "status": "error",
            "formulas": []
        }), 500

@app.route('/save-formulas', methods=['POST'])
def save_formulas():
    """Save edited formulas"""
    try:
        data = request.get_json()
        formulas = data.get('formulas', [])
        
        # Here you would typically save to database
        # For now, just return success
        
        return jsonify({
            "message": f"Successfully saved {len(formulas)} formulas",
            "status": "success",
            "saved_count": len(formulas)
        })
        
    except Exception as e:
        return jsonify({
            "message": f"Failed to save formulas: {str(e)}",
            "status": "error"
        }), 500

@app.route('/forward-formulas', methods=['POST'])
def forward_formulas():
    """Forward formulas to data processing service"""
    try:
        data = request.get_json()
        response = requests.post("http://127.0.0.1:5001/store-formulas", json=data)
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"message": f"Forwarding failed: {str(e)}"}), 500

@app.errorhandler(413)
def too_large(e):
    return jsonify({
        "message": "File too large. Maximum size is 16MB.",
        "status": "error"
    }), 413

@app.errorhandler(500)
def internal_error(e):
    return jsonify({
        "message": "Internal server error occurred.",
        "status": "error"
    }), 500

if __name__ == '__main__':
    print("📋 Starting Enhanced Document Formula Extractor")
    print(f"🔧 API Key Configured: {'YES' if not MOCK_MODE else 'NO'}")
    print("🌐 Server will run on http://127.0.0.1:5000")
    print("📁 Supported formats:", ', '.join(ALLOWED_EXTENSIONS))
    print(f"📊 Generic insurance terms: {len(GENERIC_INSURANCE_TERMS)}")
    print("✅ Features: Custom variables, Variant detection, Editable formulas")
    
    app.run(
        host='127.0.0.1',
        port=5000,
        debug=True,
        threaded=True
    )