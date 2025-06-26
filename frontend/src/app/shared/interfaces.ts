// src/app/shared/interfaces.ts

export interface ExtractedFormula {
  id: string;
  term_description: string;
  mathematical_relationship: string;
  business_context: string;
  formula_explanation: string;
  confidence: number;
  reasoning_steps: string[];
  variables_explained: { [key: string]: string };
  source_method: string;
  variant_specific?: boolean;
  applicable_variants?: string[];
  editable?: boolean;
}

export interface BackendResponse {
  message: string;
  formulas: ExtractedFormula[];
  status: 'success' | 'warning' | 'error';
  file_type?: string;
  extraction_method?: string;
  total_formulas?: number;
  variants_detected?: string[];
  input_variables?: { [key: string]: string };
  output_variables?: string[];
  api_key_configured?: boolean;
}

export interface GenericTermsResponse {
  generic_terms: { [key: string]: string };
  count: number;
}

export interface SaveFormulaData {
  formulas: ExtractedFormula[];
  input_variables: { [key: string]: string };
  output_variables: string[];
  variants_detected: string[];
}

export interface SupportedFormatsResponse {
  supported_formats: string[];
  api_key_configured: boolean;
}

export interface InputVariables {
  [key: string]: string; // variable name -> description
}

export interface FormulaResult {
  title: string;
  expression: string;
  confidence: 'high' | 'medium' | 'low';
  variables: { [key: string]: string };
}

export interface ExcelExportData {
  'Formula ID': string;
  'Term Description': string;
  'Mathematical Relationship': string;
  'Business Context': string;
  'Formula Explanation': string;
  'Confidence Score': string;
  'Variables': string;
  'Source Method': string;
  'Variant Specific': string;
  'Applicable Variants': string;
  'Editable': string;
}