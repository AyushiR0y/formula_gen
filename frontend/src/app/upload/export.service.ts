// src/app/upload/export.service.ts
import { Injectable } from '@angular/core';
import { saveAs } from 'file-saver';
import * as XLSX from 'xlsx';
import { ExtractedFormula, ExcelExportData } from '../shared/interfaces';

@Injectable({
  providedIn: 'root'
})
export class ExportService {

  exportFormulasToExcel(
    formulas: ExtractedFormula[],
    inputVariables: { [key: string]: string },
    outputVariables: string[]
  ): void {
    const workbook = XLSX.utils.book_new();

    // Create main formulas sheet
    this.addFormulasSheet(workbook, formulas);
    
    // Create input variables sheet
    this.addInputVariablesSheet(workbook, inputVariables);
    
    // Create output variables sheet
    this.addOutputVariablesSheet(workbook, outputVariables);

    // Generate and save file
    this.saveWorkbook(workbook);
  }

  private addFormulasSheet(workbook: XLSX.WorkBook, formulas: ExtractedFormula[]): void {
    const excelData: ExcelExportData[] = formulas.map(formula => ({
      'Formula ID': formula.id,
      'Term Description': formula.term_description,
      'Mathematical Relationship': formula.mathematical_relationship,
      'Business Context': formula.business_context,
      'Formula Explanation': formula.formula_explanation,
      'Confidence Score': (formula.confidence * 100).toFixed(1) + '%',
      'Variables': this.formatVariablesForExcel(formula.variables_explained),
      'Source Method': formula.source_method,
      'Variant Specific': formula.variant_specific ? 'Yes' : 'No',
      'Applicable Variants': formula.applicable_variants?.join(', ') || 'All',
      'Editable': formula.editable ? 'Yes' : 'No'
    }));

    const worksheet = XLSX.utils.json_to_sheet(excelData);
    this.setColumnWidths(worksheet);
    XLSX.utils.book_append_sheet(workbook, worksheet, 'Formula Analysis');
  }

  private addInputVariablesSheet(workbook: XLSX.WorkBook, inputVariables: { [key: string]: string }): void {
    const inputVarsData = Object.entries(inputVariables).map(([key, value]) => ({
      'Variable Name': key,
      'Description': value
    }));
    
    const inputVarsSheet = XLSX.utils.json_to_sheet(inputVarsData);
    XLSX.utils.book_append_sheet(workbook, inputVarsSheet, 'Input Variables');
  }

  private addOutputVariablesSheet(workbook: XLSX.WorkBook, outputVariables: string[]): void {
    const outputVarsData = outputVariables.map(varName => ({
      'Variable Name': varName
    }));
    
    const outputVarsSheet = XLSX.utils.json_to_sheet(outputVarsData);
    XLSX.utils.book_append_sheet(workbook, outputVarsSheet, 'Output Variables');
  }

  private formatVariablesForExcel(variables: { [key: string]: string }): string {
    return Object.entries(variables)
      .map(([key, value]) => `${key}: ${value}`)
      .join(' | ');
  }

  private setColumnWidths(worksheet: XLSX.WorkSheet): void {
    const colWidths = [
      { wch: 15 }, // Formula ID
      { wch: 25 }, // Term Description
      { wch: 40 }, // Mathematical Relationship
      { wch: 35 }, // Business Context
      { wch: 50 }, // Formula Explanation
      { wch: 15 }, // Confidence Score
      { wch: 60 }, // Variables
      { wch: 20 }, // Source Method
      { wch: 15 }, // Variant Specific
      { wch: 25 }, // Applicable Variants
      { wch: 10 }, // Editable
    ];
    worksheet['!cols'] = colWidths;
  }

  private saveWorkbook(workbook: XLSX.WorkBook): void {
    const excelBuffer = XLSX.write(workbook, { bookType: 'xlsx', type: 'array' });
    const blob = new Blob([excelBuffer], { type: 'application/octet-stream' });
    
    const timestamp = new Date().toISOString().split('T')[0];
    saveAs(blob, `enhanced_formula_analysis_${timestamp}.xlsx`);
  }

  exportFormulasToJson(
    formulas: ExtractedFormula[],
    inputVariables: { [key: string]: string },
    outputVariables: string[]
  ): void {
    const exportData = {
      metadata: {
        export_date: new Date().toISOString(),
        total_formulas: formulas.length,
        input_variables_count: Object.keys(inputVariables).length,
        output_variables_count: outputVariables.length
      },
      formulas,
      input_variables: inputVariables,
      output_variables: outputVariables
    };

    const jsonString = JSON.stringify(exportData, null, 2);
    const blob = new Blob([jsonString], { type: 'application/json' });
    
    const timestamp = new Date().toISOString().split('T')[0];
    saveAs(blob, `formula_analysis_${timestamp}.json`);
  }

