import { Routes } from '@angular/router';
import UploadComponent from './upload/upload';
export const routes: Routes = [
  { path: '', component: UploadComponent },
  { path: '**', redirectTo: '' }
];
