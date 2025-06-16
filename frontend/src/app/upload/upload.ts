import { Component, ChangeDetectionStrategy, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient, HttpClientModule, HttpEventType } from '@angular/common/http';
import { saveAs } from 'file-saver';
import * as XLSX from 'xlsx';

interface FormulaData {
  acronym: string;
  full_name: string;
  description: string;
  formula: string;
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
  formulas: FormulaData[] = [];
  rawOutput = '';
  showRawOutput = false;
  supportedFormats: string[] = [];
  isLoading = false;

  constructor(private http: HttpClient, private cdr: ChangeDetectorRef) {
    this.loadSupportedFormats();
  }

  // Add this getter to fix the template error
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
        // Fallback to common formats
        this.supportedFormats = ['pdf', 'docx', 'txt', 'png', 'jpg'];
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
      this.uploadStatus = ` Unsupported file type. Supported formats: ${this.supportedFormats.join(', ').toUpperCase()}`;
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
        this.uploadStatus = ` Unsupported file type. Supported formats: ${this.supportedFormats.join(', ').toUpperCase()}`;
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

    this.uploadStatus = '⏳ Analyzing document and extracting formulas...';
    this.uploadProgress = 0;
    this.formulas = [];
    this.rawOutput = '';
    this.isLoading = true;

    this.http.post<any>('http://127.0.0.1:5000/upload', formData, {
      reportProgress: true,
      observe: 'events',
    }).subscribe({
      next: (event) => {
        if (event.type === HttpEventType.UploadProgress && event.total) {
          this.uploadProgress = Math.round((event.loaded / event.total) * 100);
        } else if (event.type === HttpEventType.Response) {
          console.log('--- Response Received ---');
          console.log('Backend Response:', event.body);

          this.uploadProgress = 100;
          this.isLoading = false;
          this.formulas = event.body?.formulas ?? [];
          this.rawOutput = event.body?.raw_output || '';

          const status = event.body?.status;
          const message = event.body?.message || '';

          switch (status) {
            case 'success':
              if (this.formulas.length > 0) {
                this.uploadStatus = ` Analysis Complete! Extracted ${this.formulas.length} formulas from ${this.selectedFile?.name}`;
              } else {
                this.uploadStatus = `⚠️ ${message}`;
              }
              break;
            case 'warning':
              this.uploadStatus = `⚠️ ${message}`;
              break;
            case 'error':
              this.uploadStatus = `❌ ${message}`;
              break;
            default:
              this.uploadStatus = `✅ Processing completed for ${this.selectedFile?.name}`;
          }

          this.cdr.detectChanges();
        }
      },
      error: (err) => {
        console.error('Upload error:', err);
        this.uploadStatus = '❌ Processing failed. Please try again or contact support.';
        this.uploadProgress = 0;
        this.formulas = [];
        this.rawOutput = '';
        this.isLoading = false;
        this.cdr.detectChanges();
      },
      complete: () => {
        console.log('--- Upload Complete ---');
        this.isLoading = false;
        this.cdr.detectChanges();
      }
    });
  }

  exportToExcel() {
    if (!this.formulas.length) {
      this.uploadStatus = '⚠️ No formulas available for export.';
      return;
    }

    try {
      // Create Excel data with proper headers
      const excelData = this.formulas.map(formula => ({
        'Acronym': formula.acronym,
        'Full Name': formula.full_name,
        'Description': formula.description,
        'Formula': formula.formula
      }));

      const worksheet = XLSX.utils.json_to_sheet(excelData);
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, 'Insurance Formulas');

      // Set column widths
      const colWidths = [
        { wch: 12 }, // Acronym
        { wch: 25 }, // Full Name
        { wch: 40 }, // Description
        { wch: 50 }, // Formula
      ];
      worksheet['!cols'] = colWidths;

      const excelBuffer = XLSX.write(workbook, { bookType: 'xlsx', type: 'array' });
      const blob = new Blob([excelBuffer], { type: 'application/octet-stream' });
      
      const timestamp = new Date().toISOString().split('T')[0];
      saveAs(blob, `insurance_formulas_${timestamp}.xlsx`);
      
      this.uploadStatus = '✅ Formulas exported successfully!';
    } catch (error) {
      console.error('Export error:', error);
      this.uploadStatus = '❌ Failed to export formulas.';
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
    this.cdr.detectChanges();
  }

  // Helper methods
  get hasFormulas(): boolean {
    return this.formulas.length > 0;
  }

  get isSuccess(): boolean {
    return this.uploadStatus.includes('✅');
  }

  get isWarning(): boolean {
    return this.uploadStatus.includes('⚠️');
  }

  get isError(): boolean {
    return this.uploadStatus.includes('❌');
  }

  get supportedFormatsText(): string {
    return this.supportedFormats.map(f => f.toUpperCase()).join(', ');
  }
}