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

# --- INPUT VARIABLES DEFINITIONS ---
INPUT_VARIABLES = {
    'TERM_START_DATE': 'Date when the policy starts',
    'FUP_Date': 'First Unpaid Premium date',
    'ENTRY_AGE': 'Age of the policyholder at policy inception',
    'FULL_TERM_PREMIUM': 'Annual Premium amount',
    'BOOKING_FREQUENCY': 'Frequency of premium booking (monthly, quarterly, yearly)',
    'PREMIUM_TERM': 'Premium Paying Term - duration for paying premiums',
    'SUM_ASSURED': 'Sum Assured - guaranteed amount on maturity/death',
    'Income_Benefit_Amount': 'Amount of income benefit',
    'Income_Benefit_Frequency': 'Frequency of income benefit payout',
    'DATE_OF_SURRENDER': 'Date when policy is surrendered',
    'no_of_premium_paid': 'Years passed since date of commencement till FUP',
    'maturity_date': 'Date of commencement + (BENEFIT_TERM * 12 months)',
    'policy_year': 'Years passed + 1 between date of commencement and surrender date',
    'BENEFIT_TERM': 'The duration (in years) for which the policy benefits are payable',
    'GSV_FACTOR': 'Guaranteed Surrender Value Factor, a percentage used to calculate the minimum guaranteed surrender value from total premiums paid.',
    'SV_FACTOR': 'Surrender Value Factor',
    'SSV2_FACTOR':'A special factor used to compute Special Surrender Value (SSV) related to return of premium (ROP)'


}

# Basic derived formulas that can be logically computed
BASIC_DERIVED_FORMULAS = {
    'no_of_premium_paid': 'Calculate based on difference between TERM_START_DATE and FUP_Date',
    'policy_year': 'Calculate based on difference between TERM_START_DATE and DATE_OF_SURRENDER + 1',
    'maturity_date': 'TERM_START_DATE + (BENEFIT_TERM* 12) months',
    'PV':'Final surrender value paid'
}

# TARGET OUTPUT VARIABLES (formulas must be extracted from document)
TARGET_OUTPUT_VARIABLES = [
    'TOTAL_PREMIUM_PAID',
    'TEN_TIMES_AP', 
    'one_oh_five_percent_total_premium',
    'SUM_ASSURED_ON_DEATH',
    'GSV',
    'PAID_UP_SA',
    'PAID_UP_SA_ON_DEATH', 
    'paid_up_income_benefit_amount',
    'SSV1_AMT',  # These were missing in extraction
    'SSV2_AMT',
    'SSV3_AMT',
    'SSV',
    'SURRENDER_PAID_AMOUNT',
    'PV'
]

@dataclass
class ExtractedFormula:
    formula_name: str
    formula_expression: str
    variants_info: str
    business_context: str
    confidence: float
    source_method: str
    document_evidence: str
    specific_variables: Dict[str, str]  # Only variables used in this formula
    
    def to_dict(self):
        return asdict(self)

@dataclass
class DocumentExtractionResult:
    input_variables: Dict[str, str]
    basic_derived_formulas: Dict[str, str]
    extracted_formulas: List[ExtractedFormula]
    extraction_summary: str
    overall_confidence: float
    surrender_formula_found: bool
    
    def to_dict(self):
        return asdict(self)

