import { bootstrapApplication } from '@angular/platform-browser';
import { appConfig } from './app/app.config';
import { AppRoot } from './app/app';
import { provideHttpClient } from '@angular/common/http';
import 'zone.js';

// Add provideHttpClient to your existing appConfig
const updatedAppConfig = {
  ...appConfig,
  providers: [
    ...(appConfig.providers || []),
    provideHttpClient()
  ]
};

bootstrapApplication(AppRoot, updatedAppConfig)
  .catch((err) => console.error(err));