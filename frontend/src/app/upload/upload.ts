// src/app/upload/upload.component.ts
import { Component, ChangeDetectionStrategy, ChangeDetectorRef } from '@angular/core';
import { Router } from '@angular/router';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClientModule } from '@angular/common/http';
import { UploadService } from './upload.service';
import { VariableService } from './variable.service';
import { ExportService } from './export.service';
import { ExtractedFormula, BackendResponse } from '../shared/interfaces';

@Component({
  selector: 'app-upload',
  standalone: true,
  imports: [CommonModule, HttpClientModule, FormsModule],
  providers: [UploadService, VariableService, ExportService], // Provide services here
  templateUrl: './upload.html',
  styleUrls: ['./upload.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush
})
export default class UploadComponent {
  // File handling
  selectedFile: File | null = null;
  uploadStatus = '';
  uploadProgress = 0;
  isLoading = false;
  supportedFormats: string[] = [];

  // Formula results
  formulas: ExtractedFormula[] = [];
  rawOutput = '';
  showRawOutput = false;
  extractionMethod = '';
  totalFormulas = 0;
  variantsDetected: string[] = [];
  
  // API configuration
  apiKeyConfigured = false;

  // Custom Variables Management
  showVariablesSection = false;
  inputVariables: { [key: string]: string } = {};
  outputVariables: string[] = [];
  newInputVarName = '';
  newInputVarDesc = '';
  newOutputVar = '';
  genericTerms: { [key: string]: string } = {};
  showGenericTerms = false;

  // Formula Editing
  editingFormula: ExtractedFormula | null = null;
  showFormulaEditor = false;

  // Expose Object to template
  Object = Object;

  constructor(
    private cdr: ChangeDetectorRef,
    private router: Router,
    private uploadService: UploadService,
    private variableService: VariableService,
    private exportService: ExportService
  ) {
    this.initialize();
  }

  private async initialize(): Promise<void> {
    await this.loadSupportedFormats();
    await this.loadGenericTerms();
    this.initializeDefaultVariables();
  }

  // Getters for computed properties
  get allowedExtensions(): string[] {
    return this.supportedFormats;
  }

  get hasFormulas(): boolean {
    return this.formulas.length > 0;
  }

  get isSuccess(): boolean {
    return this.uploadStatus.includes('Complete!') || this.uploadStatus.includes('successfully');
  }

  get isWarning(): boolean {
    return this.uploadStatus.includes('warning') || this.uploadStatus.includes('but no');
  }

  get isError(): boolean {
    return this.uploadStatus.includes('failed') || this.uploadStatus.includes('Unsupported');
  }

  get supportedFormatsText(): string {
    return this.supportedFormats.map(f => f.toUpperCase()).join(', ');
  }

  get hasVariantsDetected(): boolean {
    return this.variantsDetected.length > 0;
  }

  get inputVariableCount(): number {
    return Object.keys(this.inputVariables).length;
  }

  get outputVariableCount(): number {
    return this.outputVariables.length;
  }

  // Initialization methods
  private async loadSupportedFormats(): Promise<void> {
    try {
      const response = await this.uploadService.getSupportedFormats();
      this.supportedFormats = response.supported_formats || [];
      this.apiKeyConfigured = response.api_key_configured || false;
    } catch (error) {
      console.error('Failed to load supported formats:', error);
      this.supportedFormats = ['pdf', 'docx', 'txt'];
    }
  }

  private async loadGenericTerms(): Promise<void> {
    try {
      const response = await this.variableService.getGenericTerms();
      this.genericTerms = response.generic_terms || {};
    } catch (error) {
      console.error('Failed to load generic terms:', error);
    }
  }

  private initializeDefaultVariables(): void {
    this.inputVariables = this.variableService.getDefaultInputVariables();
    this.outputVariables = this.variableService.getDefaultOutputVariables();
  }

  // Variable management methods
  toggleVariablesSection(): void {
    this.showVariablesSection = !this.showVariablesSection;
  }

  toggleGenericTerms(): void {
    this.showGenericTerms = !this.showGenericTerms;
  }

  addInputVariable(): void {
    if (this.newInputVarName.trim() && this.newInputVarDesc.trim()) {
      const varName = this.newInputVarName.trim().toUpperCase();
      this.inputVariables[varName] = this.newInputVarDesc.trim();
      this.newInputVarName = '';
      this.newInputVarDesc = '';
    }
  }

  removeInputVariable(varName: string): void {
    delete this.inputVariables[varName];
  }

  addOutputVariable(): void {
    if (this.newOutputVar.trim()) {
      const varName = this.newOutputVar.trim().toUpperCase();
      if (!this.outputVariables.includes(varName)) {
        this.outputVariables.push(varName);
        this.newOutputVar = '';
      }
    }
  }

  removeOutputVariable(index: number): void {
    this.outputVariables.splice(index, 1);
  }

  addGenericTerm(termName: string): void {
    if (termName && this.genericTerms[termName]) {
      this.inputVariables[termName] = this.genericTerms[termName];
    }
  }

  // File handling methods
  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (!input.files?.length) {
      this.reset();
      return;
    }
    
    const file = input.files[0];
    this.handleFileSelection(file);
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
  }

  onDragLeave(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    
    const files = event.dataTransfer?.files;
    if (files && files.length > 0) {
      this.handleFileSelection(files[0]);
    }
  }

  private handleFileSelection(file: File): void {
    const fileExtension = file.name.split('.').pop()?.toLowerCase();
    
    if (!fileExtension || !this.supportedFormats.includes(fileExtension)) {
      this.uploadStatus = `Unsupported file type. Supported formats: ${this.supportedFormatsText}`;
      this.selectedFile = null;
      this.resetUploadState();
      return;
    }

    this.selectedFile = file;
    this.resetUploadState();
  }

  private resetUploadState(): void {
    this.uploadStatus = '';
    this.uploadProgress = 0;
    this.formulas = [];
    this.rawOutput = '';
    this.showRawOutput = false;
  }

  // Upload and processing methods
  async uploadFile(): Promise<void> {
    if (!this.selectedFile) {
      this.uploadStatus = 'Please select a file to upload.';
      return;
    }

    if (!this.validateVariables()) {
      this.uploadStatus = 'Please define at least one input variable and one output variable.';
      return;
    }

    this.setLoadingState(true);
    
    try {
      const response = await this.uploadService.uploadFile(
        this.selectedFile,
        this.inputVariables,
        this.outputVariables
      );

      this.handleUploadResponse(response);
    } catch (error) {
      this.handleUploadError(error);
    } finally {
      this.setLoadingState(false);
    }
  }

  private validateVariables(): boolean {
    return Object.keys(this.inputVariables).length > 0 && this.outputVariables.length > 0;
  }

  private setLoadingState(loading: boolean): void {
    this.isLoading = loading;
    this.uploadProgress = loading ? 0 : 100;
    this.uploadStatus = loading ? 'Analyzing document and extracting formulas with custom variables...' : this.uploadStatus;
    this.cdr.detectChanges();
  }

  private handleUploadResponse(response: BackendResponse): void {
    this.formulas = response.formulas ?? [];
    this.extractionMethod = response.extraction_method || '';
    this.totalFormulas = response.total_formulas || 0;
    this.variantsDetected = response.variants_detected || [];

    switch (response.status) {
      case 'success':
        this.handleSuccessResponse(response);
        break;
      case 'warning':
      case 'error':
        this.uploadStatus = response.message;
        break;
      default:
        this.uploadStatus = `Processing completed for ${this.selectedFile?.name}`;
    }

    this.cdr.detectChanges();
  }

  private handleSuccessResponse(response: BackendResponse): void {
    if (this.formulas.length > 0) {
      this.uploadStatus = `Analysis Complete! Extracted ${this.formulas.length} formulas from ${this.selectedFile?.name}`;
      if (this.variantsDetected.length > 1) {
        this.uploadStatus += ` (${this.variantsDetected.length} variants detected)`;
      }
    } else {
      this.uploadStatus = response.message;
    }
  }

  private handleUploadError(error: any): void {
    console.error('Upload error:', error);
    this.uploadStatus = 'Processing failed. Please try again or contact support.';
    this.resetUploadState();
  }

  // Formula editing methods
  editFormula(formula: ExtractedFormula): void {
    this.editingFormula = { ...formula };
    this.showFormulaEditor = true;
  }

  saveFormulaEdit(): void {
    if (this.editingFormula) {
      const index = this.formulas.findIndex(f => f.id === this.editingFormula!.id);
      if (index !== -1) {
        this.formulas[index] = { ...this.editingFormula };
      }
      this.closeFormulaEditor();
      this.uploadStatus = 'Formula updated successfully!';
    }
  }

  closeFormulaEditor(): void {
    this.editingFormula = null;
    this.showFormulaEditor = false;
  }

  deleteFormula(formulaId: string): void {
    if (confirm('Are you sure you want to delete this formula?')) {
      this.formulas = this.formulas.filter(f => f.id !== formulaId);
      this.uploadStatus = 'Formula deleted successfully!';
    }
  }

  // Export and save methods
  async saveFormulas(): Promise<void> {
    if (this.formulas.length === 0) {
      this.uploadStatus = 'No formulas to save.';
      return;
    }

    try {
      const response = await this.uploadService.saveFormulas({
        formulas: this.formulas,
        input_variables: this.inputVariables,
        output_variables: this.outputVariables,
        variants_detected: this.variantsDetected
      });
      this.uploadStatus = response.message || 'Formulas saved successfully!';
    } catch (error) {
      console.error('Save error:', error);
      this.uploadStatus = 'Failed to save formulas.';
    }
  }

  async forwardToDataProcessing(): Promise<void> {
    if (this.formulas.length === 0) {
      this.uploadStatus = 'No formulas to forward.';
      return;
    }

    try {
      await this.uploadService.forwardFormulas({
        formulas: this.formulas,
        input_variables: this.inputVariables,
        output_variables: this.outputVariables,
        variants_detected: this.variantsDetected
      });
      this.uploadStatus = 'Formulas forwarded to data processing service!';
    } catch (error) {
      console.error('Forward error:', error);
      this.uploadStatus = 'Failed to forward formulas to data processing service.';
    }
  }

  exportToExcel(): void {
    if (!this.formulas.length) {
      this.uploadStatus = 'No formulas available for export.';
      return;
    }

    try {
      this.exportService.exportFormulasToExcel(
        this.formulas,
        this.inputVariables,
        this.outputVariables
      );
      this.uploadStatus = 'Enhanced formulas exported successfully!';
    } catch (error) {
      console.error('Export error:', error);
      this.uploadStatus = 'Failed to export formulas.';
    }
  }

  // Navigation methods
  goToDataProcessing(): void {
    if (this.formulas.length > 0) {
      this.router.navigate(['/process-data'], {
        state: { 
          formulas: this.formulas,
          inputVariables: this.inputVariables,
          outputVariables: this.outputVariables,
          variantsDetected: this.variantsDetected
        }
      });
    } else {
      this.uploadStatus = '❗ Please extract formulas before proceeding to data processing.';
    }
  }

  // Utility methods
  toggleRawOutput(): void {
    this.showRawOutput = !this.showRawOutput;
  }

  reset(): void {
    this.selectedFile = null;
    this.resetUploadState();
    this.isLoading = false;
    this.extractionMethod = '';
    this.totalFormulas = 0;
    this.variantsDetected = [];
    this.closeFormulaEditor();
    this.cdr.detectChanges();
  }
}