  exportFormulasCsv(formulas: ExtractedFormula[]): void {
    const csvData = formulas.map(formula => ({
      id: formula.id,
      term_description: formula.term_description,
      mathematical_relationship: formula.mathematical_relationship,
      business_context: formula.business_context,
      formula_explanation: formula.formula_explanation,
      confidence: (formula.confidence * 100).toFixed(1) + '%',
      variables_explained: this.formatVariablesForCsv(formula.variables_explained),
      source_method: formula.source_method,
      variant_specific: formula.variant_specific ? 'Yes' : 'No',
      applicable_variants: formula.applicable_variants?.join(';') || 'All',
      editable: formula.editable ? 'Yes' : 'No'
    }));

    const worksheet = XLSX.utils.json_to_sheet(csvData);
    const csvOutput = XLSX.utils.sheet_to_csv(worksheet);
    const blob = new Blob([csvOutput], { type: 'text/csv;charset=utf-8;' });
    
    const timestamp = new Date().toISOString().split('T')[0];
    saveAs(blob, `formula_analysis_${timestamp}.csv`);
  }

  private formatVariablesForCsv(variables: { [key: string]: string }): string {
    return Object.entries(variables)
      .map(([key, value]) => `${key}: ${value}`)
      .join('; ');
  }

  exportSummaryReport(
    formulas: ExtractedFormula[],
    inputVariables: { [key: string]: string },
    outputVariables: string[]
  ): void {
    const report = this.generateSummaryReport(formulas, inputVariables, outputVariables);
    const blob = new Blob([report], { type: 'text/plain;charset=utf-8;' });
    
    const timestamp = new Date().toISOString().split('T')[0];
    saveAs(blob, `formula_analysis_summary_${timestamp}.txt`);
  }

  private generateSummaryReport(
    formulas: ExtractedFormula[],
    inputVariables: { [key: string]: string },
    outputVariables: string[]
  ): string {
    const totalFormulas = formulas.length;
    const avgConfidence = formulas.reduce((sum, f) => sum + f.confidence, 0) / totalFormulas;
    const sourceMethods = [...new Set(formulas.map(f => f.source_method))];
    const variantSpecificCount = formulas.filter(f => f.variant_specific).length;
    const editableCount = formulas.filter(f => f.editable).length;

    const report = `
FORMULA ANALYSIS SUMMARY REPORT
Generated: ${new Date().toISOString()}

OVERVIEW
========
Total Formulas Analyzed: ${totalFormulas}
Input Variables: ${Object.keys(inputVariables).length}
Output Variables: ${outputVariables.length}
Average Confidence Score: ${(avgConfidence * 100).toFixed(1)}%

FORMULA BREAKDOWN
================
Variant-Specific Formulas: ${variantSpecificCount} (${((variantSpecificCount / totalFormulas) * 100).toFixed(1)}%)
Editable Formulas: ${editableCount} (${((editableCount / totalFormulas) * 100).toFixed(1)}%)

SOURCE METHODS
==============
${sourceMethods.map(method => `- ${method}`).join('\n')}

CONFIDENCE DISTRIBUTION
======================
High Confidence (>80%): ${formulas.filter(f => f.confidence > 0.8).length}
Medium Confidence (50-80%): ${formulas.filter(f => f.confidence >= 0.5 && f.confidence <= 0.8).length}
Low Confidence (<50%): ${formulas.filter(f => f.confidence < 0.5).length}

INPUT VARIABLES
===============
${Object.entries(inputVariables).map(([key, value]) => `${key}: ${value}`).join('\n')}

OUTPUT VARIABLES
================
${outputVariables.map(varName => `- ${varName}`).join('\n')}

DETAILED FORMULAS
=================
${formulas.map((formula, index) => `
${index + 1}. ${formula.term_description}
   ID: ${formula.id}
   Mathematical Relationship: ${formula.mathematical_relationship}
   Business Context: ${formula.business_context}
   Confidence: ${(formula.confidence * 100).toFixed(1)}%
   Source Method: ${formula.source_method}
   Variant Specific: ${formula.variant_specific ? 'Yes' : 'No'}
   Applicable Variants: ${formula.applicable_variants?.join(', ') || 'All'}
   Variables: ${Object.entries(formula.variables_explained).map(([k, v]) => `${k} (${v})`).join(', ')}
`).join('\n')}
    `.trim();

    return report;
  }
}