import { Component, ChangeDetectionStrategy, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient, HttpClientModule, HttpEventType } from '@angular/common/http';
import { saveAs } from 'file-saver';
import * as XLSX from 'xlsx';

interface ExtractedFormula {
  term_description: string;
  mathematical_relationship: string;
  business_context: string;
  formula_explanation: string;
  confidence: number;
  reasoning_steps: string[];
  variables_explained: { [key: string]: string };
  source_method: string;
}

interface BackendResponse {
  message: string;
  formulas: ExtractedFormula[];
  status: 'success' | 'warning' | 'error';
  file_type?: string;
  extraction_method?: string;
  total_formulas?: number;
}

@Component({
  selector: 'app-upload',
  standalone: true,
  imports: [CommonModule, HttpClientModule],
  templateUrl: './upload.html',
  styleUrls: ['./upload.scss'],
})
export default class UploadComponent {
  selectedFile: File | null = null;
  uploadStatus = '';
  uploadProgress = 0;
  formulas: ExtractedFormula[] = [];
  rawOutput = '';
  showRawOutput = false;
  supportedFormats: string[] = [];
  isLoading = false;
  extractionMethod = '';
  totalFormulas = 0;

  // Expose Object to template
  Object = Object;

  constructor(private http: HttpClient, private cdr: ChangeDetectorRef) {
    this.loadSupportedFormats();
  }

  get allowedExtensions(): string[] {
    return this.supportedFormats;
  }

  loadSupportedFormats() {
    this.http.get<any>('http://127.0.0.1:5000/supported-formats').subscribe({
      next: (response) => {
        this.supportedFormats = response.supported_formats || [];
        console.log('Supported formats:', this.supportedFormats);
      },
      error: (err) => {
        console.error('Failed to load supported formats:', err);
        this.supportedFormats = ['pdf', 'docx', 'txt'];
      }
    });
  }

  onFileSelected(event: Event) {
    const input = event.target as HTMLInputElement;
    if (!input.files?.length) {
      this.reset();
      return;
    }
    
    const file = input.files[0];
    const fileExtension = file.name.split('.').pop()?.toLowerCase();
    
    if (!fileExtension || !this.supportedFormats.includes(fileExtension)) {
      this.uploadStatus = `Unsupported file type. Supported formats: ${this.supportedFormats.join(', ').toUpperCase()}`;
      this.selectedFile = null;
      this.uploadProgress = 0;
      this.formulas = [];
      this.rawOutput = '';
      return;
    }

    this.selectedFile = file;
    this.uploadStatus = '';
    this.uploadProgress = 0;
    this.formulas = [];
    this.rawOutput = '';
    this.showRawOutput = false;
  }

  onDragOver(event: DragEvent) {
    event.preventDefault();
    event.stopPropagation();
  }

  onDragLeave(event: DragEvent) {
    event.preventDefault();
    event.stopPropagation();
  }

  onDrop(event: DragEvent) {
    event.preventDefault();
    event.stopPropagation();
    
    const files = event.dataTransfer?.files;
    if (files && files.length > 0) {
      const file = files[0];
      const fileExtension = file.name.split('.').pop()?.toLowerCase();
      
      if (!fileExtension || !this.supportedFormats.includes(fileExtension)) {
        this.uploadStatus = `Unsupported file type. Supported formats: ${this.supportedFormats.join(', ').toUpperCase()}`;
        return;
      }

      this.selectedFile = file;
      this.uploadStatus = '';
      this.uploadProgress = 0;
      this.formulas = [];
      this.rawOutput = '';
      this.showRawOutput = false;
    }
  }

