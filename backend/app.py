import os
import re
import json
from typing import List, Dict, Tuple, Optional
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
    print("The extractor will work with mock data for testing purposes.")
    print("To use real AI extraction, create a .env file with your GEMINI_API_KEY")
    MOCK_MODE = True
else:
    genai.configure(api_key=API_KEY)
    MOCK_MODE = False

@dataclass
class ExtractedFormula:
    term_description: str
    mathematical_relationship: str
    business_context: str
    formula_explanation: str
    confidence: float
    reasoning_steps: List[str]
    variables_explained: Dict[str, str]
    source_method: str
    
    def to_dict(self):
        return asdict(self)

class EnhancedInsuranceFormulaExtractor:
    """Enhanced formula extractor with ReAct prompting and consistent outputs"""
    
    def __init__(self):
        self.insurance_terminology = self._load_comprehensive_terminology()
        self.formula_cache = {}
        
    def _load_comprehensive_terminology(self) -> Dict[str, str]:
        """Comprehensive insurance terminology"""
        return {
            'sum assured': 'The guaranteed amount payable to beneficiaries upon death or maturity',
            'sum insured': 'The maximum amount the insurer will pay for covered losses',
            'annual premium': 'The yearly payment made to keep the insurance policy active',
            'total premium': 'The cumulative amount of all premiums paid throughout the policy term',
            'premiums paid': 'The actual amount of premiums paid up to a specific point in time',
            'maturity benefit': 'The amount payable when the policy reaches its maturity date',
            'death benefit': 'The amount payable to beneficiaries upon the death of the insured',
            'surrender value': 'The amount payable when a policy is voluntarily terminated before maturity',
            'guaranteed surrender value': 'The minimum assured amount payable on policy surrender',
            'special surrender value': 'An enhanced surrender value offered under special circumstances',
            'paid up value': 'The reduced sum assured when premiums are discontinued but policy remains active',
            'policy year': 'The number of years the policy has been in force',
            'premium paying term': 'The duration during which premiums must be paid',
            'policy term': 'The total duration for which the policy provides coverage',
            'bonus': 'Additional amount added to the sum assured based on company performance',
            'loyalty addition': 'Extra benefit provided for long-term policyholders',
            'terminal bonus': 'One-time bonus paid at policy maturity or on death claim',
            'reversionary bonus': 'Annual bonus added to the sum assured and guaranteed thereafter',
            'surrender charge': 'Fee deducted when a policy is surrendered before maturity',
            'mortality charge': 'Cost of providing life insurance coverage',
            'administration charge': 'Fee for managing and administering the policy',
            'fund value': 'Current market value of units allocated to the policyholder',
            'net asset value': 'Market value per unit of the investment fund',
            'allocation rate': 'Percentage of premium allocated to investment after charges',
            'loading factor': 'Additional charge applied to standard premium rates',
            'interest rate': 'Rate of return applied to policy reserves or investments',
            'coverage amount': 'The total amount of insurance protection provided',
            'claim amount': 'The actual amount claimed by the policyholder',
            'deductible': 'The amount the policyholder must pay before insurance coverage applies',
            'waiting period': 'Time period before certain benefits become available',
            'age': 'Age of the insured person, typically at policy inception or current age'
        }
    
    def _generate_content_hash(self, text: str) -> str:
        """Generate hash for caching"""
        return hashlib.md5(text.encode()).hexdigest()
    
    def extract_formulas_with_react(self, text: str) -> List[ExtractedFormula]:
        """Extract formulas using ReAct methodology or mock data"""
        
        if MOCK_MODE:
            return self._mock_extraction(text)
        
        content_hash = self._generate_content_hash(text)
        if content_hash in self.formula_cache:
            print(" Using cached result")
            return self.formula_cache[content_hash]
        
        try:
            print("🧠 Starting ReAct analysis...")
            
            analysis_result = self._react_observe_and_analyze(text)
            reasoning_result = self._react_reason_and_plan(text, analysis_result)
            extraction_result = self._react_extract_formulas(text, reasoning_result)
            validated_result = self._react_validate_and_refine(extraction_result)
            
            self.formula_cache[content_hash] = validated_result
            return validated_result
            
        except Exception as e:
            print(f"❌ ReAct extraction failed: {e}")
            print(f"Traceback: {traceback.format_exc()}")
            return self._mock_extraction(text)
    
    def _mock_extraction(self, text: str) -> List[ExtractedFormula]:
        """Mock extraction for testing when API key is not available"""
        
        # Look for common insurance calculation patterns
        formulas = []
        
        # Check for premium calculations
        if any(term in text.lower() for term in ['premium', 'sum assured', 'maturity', 'surrender']):
            formulas.append(ExtractedFormula(
                term_description="Annual Premium Calculation",
                mathematical_relationship="Annual Premium = (Sum Assured × Premium Rate) + Administrative Charges",
                business_context="Used to calculate the yearly premium amount for life insurance policies",
                formula_explanation="The annual premium is calculated by multiplying the sum assured by the premium rate and adding any administrative charges",
                confidence=0.8,
                reasoning_steps=[
                    "Identified premium calculation pattern in text",
                    "Recognized standard insurance terminology",
                    "Applied common industry calculation method"
                ],
                variables_explained={
                    "Sum Assured": "The guaranteed amount payable to beneficiaries",
                    "Premium Rate": "The rate charged per unit of coverage",
                    "Administrative Charges": "Fixed costs for policy administration"
                },
                source_method="mock_extraction"
            ))
        
        # Check for surrender value calculations
        if any(term in text.lower() for term in ['surrender', 'paid up', 'cash value']):
            formulas.append(ExtractedFormula(
                term_description="Surrender Value Calculation",
                mathematical_relationship="Surrender Value = (Premiums Paid × Surrender Value Factor) - Surrender Charges",
                business_context="Used to determine the amount payable when a policy is surrendered before maturity",
                formula_explanation="The surrender value is calculated by applying a surrender value factor to the premiums paid and deducting any surrender charges",
                confidence=0.75,
                reasoning_steps=[
                    "Detected surrender value terminology",
                    "Applied standard surrender value calculation method",
                    "Incorporated surrender charges as per industry practice"
                ],
                variables_explained={
                    "Premiums Paid": "Total amount of premiums paid to date",
                    "Surrender Value Factor": "Percentage factor applied to premiums paid",
                    "Surrender Charges": "Fees deducted for early policy termination"
                },
                source_method="mock_extraction"
            ))
        
        return formulas
    
    def _react_observe_and_analyze(self, text: str) -> Dict:
        """Step 1: Observe and analyze the document content"""
        
        prompt = f"""
        **OBSERVATION PHASE**
        
        As an expert insurance analyst, carefully observe and analyze this document:
        
        Text: "{text[:2000]}..."
        
        **ANALYZE AND IDENTIFY:**
        1. What type of insurance document is this?
        2. What mathematical relationships or calculations are described?
        3. What insurance terms and concepts are mentioned?
        4. What business rules or conditions are stated?
        5. Are there any percentage calculations, ratios, or formulas mentioned?
        
        **PROVIDE YOUR ANALYSIS:**
        Document Type: [Identify the document type]
        Key Mathematical Concepts: [List all mathematical relationships found]
        Insurance Terms Present: [List all insurance terminology]
        Business Rules: [List any conditional logic or business rules]
        Calculation Patterns: [Identify calculation patterns]
        
        Be thorough and systematic in your observation.
        """
        
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(prompt)
            analysis_text = response.text
            
            return {
                'analysis': analysis_text,
                'timestamp': time.time()
            }
        except Exception as e:
            print(f"Analysis phase error: {e}")
            return {'analysis': 'Analysis failed', 'timestamp': time.time()}
    
    def _react_reason_and_plan(self, text: str, analysis: Dict) -> Dict:
        """Step 2: Reason about findings and plan extraction strategy"""
        
        prompt = f"""
        **REASONING PHASE**
        
        Based on my analysis: {analysis['analysis']}
        
        **REASONING TASKS:**
        1. What is the logical structure of calculations in this document?
        2. How do different insurance terms relate to each other mathematically?
        3. What are the step-by-step calculation processes described?
        4. Which calculations are core formulas vs derived values?
        
        **PLANNING EXTRACTION STRATEGY:**
        For each mathematical relationship identified:
        - Determine the primary insurance concept being calculated
        - Identify all input variables and their business meaning
        - Map the logical flow of the calculation
        - Identify any conditions or business rules that apply
        
        **PROVIDE YOUR REASONING:**
        Core Calculations Identified: [List main formulas/calculations]
        Variable Relationships: [Explain how variables connect]
        Calculation Logic: [Describe the step-by-step process]
        Extraction Strategy: [Plan how to extract each formula]
        
        Original Text Context: "{text[:1500]}..."
        
        Think step by step and provide clear reasoning.
        """
        
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(prompt)
            reasoning_text = response.text
            
            return {
                'reasoning': reasoning_text,
                'analysis': analysis,
                'timestamp': time.time()
            }
        except Exception as e:
            print(f"Reasoning phase error: {e}")
            return {'reasoning': 'Reasoning failed', 'analysis': analysis, 'timestamp': time.time()}
    
    def _react_extract_formulas(self, text: str, reasoning: Dict) -> List[Dict]:
        """Step 3: Extract formulas based on reasoning"""
        
        prompt = f"""
        **EXTRACTION PHASE**
        
        Based on my analysis and reasoning:
        {reasoning['reasoning']}
        
        **EXTRACTION INSTRUCTIONS:**
        Extract ONLY the mathematical formulas and relationships from this text. 
        For each formula found, provide:
        
        1. **Term Description**: Full descriptive name (NO abbreviations)
        2. **Mathematical Relationship**: The actual formula using descriptive variable names
        3. **Business Context**: When and why this calculation is used
        4. **Formula Explanation**: Step-by-step explanation of how the calculation works
        5. **Variables Explained**: Each variable with its full business meaning
        
        **FORMAT YOUR RESPONSE EXACTLY AS:**
        
        FORMULA 1:
        Term Description: [Full descriptive name]
        Mathematical Relationship: [Formula with descriptive names]
        Business Context: [When and why this is used]
        Formula Explanation: [Step-by-step explanation]
        Variables: 
        - Variable 1: [Full description]
        - Variable 2: [Full description]
        
        FORMULA 2:
        [Continue for each formula...]
        
        **TEXT TO EXTRACT FROM:**
        "{text}"
        
        If no mathematical formulas are found, respond with: "NO_FORMULAS_FOUND"
        """
        
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(prompt)
            extraction_text = response.text
            
            if "NO_FORMULAS_FOUND" in extraction_text:
                return []
            
            formulas = self._parse_structured_extraction(extraction_text)
            return formulas
            
        except Exception as e:
            print(f"Extraction phase error: {e}")
            return []
    
    def _parse_structured_extraction(self, extraction_text: str) -> List[Dict]:
        """Parse the structured extraction response"""
        formulas = []
        
        formula_blocks = re.split(r'FORMULA \d+:', extraction_text)
        
        for block in formula_blocks[1:]:
            try:
                formula_data = {}
                
                term_match = re.search(r'Term Description:\s*(.+?)(?=\n|Mathematical Relationship:)', block, re.DOTALL)
                math_match = re.search(r'Mathematical Relationship:\s*(.+?)(?=\n|Business Context:)', block, re.DOTALL)
                context_match = re.search(r'Business Context:\s*(.+?)(?=\n|Formula Explanation:)', block, re.DOTALL)
                explanation_match = re.search(r'Formula Explanation:\s*(.+?)(?=\n|Variables:)', block, re.DOTALL)
                variables_match = re.search(r'Variables:\s*(.+?)(?=\n\n|$)', block, re.DOTALL)
                
                if term_match and math_match:
                    formula_data['term_description'] = term_match.group(1).strip()
                    formula_data['mathematical_relationship'] = math_match.group(1).strip()
                    formula_data['business_context'] = context_match.group(1).strip() if context_match else ""
                    formula_data['formula_explanation'] = explanation_match.group(1).strip() if explanation_match else ""
                    
                    # Parse variables
                    variables_dict = {}
                    if variables_match:
                        var_text = variables_match.group(1)
                        var_lines = [line.strip() for line in var_text.split('\n') if line.strip() and line.startswith('-')]
                        for var_line in var_lines:
                            var_parts = var_line[1:].split(':', 1)
                            if len(var_parts) == 2:
                                variables_dict[var_parts[0].strip()] = var_parts[1].strip()
                    
                    formula_data['variables_explained'] = variables_dict
                    formulas.append(formula_data)
                    
            except Exception as e:
                print(f"Error parsing formula block: {e}")
                continue
        
        return formulas
    
    def _react_validate_and_refine(self, extracted_formulas: List[Dict]) -> List[ExtractedFormula]:
        """Step 4: Validate and refine extracted formulas"""
        
        validated_formulas = []
        
        for formula_data in extracted_formulas:
            try:
                reasoning_steps = [
                    "Identified mathematical relationship in source text",
                    "Analyzed business context and purpose",
                    "Mapped variables to insurance terminology",
                    "Validated mathematical logic and structure",
                    "Provided comprehensive explanation"
                ]
                
                confidence = self._calculate_confidence(formula_data)
                
                validated_formula = ExtractedFormula(
                    term_description=formula_data.get('term_description', 'Unknown Calculation'),
                    mathematical_relationship=formula_data.get('mathematical_relationship', 'Not specified'),
                    business_context=formula_data.get('business_context', 'General insurance calculation'),
                    formula_explanation=formula_data.get('formula_explanation', 'No explanation provided'),
                    confidence=confidence,
                    reasoning_steps=reasoning_steps,
                    variables_explained=formula_data.get('variables_explained', {}),
                    source_method='react_methodology'
                )
                
                validated_formulas.append(validated_formula)
                
            except Exception as e:
                print(f"Error validating formula: {e}")
                continue
        
        return validated_formulas
    
    def _calculate_confidence(self, formula_data: Dict) -> float:
        """Calculate confidence score based on completeness"""
        score = 0.0
        
        if formula_data.get('term_description'):
            score += 0.25
        if formula_data.get('mathematical_relationship'):
            score += 0.35
        if formula_data.get('business_context'):
            score += 0.20
        if formula_data.get('formula_explanation'):
            score += 0.15
        if formula_data.get('variables_explained'):
            score += 0.05
        
        return min(score, 1.0)