class DocumentFormulaExtractor:
    """Extracts formulas purely from document content without hardcoded formulas"""
    
    def __init__(self):
        self.input_variables = INPUT_VARIABLES
        self.basic_derived = BASIC_DERIVED_FORMULAS
        self.target_outputs = TARGET_OUTPUT_VARIABLES
        
    def extract_formulas_from_document(self, text: str) -> DocumentExtractionResult:
        """Extract all formulas from document text"""
        
        if MOCK_MODE or not API_KEY:
            return self._explain_no_extraction()
        
        try:
            print("🔍 Starting document-based formula extraction...")
            
            # First, analyze document structure and identify formula sections
            formula_sections = self._identify_formula_sections(text)
            
            # Extract surrender value formula with special focus
            surrender_result = self._extract_surrender_formula_specifically(text)
            
            # Extract all other formulas from document
            extracted_formulas = []
            
            for formula_name in self.target_outputs:
                print(f"🔍 Extracting: {formula_name}")
                
                if formula_name == 'surrender_value' and surrender_result:
                    extracted_formulas.append(surrender_result)
                else:
                    formula_result = self._extract_formula_from_document(text, formula_name, formula_sections)
                    if formula_result:
                        extracted_formulas.append(formula_result)
                
                time.sleep(0.2)  # Rate limiting
            
            surrender_found = any(f.formula_name == 'surrender_value' for f in extracted_formulas)
            
            return DocumentExtractionResult(
                input_variables=self.input_variables,
                basic_derived_formulas=self.basic_derived,
                extracted_formulas=extracted_formulas,
                extraction_summary=f"Document analysis complete. Extracted {len(extracted_formulas)} formulas from source document.",
                overall_confidence=sum(f.confidence for f in extracted_formulas) / len(extracted_formulas) if extracted_formulas else 0.0,
                surrender_formula_found=surrender_found
            )
            
        except Exception as e:
            print(f"❌ Document extraction failed: {e}")
            print(f"Traceback: {traceback.format_exc()}")
            return self._explain_no_extraction()
    
    def _identify_formula_sections(self, text: str) -> List[str]:
        """Identify sections of document that contain formulas"""
        
        prompt = f"""
        Analyze this insurance document and identify all sections that contain mathematical formulas, calculations, or surrender value computations.
        
        DOCUMENT: {text}
        
        TASK: Extract ONLY the text sections that contain:
        1. Mathematical formulas (with = signs, calculations)
        2. Surrender value calculations (GSV, SSV, SSV1, SSV2, SSV3)
        3. Benefit calculations
        4. Premium calculations
        5. Any text that shows how values are computed
        
        Return each relevant section as a separate block.
        Focus especially on surrender value, GSV, SSV, paid-up calculations.
        
        FORMAT: Return sections separated by "---SECTION---"
        """
        
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(prompt)
            
            sections = response.text.split("---SECTION---")
            return [section.strip() for section in sections if section.strip()]
            
        except Exception as e:
            print(f"Error identifying formula sections: {e}")
            return [text]  # Return full text if section identification fails
    
    def _extract_formula_from_document(self, text: str, formula_name: str, formula_sections: List[str]) -> Optional[ExtractedFormula]:
        """Extract specific formula from document sections with variable identification"""
        
        # Use formula sections if available, otherwise full text
        search_text = "\n".join(formula_sections) if formula_sections else text
        
        # Special handling for SSV components
        ssv_context = ""
        if formula_name in ['ssv1_amount', 'ssv2_amount', 'ssv3_amount']:
            ssv_context = """
            NOTE: For SSV (Special Surrender Value) components:
            - SSV1 typically relates to present value of paid-up sum assured on death
            - SSV2 typically relates to ROP (Return of Premium) or Total Premiums paid benefit
            - SSV3 typically relates to paid-up income instalments or survival benefits
            Look for these specific components in the surrender value calculations.
            """
        
        prompt = f"""
        Extract the formula for "{formula_name}" from this insurance document content.
        
        DOCUMENT CONTENT: {search_text}
        
        AVAILABLE VARIABLES: {list(self.input_variables.keys())}
        BASIC DERIVED: {self.basic_derived}
        
        TARGET: Find how "{formula_name}" is calculated in this document.
        {ssv_context}
        
        INSTRUCTIONS:
        1. Look for explicit formulas, calculation methods, or mathematical relationships
        2. Express using only the available variable names above
        3. IDENTIFY ONLY THE SPECIFIC VARIABLES used in this formula
        4. Extract exact supporting text from document
        5. If not explicitly stated but can be logically derived from context, derive it
        6. If truly not found or derivable, return "NOT_FOUND"
        
        RESPONSE FORMAT:
        FORMULA: [mathematical expression using only relevant variables]
        SPECIFIC_VARIABLES: [comma-separated list of variables actually used in this formula]
        DOCUMENT_EVIDENCE: [exact text that supports this]
        CONTEXT: [business explanation]
        METHOD: [EXPLICIT/DERIVED/NOT_FOUND]
        CONFIDENCE: [0.1-1.0]
        
        Example:
        FORMULA: premium * no_of_premium_paid
        SPECIFIC_VARIABLES: premium, no_of_premium_paid
        DOCUMENT_EVIDENCE: "The total premium paid is calculated by multiplying..."
        CONTEXT: "Total premiums received by company"
        METHOD: EXPLICIT
        CONFIDENCE: 0.9
        """
        
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(prompt)
            
            if "NOT_FOUND" in response.text:
                return None
                
            return self._parse_formula_response(response.text, formula_name)
            
        except Exception as e:
            print(f"Error extracting {formula_name}: {e}")
            return None
    
    def _extract_surrender_formula_specifically(self, text: str) -> Optional[ExtractedFormula]:
        """Special focused extraction for surrender value formula"""
        
        prompt = f"""
        CRITICAL TASK: Extract the surrender value calculation formula from this insurance document.
        
        DOCUMENT: {text}
        
        AVAILABLE INPUT VARIABLES: {list(self.input_variables.keys())}
        BASIC DERIVED FORMULAS: {self.basic_derived}
        
        REQUIREMENTS:
        1. Find the EXACT surrender value calculation method from the document
        2. Express formula using only the available variable names above
        3. IDENTIFY ONLY THE SPECIFIC VARIABLES used in surrender value calculation
        4. If document mentions GSV (Guaranteed Surrender Value) and SSV (Special Surrender Value), show relationship
        5. If multiple variants exist, show all variants
        6. Extract the ACTUAL text from document that describes this calculation.
        7. ROP= Total premiums paid. Display total premiums in the formula wherever ROP is used.
        
        RESPONSE FORMAT:
        SURRENDER_FORMULA: [exact mathematical expression using available variables]
        SPECIFIC_VARIABLES: [comma-separated list of variables actually used]
        VARIANTS: [if multiple calculation methods exist]
        DOCUMENT_EVIDENCE: [exact text from document that supports this formula]
        BUSINESS_LOGIC: [explanation of when/how this applies]
        CONFIDENCE: [0.1-1.0 based on clarity in document]
        
        If surrender value is not clearly defined in document, respond with "NOT_FOUND"
        """
        
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(prompt)
            
            if "NOT_FOUND" in response.text:
                return None
                
            return self._parse_surrender_response(response.text)
            
        except Exception as e:
            print(f"Error extracting surrender formula: {e}")
            return None
    
    def _parse_surrender_response(self, response_text: str) -> Optional[ExtractedFormula]:
        """Parse surrender formula response"""
        
        try:
            # Extract surrender formula
            formula_match = re.search(r'SURRENDER_FORMULA:\s*(.+?)(?=\nSPECIFIC_VARIABLES|$)', response_text, re.DOTALL | re.IGNORECASE)
            formula_expression = formula_match.group(1).strip() if formula_match else "Formula not clearly defined"
            
            # Extract specific variables
            variables_match = re.search(r'SPECIFIC_VARIABLES:\s*(.+?)(?=\nVARIANTS|$)', response_text, re.DOTALL | re.IGNORECASE)
            specific_vars_str = variables_match.group(1).strip() if variables_match else ""
            specific_variables = self._parse_specific_variables(specific_vars_str)
            
            # Extract variants
            variants_match = re.search(r'VARIANTS:\s*(.+?)(?=\nDOCUMENT_EVIDENCE|$)', response_text, re.DOTALL | re.IGNORECASE)
            variants_info = variants_match.group(1).strip() if variants_match else "Single method"
            
            # Extract document evidence
            evidence_match = re.search(r'DOCUMENT_EVIDENCE:\s*(.+?)(?=\nBUSINESS_LOGIC|$)', response_text, re.DOTALL | re.IGNORECASE)
            document_evidence = evidence_match.group(1).strip() if evidence_match else "Evidence not extracted"
            
            # Extract business logic
            logic_match = re.search(r'BUSINESS_LOGIC:\s*(.+?)(?=\nCONFIDENCE|$)', response_text, re.DOTALL | re.IGNORECASE)
            business_context = logic_match.group(1).strip() if logic_match else "Surrender value calculation"
            
            # Extract confidence
            confidence_match = re.search(r'CONFIDENCE:\s*([0-9]*\.?[0-9]+)', response_text, re.IGNORECASE)
            confidence = float(confidence_match.group(1)) if confidence_match else 0.5
            
            return ExtractedFormula(
                formula_name='surrender_value',
                formula_expression=formula_expression,
                variants_info=variants_info,
                business_context=business_context,
                confidence=confidence,
                source_method='document_extraction',
                document_evidence=document_evidence,
                specific_variables=specific_variables
            )
            
        except Exception as e:
            print(f"Error parsing surrender response: {e}")
            return None
    
    def _parse_formula_response(self, response_text: str, formula_name: str) -> Optional[ExtractedFormula]:
        """Parse general formula response"""
        
        try:
            # Extract formula
            formula_match = re.search(r'FORMULA:\s*(.+?)(?=\nSPECIFIC_VARIABLES|$)', response_text, re.DOTALL | re.IGNORECASE)
            formula_expression = formula_match.group(1).strip() if formula_match else "Formula not found"
            
            # Extract specific variables
            variables_match = re.search(r'SPECIFIC_VARIABLES:\s*(.+?)(?=\nDOCUMENT_EVIDENCE|$)', response_text, re.DOTALL | re.IGNORECASE)
            specific_vars_str = variables_match.group(1).strip() if variables_match else ""
            specific_variables = self._parse_specific_variables(specific_vars_str)
            
            # Extract document evidence
            evidence_match = re.search(r'DOCUMENT_EVIDENCE:\s*(.+?)(?=\nCONTEXT|$)', response_text, re.DOTALL | re.IGNORECASE)
            document_evidence = evidence_match.group(1).strip() if evidence_match else "No supporting text found"
            
            # Extract context
            context_match = re.search(r'CONTEXT:\s*(.+?)(?=\nMETHOD|$)', response_text, re.DOTALL | re.IGNORECASE)
            business_context = context_match.group(1).strip() if context_match else f"Calculation for {formula_name}"
            
            # Extract method
            method_match = re.search(r'METHOD:\s*(.+?)(?=\nCONFIDENCE|$)', response_text, re.IGNORECASE)
            method = method_match.group(1).strip() if method_match else "UNKNOWN"
            
            # Extract confidence
            confidence_match = re.search(r'CONFIDENCE:\s*([0-9]*\.?[0-9]+)', response_text, re.IGNORECASE)
            confidence = float(confidence_match.group(1)) if confidence_match else 0.3
            
            return ExtractedFormula(
                formula_name=formula_name,
                formula_expression=formula_expression,
                variants_info=f"Extraction method: {method}",
                business_context=business_context,
                confidence=confidence,
                source_method='document_extraction',
                document_evidence=document_evidence,
                specific_variables=specific_variables
            )
            
        except Exception as e:
            print(f"Error parsing formula response for {formula_name}: {e}")
            return None
    
    def _parse_specific_variables(self, variables_str: str) -> Dict[str, str]:
        """Parse specific variables from comma-separated string"""
        
        specific_variables = {}
        if variables_str:
            # Split by comma and clean up
            var_names = [var.strip() for var in variables_str.split(',')]
            
            # Get descriptions from INPUT_VARIABLES
            for var_name in var_names:
                if var_name in self.input_variables:
                    specific_variables[var_name] = self.input_variables[var_name]
                elif var_name in self.basic_derived:
                    specific_variables[var_name] = self.basic_derived[var_name]
                else:
                    # Handle case where variable might not be in our predefined list
                    specific_variables[var_name] = f"Variable used in calculation: {var_name}"
        
        return specific_variables
    
    def _explain_no_extraction(self) -> DocumentExtractionResult:
        """Explain that extraction cannot be performed without API key"""
        
        return DocumentExtractionResult(
            input_variables=self.input_variables,
            basic_derived_formulas=self.basic_derived,
            extracted_formulas=[],
            extraction_summary="Cannot extract formulas from document - GEMINI_API_KEY required for document analysis. This system extracts formulas directly from insurance policy documents, especially surrender value calculations.",
            overall_confidence=0.0,
            surrender_formula_found=False
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
        "service": "Document-Based Formula Extractor",
        "version": "7.1",
        "api_key_configured": not MOCK_MODE,
        "supported_formats": list(ALLOWED_EXTENSIONS),
        "input_variables": len(INPUT_VARIABLES),
        "target_outputs": len(TARGET_OUTPUT_VARIABLES),
        "features": [
            "Extract formulas from document content only",
            "No hardcoded formulas",
            "Special focus on surrender value calculations",
            "Document evidence tracking",
            "Confidence scoring based on document clarity",
            "Formula-specific variable identification"
        ],
        "note": "Requires GEMINI_API_KEY for document analysis"
    })

