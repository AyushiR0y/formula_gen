import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient, HttpClientModule, HttpEventType } from '@angular/common/http';
import { Router } from '@angular/router';

interface ExtractedFormula {
  term_description: string;
  mathematical_relationship: string;
  business_context: string;
  formula_explanation: string;
  confidence: number;
  reasoning_steps: string[];
  variables_explained: { [key: string]: string };
  source_method: string;
  variants?: { [key: string]: string }; // Add variants support
}

@Component({
  selector: 'app-data-processor',
  standalone: true,
  imports: [CommonModule, HttpClientModule],
  templateUrl: './data-processor.html',
  styleUrls: ['./data-processor.scss']
})
export default class DataProcessorComponent implements OnInit {
  extractedFormulas: ExtractedFormula[] = [];

  selectedFile: File | null = null;
  uploadStatus = '';
  uploadProgress = 0;
  isLoading = false;
  downloadReady = false;
  outputFilename = '';
  processingResult: any = null;
  isDragOver = false; // Add this property

  private apiUrl = 'http://127.0.0.1:5001';

  constructor(
    private http: HttpClient,
    private cdr: ChangeDetectorRef,
    private router: Router
  ) {}

  ngOnInit() {
    const state = history.state;
    if (state && Array.isArray(state.formulas) && state.formulas.length > 0) {
      this.extractedFormulas = state.formulas;
      console.log('Loaded formulas:', this.extractedFormulas);
    }
  }

  get hasFormulas(): boolean {
    return this.extractedFormulas.length > 0;
  }

  onFileSelected(event: Event) {
    const input = event.target as HTMLInputElement;
    if (!input.files?.length) {
      this.reset();
      return;
    }
    const file = input.files[0];
    this.validateAndSetFile(file);
  }

  onDragOver(event: DragEvent) {
    event.preventDefault();
    event.stopPropagation();
    this.isDragOver = true;
  }

  onDragLeave(event: DragEvent) {
    event.preventDefault();
    event.stopPropagation();
    this.isDragOver = false;
  }

  onDrop(event: DragEvent) {
    event.preventDefault();
    event.stopPropagation();
    this.isDragOver = false;

    const files = event.dataTransfer?.files;
    if (files && files.length > 0) {
      this.validateAndSetFile(files[0]);
    }
  }

  private validateAndSetFile(file: File) {
    const ext = file.name.split('.').pop()?.toLowerCase();
    if (!['csv', 'xlsx', 'xls'].includes(ext || '')) {
      this.uploadStatus = 'Unsupported file type. Please upload CSV or Excel.';
      this.selectedFile = null;
      return;
    }
    this.selectedFile = file;
    this.uploadStatus = `${file.name} selected (${this.formatFileSize(file.size)})`;
    this.uploadProgress = 0;
    this.downloadReady = false;
    this.processingResult = null;
  }

  private formatFileSize(bytes: number): string {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }

  processData() {
    if (!this.selectedFile) {
      this.uploadStatus = 'Please select a data file.';
      return;
    }
    if (!this.hasFormulas) {
      this.uploadStatus = 'No formulas available for processing.';
      return;
    }

    // First, store the formulas on the backend
    this.http.post(`${this.apiUrl}/store-formulas`, this.extractedFormulas).subscribe({
      next: (response) => {
        console.log('Formulas stored:', response);
        this.uploadFormAndProcess();
      },
      error: (err) => {
        console.error('Error storing formulas:', err);
        this.uploadStatus = 'Failed to store formulas on server.';
      }
    });
  }

  private uploadFormAndProcess() {
    const formData = new FormData();
    formData.append('file', this.selectedFile!);
    formData.append('formulas', JSON.stringify(this.extractedFormulas));

    this.uploadStatus = 'Processing data...';
    this.isLoading = true;
    this.uploadProgress = 0;
    this.processingResult = null;

    this.http.post<any>(`${this.apiUrl}/process-data`, formData, {
      reportProgress: true,
      observe: 'events'
    }).subscribe({
      next: event => {
        if (event.type === HttpEventType.UploadProgress && event.total) {
          this.uploadProgress = Math.round(100 * event.loaded / event.total);
        } else if (event.type === HttpEventType.Response) {
          this.uploadStatus = event.body?.message || 'Processing completed';
          this.downloadReady = event.body?.download_ready || false;
          this.outputFilename = event.body?.output_filename || '';
          this.processingResult = event.body?.processing_result || null;
          
          console.log('Processing result:', this.processingResult);
          
          if (this.processingResult?.errors?.length > 0) {
            this.uploadStatus += ` (${this.processingResult.errors.length} errors)`;
          }
        }
        this.cdr.detectChanges();
      },
      error: err => {
        console.error('Processing error:', err);
        this.uploadStatus = `Processing failed: ${err.error?.message || err.message}`;
        this.isLoading = false;
        this.cdr.detectChanges();
      },
      complete: () => {
        this.isLoading = false;
        this.cdr.detectChanges();
      }
    });
  }

  downloadResult() {
    if (!this.downloadReady || !this.outputFilename) {
      this.uploadStatus = 'No file ready for download.';
      return;
    }

    const link = document.createElement('a');
    link.href = `${this.apiUrl}/download/${this.outputFilename}`;
    link.download = this.outputFilename;
    link.target = '_blank';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  getStatusClass(): string {
    if (this.uploadStatus.includes('failed') || this.uploadStatus.includes('error')) {
      return 'error';
    }
    if (this.uploadStatus.includes('selected') || this.uploadStatus.includes('completed')) {
      return 'success';
    }
    return 'info';
  }

  reset() {
    this.selectedFile = null;
    this.uploadStatus = '';
    this.uploadProgress = 0;
    this.downloadReady = false;
    this.outputFilename = '';
    this.processingResult = null;
    this.isLoading = false;
    this.isDragOver = false;
  }
}