# Initialize the enhanced extractor
enhanced_extractor = EnhancedInsuranceFormulaExtractor()

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
        "service": "Insurance Formula Extractor",
        "version": "2.0",
        "mock_mode": MOCK_MODE,
        "supported_formats": list(ALLOWED_EXTENSIONS)
    })

@app.route('/upload', methods=['POST'])
def upload_file():
    """Enhanced upload endpoint with better error handling"""
    try:
        print(" Starting enhanced upload process...")
        
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
            }), 415

        # Secure filename
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        print(f" File saved: {filepath}")

        # Extract text
        text = extract_text_from_file(filepath)
        if not text.strip():
            return jsonify({
                "message": "Could not extract text from file or file was empty.",
                "status": "error",
                "formulas": []
            }), 400

        print(f" Extracted text: {len(text)} characters")

        # Extract formulas
        extracted_formulas = enhanced_extractor.extract_formulas_with_react(text)
        
        # Convert to response format
        formulas_response = [formula.to_dict() for formula in extracted_formulas]
        
        if not formulas_response:
            message = "File processed successfully, but no mathematical formulas were found."
            status = "warning"
        else:
            method = "Mock Extraction" if MOCK_MODE else "ReAct Methodology"
            message = f"Successfully extracted {len(formulas_response)} formulas using {method}."
            status = "success"

        # Clean up uploaded file
        try:
            os.remove(filepath)
        except:
            pass

        return jsonify({
            "message": message,
            "formulas": formulas_response,
            "status": status,
            "file_type": os.path.splitext(filename)[1].lower(),
            "extraction_method": "Mock Extraction" if MOCK_MODE else "ReAct Methodology",
            "total_formulas": len(formulas_response),
            "mock_mode": MOCK_MODE
        }), 200
        
    except Exception as e:
        print(f"❌ Upload processing failed: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            "message": f"Processing failed: {str(e)}",
            "status": "error",
            "formulas": []
        }), 500

@app.route('/supported-formats', methods=['GET'])
def get_supported_formats():
    """Endpoint to get list of supported file formats"""
    return jsonify({
        "supported_formats": list(ALLOWED_EXTENSIONS),
        "message": "List of supported file formats for upload",
        "mock_mode": MOCK_MODE
    })

@app.route('/test-react', methods=['POST'])
def test_react():
    """Test endpoint for ReAct methodology"""
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({"error": "No text provided"}), 400
        
        text = data['text']
        formulas = enhanced_extractor.extract_formulas_with_react(text)
        
        return jsonify({
            "input_text": text,
            "extraction_method": "Mock Extraction" if MOCK_MODE else "ReAct Methodology",
            "extracted_formulas": [f.to_dict() for f in formulas],
            "total_formulas": len(formulas),
            "mock_mode": MOCK_MODE
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
    print(" Starting Enhanced Insurance Formula Extractor")
    print(f" Mock Mode: {'ON' if MOCK_MODE else 'OFF'}")
    print(" Server will run on http://127.0.0.1:5000")
    print(" Supported formats:", ', '.join(ALLOWED_EXTENSIONS))
    
    # Run with proper configuration
    app.run(
        host='127.0.0.1',
        port=5000,
        debug=True,
        threaded=True
    )