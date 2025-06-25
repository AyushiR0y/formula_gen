import os
import pandas as pd
import numpy as np
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
import traceback
import re
import math
from typing import List, Dict, Any

app = Flask(__name__)
CORS(app, origins=["http://localhost:4200", "http://127.0.0.1:4200"])

UPLOAD_FOLDER = 'data_uploads'
PROCESSED_FOLDER = 'processed_files'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROCESSED_FOLDER'] = PROCESSED_FOLDER
ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}

# Global storage for formulas
dynamic_formulas: List[Dict] = []

VARIANT_MAP = {
    'L190A01': 'Variant 1',
    'LI90B01': 'Variant 2', 'LI90B02': 'Variant 2',
    'L190C01': 'Variant 3',
    'L190D01': 'Variant 4',
    'L190E01': 'Variant 5', 'L190E02': 'Variant 5',
    'L190F01': 'Variant 6'
}

@app.route('/store-formulas', methods=['POST'])
def store_formulas():
    global dynamic_formulas
    try:
        data = request.get_json()
        dynamic_formulas = data if isinstance(data, list) else []
        print(f"Stored {len(dynamic_formulas)} formulas")
        for i, formula in enumerate(dynamic_formulas):
            print(f"Formula {i+1}: {formula.get('term_description', 'Unknown')}")
            print(f"  Expression: {formula.get('mathematical_relationship', 'No expression')}")
        return jsonify({"message": "Stored extracted formulas", "count": len(dynamic_formulas)}), 200
    except Exception as e:
        print(f"Error storing formulas: {str(e)}")
        return jsonify({"error": str(e)}), 500

def clean_column_name(name: str) -> str:
    """Clean column name for consistent matching"""
    return str(name).strip().lower().replace(' ', '_').replace('%', 'percent').replace('*', '')

def prepare_context(row: pd.Series) -> Dict[str, float]:
    """Prepare context dictionary with cleaned column names"""
    context = {}
    for col, val in row.items():
        clean_col = clean_column_name(col)
        # Convert to numeric, default to 0 if not possible
        try:
            if pd.isna(val) or val == '' or val is None:
                context[clean_col] = 0.0
            else:
                context[clean_col] = float(val)
        except (ValueError, TypeError):
            context[clean_col] = 0.0
    
    # Add common mathematical functions to context
    context.update({
        'max': max,
        'min': min,
        'abs': abs,
        'round': round,
        'sqrt': math.sqrt,
        'exp': math.exp,
        'log': math.log,
        'sin': math.sin,
        'cos': math.cos,
        'tan': math.tan,
        'pi': math.pi,
        'e': math.e
    })
    
    return context