  uploadFile() {
    if (!this.selectedFile) {
      this.uploadStatus = 'Please select a file to upload.';
      return;
    }

    const formData = new FormData();
    formData.append('file', this.selectedFile);

    this.uploadStatus = 'Analyzing document and extracting formulas...';
    this.uploadProgress = 0;
    this.formulas = [];
    this.rawOutput = '';
    this.isLoading = true;

    this.http.post<BackendResponse>('http://127.0.0.1:5000/upload', formData, {
      reportProgress: true,
      observe: 'events',
    }).subscribe({
      next: (event) => {
        if (event.type === HttpEventType.UploadProgress && event.total) {
          this.uploadProgress = Math.round((event.loaded / event.total) * 100);
        } else if (event.type === HttpEventType.Response) {
          console.log('Backend Response:', event.body);

          this.uploadProgress = 100;
          this.isLoading = false;
          this.formulas = event.body?.formulas ?? [];
          this.extractionMethod = event.body?.extraction_method || '';
          this.totalFormulas = event.body?.total_formulas || 0;

          const status = event.body?.status;
          const message = event.body?.message || '';

          switch (status) {
            case 'success':
              if (this.formulas.length > 0) {
                this.uploadStatus = `Analysis Complete! Extracted ${this.formulas.length} formulas from ${this.selectedFile?.name}`;
              } else {
                this.uploadStatus = message;
              }
              break;
            case 'warning':
              this.uploadStatus = message;
              break;
            case 'error':
              this.uploadStatus = message;
              break;
            default:
              this.uploadStatus = `Processing completed for ${this.selectedFile?.name}`;
          }

          this.cdr.detectChanges();
        }
      },
      error: (err) => {
        console.error('Upload error:', err);
        this.uploadStatus = 'Processing failed. Please try again or contact support.';
        this.uploadProgress = 0;
        this.formulas = [];
        this.rawOutput = '';
        this.isLoading = false;
        this.cdr.detectChanges();
      },
      complete: () => {
        this.isLoading = false;
        this.cdr.detectChanges();
      }
    });
  }

  exportToExcel() {
    if (!this.formulas.length) {
      this.uploadStatus = 'No formulas available for export.';
      return;
    }

    try {
      const excelData = this.formulas.map(formula => ({
        'Term Description': formula.term_description,
        'Mathematical Relationship': formula.mathematical_relationship,
        'Business Context': formula.business_context,
        'Formula Explanation': formula.formula_explanation,
        'Confidence Score': (formula.confidence * 100).toFixed(1) + '%',
        'Variables': Object.entries(formula.variables_explained)
                      .map(([key, value]) => `${key}: ${value}`)
                      .join(' | '),
        'Source Method': formula.source_method
      }));

      const worksheet = XLSX.utils.json_to_sheet(excelData);
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, 'Formula Analysis');

      const colWidths = [
        { wch: 25 }, // Term Description
        { wch: 40 }, // Mathematical Relationship
        { wch: 35 }, // Business Context
        { wch: 50 }, // Formula Explanation
        { wch: 15 }, // Confidence Score
        { wch: 60 }, // Variables
        { wch: 20 }, // Source Method
      ];
      worksheet['!cols'] = colWidths;

      const excelBuffer = XLSX.write(workbook, { bookType: 'xlsx', type: 'array' });
      const blob = new Blob([excelBuffer], { type: 'application/octet-stream' });
      
      const timestamp = new Date().toISOString().split('T')[0];
      saveAs(blob, `formula_analysis_${timestamp}.xlsx`);
      
      this.uploadStatus = 'Formulas exported successfully!';
    } catch (error) {
      console.error('Export error:', error);
      this.uploadStatus = 'Failed to export formulas.';
    }
  }

  toggleRawOutput() {
    this.showRawOutput = !this.showRawOutput;
  }

  reset() {
    this.selectedFile = null;
    this.uploadStatus = '';
    this.uploadProgress = 0;
    this.formulas = [];
    this.rawOutput = '';
    this.showRawOutput = false;
    this.isLoading = false;
    this.extractionMethod = '';
    this.totalFormulas = 0;
    this.cdr.detectChanges();
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

  
}