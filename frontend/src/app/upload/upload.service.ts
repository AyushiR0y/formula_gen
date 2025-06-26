// src/app/upload/upload.service.ts
import { Injectable } from '@angular/core';
import { HttpClient, HttpEventType } from '@angular/common/http';
import { Observable, firstValueFrom } from 'rxjs';
import { 
  BackendResponse, 
  SaveFormulaData, 
  SupportedFormatsResponse 
} from '../shared/interfaces';

@Injectable({
  providedIn: 'root'
})
export class UploadService {
  private readonly baseUrl = 'http://127.0.0.1:5000';

  constructor(private http: HttpClient) {}

  async getSupportedFormats(): Promise<SupportedFormatsResponse> {
    return firstValueFrom(
      this.http.get<SupportedFormatsResponse>(`${this.baseUrl}/`)
    );
  }

  async uploadFile(
    file: File,
    inputVariables: { [key: string]: string },
    outputVariables: string[]
  ): Promise<BackendResponse> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('input_variables', JSON.stringify(inputVariables));
    formData.append('output_variables', JSON.stringify(outputVariables));

    return new Promise((resolve, reject) => {
      this.http.post<BackendResponse>(`${this.baseUrl}/upload`, formData, {
        reportProgress: true,
        observe: 'events',
      }).subscribe({
        next: (event) => {
          if (event.type === HttpEventType.Response && event.body) {
            resolve(event.body);
          }
        },
        error: (error) => reject(error)
      });
    });
  }

  async saveFormulas(data: SaveFormulaData): Promise<{ message: string }> {
    return firstValueFrom(
      this.http.post<{ message: string }>(`${this.baseUrl}/save-formulas`, data)
    );
  }

  async forwardFormulas(data: SaveFormulaData): Promise<{ message: string }> {
    return firstValueFrom(
      this.http.post<{ message: string }>(`${this.baseUrl}/forward-formulas`, data)
    );
  }

  uploadFileWithProgress(
    file: File,
    inputVariables: { [key: string]: string },
    outputVariables: string[]
  ): Observable<any> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('input_variables', JSON.stringify(inputVariables));
    formData.append('output_variables', JSON.stringify(outputVariables));

    return this.http.post<BackendResponse>(`${this.baseUrl}/upload`, formData, {
      reportProgress: true,
      observe: 'events',
    });
  }
}