def safe_eval(expr: str, context: dict) -> float:
    """Safely evaluate mathematical expressions"""
    try:
        if not expr or expr.strip() == '':
            return None
            
        # Clean the expression
        expr = str(expr).strip()
        
        # Handle common mathematical patterns
        expr = expr.replace('^', '**')  # Convert ^ to ** for power
        expr = expr.replace('×', '*')   # Convert × to *
        expr = expr.replace('÷', '/')   # Convert ÷ to /
        
        # Replace variable names with their values
        # Find all variable names (letters, underscores, numbers)
        pattern = re.compile(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b')
        
        def replace_var(match):
            var_name = match.group().lower()
            if var_name in context:
                return str(context[var_name])
            else:
                print(f"Warning: Variable '{var_name}' not found in context")
                return '0'  # Default to 0 for missing variables
        
        expr_with_values = pattern.sub(replace_var, expr)
        
        print(f"Evaluating: {expr} -> {expr_with_values}")
        
        # Evaluate the expression
        result = eval(expr_with_values, {"__builtins__": {}}, context)
        
        # Ensure result is numeric
        if isinstance(result, (int, float)) and not (math.isnan(result) or math.isinf(result)):
            return float(result)
        else:
            return None
            
    except Exception as e:
        print(f"Error evaluating expression '{expr}': {str(e)}")
        return None

@app.route('/process-data', methods=['POST'])
def process_data():
    global dynamic_formulas
    try:
        if 'file' not in request.files:
            return jsonify({"message": "No file uploaded."}), 400

        file = request.files['file']
        filename = secure_filename(file.filename)
        if not filename:
            return jsonify({"message": "Invalid file name."}), 400

        file_ext = filename.rsplit('.', 1)[1].lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            return jsonify({"message": f"Unsupported file type: {file_ext}"}), 415

        # Read the file
        try:
            if 'xls' in file_ext:
                df = pd.read_excel(file)
            else:
                df = pd.read_csv(file)
        except Exception as e:
            return jsonify({"message": f"Error reading file: {str(e)}"}), 400

        print(f"Original DataFrame shape: {df.shape}")
        print(f"Columns: {list(df.columns)}")

        # Clean column names
        df.columns = df.columns.str.strip()
        
        # Create a copy for processing
        filled_df = df.copy()
        
        processed = 0
        errors = []
        successful_calculations = 0
        
        print(f"Processing {len(df)} rows with {len(dynamic_formulas)} formulas")

        # Process each row
        for idx, row in df.iterrows():
            try:
                # Get cover code and variant
                cover_code = str(row.get('COVER_CODE', '')).strip()
                variant = VARIANT_MAP.get(cover_code)

                if not variant:
                    errors.append(f"Row {idx + 2}: Unknown COVER_CODE '{cover_code}'")
                    continue

                # Prepare context with current row values
                context = prepare_context(row)
                computed_this_row = {}

                print(f"\nProcessing row {idx + 2}, Cover Code: {cover_code}, Variant: {variant}")

                # Apply each formula
                for formula_idx, formula in enumerate(dynamic_formulas):
                    try:
                        term = formula.get('term_description', '').strip()
                        math_expr = formula.get('mathematical_relationship', '')
                        
                        # Check if formula has variant-specific expressions
                        variants = formula.get('variants', {})
                        if variants and variant in variants:
                            expr = variants[variant]
                        else:
                            expr = math_expr

                        if not expr:
                            continue

                        print(f"  Applying formula {formula_idx + 1}: {term}")
                        print(f"    Expression: {expr}")

                        # Update context with previously computed values
                        context.update(computed_this_row)

                        # Evaluate the formula
                        result = safe_eval(expr, context)

                        if result is not None:
                            # Create column name
                            col_name = clean_column_name(term)
                            
                            # Check if we should only fill missing values
                            original_col_name = None
                            for col in df.columns:
                                if clean_column_name(col) == col_name:
                                    original_col_name = col
                                    break
                            
                            # If column exists, only fill if value is missing/null
                            if original_col_name:
                                current_value = filled_df.loc[idx, original_col_name]
                                if pd.isna(current_value) or current_value == '' or current_value == 0:
                                    filled_df.loc[idx, original_col_name] = round(result, 2)
                                    print(f"    Filled missing value: {round(result, 2)}")
                                else:
                                    print(f"    Existing value kept: {current_value}")
                            else:
                                # Create new column
                                filled_df.loc[idx, col_name] = round(result, 2)
                                print(f"    Created new column: {col_name} = {round(result, 2)}")
                            
                            # Store for use in subsequent formulas
                            computed_this_row[col_name] = result
                            successful_calculations += 1
                            
                        else:
                            errors.append(f"Row {idx + 2}: Could not evaluate formula '{term}' with expression '{expr}'")
                            print(f"    Failed to evaluate: {expr}")

                    except Exception as formula_error:
                        error_msg = f"Row {idx + 2}, Formula '{term}': {str(formula_error)}"
                        errors.append(error_msg)
                        print(f"    Formula error: {str(formula_error)}")

                processed += 1

            except Exception as row_error:
                error_msg = f"Row {idx + 2}: {str(row_error)}"
                errors.append(error_msg)
                print(f"Row error: {str(row_error)}")

        # Generate output filename
        timestamp = pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')
        output_filename = f"processed_output_{timestamp}.xlsx"
        output_path = os.path.join(app.config['PROCESSED_FOLDER'], output_filename)
        
        # Save the processed file
        try:
            filled_df.to_excel(output_path, index=False)
            print(f"Saved processed file: {output_path}")
        except Exception as save_error:
            return jsonify({"message": f"Error saving file: {str(save_error)}"}), 500

        # Create summary
        result_summary = {
            "total_policies": len(df),
            "processed_policies": processed,
            "successful_calculations": successful_calculations,
            "error_count": len(errors),
            "warning_count": 0,
            "formulas_used": len(dynamic_formulas),
            "new_columns_created": len([col for col in filled_df.columns if col not in df.columns])
        }

        print(f"Processing complete: {result_summary}")

        return jsonify({
            "message": f"Processed {processed} policies with {successful_calculations} successful calculations.",
            "status": "success" if len(errors) == 0 else "warning",
            "download_ready": True,
            "output_filename": output_filename,
            "processing_result": {
                "processed_policies": processed,
                "successful_calculations": successful_calculations,
                "errors": errors[:10],  # Limit errors shown
                "warnings": [],
                "output_file_path": output_path,
                "processing_summary": result_summary,
                "total_errors": len(errors)
            }
        }), 200

    except Exception as e:
        print(f"Processing failed: {str(e)}")
        print(traceback.format_exc())
        return jsonify({
            "message": f"Processing failed: {str(e)}", 
            "status": "error"
        }), 500

@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    try:
        path = os.path.join(app.config['PROCESSED_FOLDER'], filename)
        if os.path.exists(path):
            return send_file(path, as_attachment=True, download_name=filename)
        else:
            return jsonify({"message": "File not found."}), 404
    except Exception as e:
        print(f"Download error: {str(e)}")
        return jsonify({"message": f"Download failed: {str(e)}"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy",
        "formulas_loaded": len(dynamic_formulas),
        "upload_folder": app.config['UPLOAD_FOLDER'],
        "processed_folder": app.config['PROCESSED_FOLDER']
    })

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "message": "Formula Processor API is running",
        "status": "ok",
        "formulas_loaded": len(dynamic_formulas),
        "endpoints": [
            "/store-formulas", 
            "/process-data", 
            "/download/<filename>",
            "/health"
        ]
    })

if __name__ == '__main__':
    print("🧮 Formula Processor running on http://127.0.0.1:5001")
    print("📁 Upload folder:", UPLOAD_FOLDER)
    print("📁 Processed folder:", PROCESSED_FOLDER)
    app.run(host='127.0.0.1', port=5001, debug=True)