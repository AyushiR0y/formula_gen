import { Routes } from '@angular/router';
import UploadComponent from './upload/upload';
import DataProcessorComponent from './data-processor/data-processor';
export const routes: Routes = [
  { path: '', component: UploadComponent },
  { path: 'process-data', component: DataProcessorComponent },
  { path: '**', redirectTo: '' }
];