@app.route('/input-variables', methods=['GET'])
def get_input_variables():
    """Get the defined input variables"""
    return jsonify({
        "input_variables": INPUT_VARIABLES,
        "basic_derived_formulas": BASIC_DERIVED_FORMULAS,
        "count": len(INPUT_VARIABLES)
    })

@app.route('/target-formulas', methods=['GET'])
def get_target_formulas():
    """Get the target output formulas"""
    return jsonify({
        "target_formulas": TARGET_OUTPUT_VARIABLES,
        "count": len(TARGET_OUTPUT_VARIABLES),
        "surrender_focus": "surrender_value is the primary focus",
        "note": "All formulas must be extracted from input documents"
    })

@app.route('/upload', methods=['POST'])
def upload_file():
    """Document-based formula extraction endpoint"""
    try:
        print("📋 Starting document-based formula extraction...")
        
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

        # Secure filename
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

        # Determine status
        if not MOCK_MODE and extraction_result.extracted_formulas:
            message = f"Successfully extracted {len(extraction_result.extracted_formulas)} formulas from document."
            status = "success"
        elif not MOCK_MODE and not extraction_result.extracted_formulas:
            message = "Document processed but no clear formulas found. Document may not contain explicit calculations."
            status = "warning"
        else:
            message = "API key required for document analysis. Please configure GEMINI_API_KEY."
            status = "error"

        # Convert extracted formulas to the format expected by frontend
        frontend_formulas = []
        for formula in extraction_result.extracted_formulas:
            frontend_formulas.append({
                "term_description": formula.formula_name,
                "mathematical_relationship": formula.formula_expression,
                "business_context": formula.business_context,
                "formula_explanation": formula.document_evidence,
                "confidence": formula.confidence,
                "reasoning_steps": [formula.variants_info],
                "variables_explained": formula.specific_variables,  # Now formula-specific!
                "source_method": formula.source_method
            })

        # Format response in the structure expected by Angular frontend
        return jsonify({
            "message": message,
            "formulas": frontend_formulas,  # This is what Angular expects
            "status": status,
            "file_type": os.path.splitext(filename)[1].lower(),
            "extraction_method": "Document-based analysis",
            "total_formulas": len(frontend_formulas),
            # Additional metadata (optional)
            "surrender_formula_found": extraction_result.surrender_formula_found,
            "api_key_configured": not MOCK_MODE,
            "extraction_approach": "Document-based analysis",
            "no_hardcoded_formulas": True,
            "extraction_result": extraction_result.to_dict()  # Keep original for debugging
        }), 200
        
    except Exception as e:
        print(f"❌ Upload processing failed: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            "message": f"Processing failed: {str(e)}",
            "status": "error",
            "formulas": []
        }), 500
@app.route('/forward-formulas', methods=['POST'])
def forward_formulas():
    try:
        data = request.get_json()
        response = requests.post("http://127.0.0.1:5001/store-formulas", json=data)
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"message": f"Forwarding failed: {str(e)}"}), 500


@app.route('/test-extraction', methods=['POST'])
def test_extraction():
    """Test endpoint for document-based extraction"""
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({"error": "No text provided"}), 400
        
        text = data['text']
        extraction_result = document_extractor.extract_formulas_from_document(text)
        
        return jsonify({
            "input_text_preview": text[:500] + "..." if len(text) > 500 else text,
            "extraction_method": "Document Analysis",
            "extraction_result": extraction_result.to_dict(),
            "api_key_configured": not MOCK_MODE,
            "surrender_formula_found": extraction_result.surrender_formula_found,
            "total_formulas": len(extraction_result.extracted_formulas)
        })
    except Exception as e:
        print(f"❌ Test endpoint failed: {e}")
        return jsonify({"error": str(e)}), 500

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
    print("📋 Starting Document-Based Formula Extractor")
    print(f"🔧 API Key Configured: {'YES' if not MOCK_MODE else 'NO'}")
    print("🌐 Server will run on http://127.0.0.1:5000")
    print("📁 Supported formats:", ', '.join(ALLOWED_EXTENSIONS))
    print(f"📊 Input variables: {len(INPUT_VARIABLES)}")
    print(f"🎯 Target formulas: {len(TARGET_OUTPUT_VARIABLES)}")
    print("✅ Document-based extraction: NO hardcoded formulas")
    print("🎯 Special focus: Surrender value calculations")
    print("💡 Set GEMINI_API_KEY environment variable to enable extraction")
    
    # Run with proper configuration
    app.run(
        host='127.0.0.1',
        port=5000,
        debug=True,
        threaded=True
    )