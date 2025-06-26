// src/app/upload/variable.service.ts
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { GenericTermsResponse } from '../shared/interfaces';

@Injectable({
  providedIn: 'root'
})
export class VariableService {
  private readonly baseUrl = 'http://127.0.0.1:5000';

  constructor(private http: HttpClient) {}

  async getGenericTerms(): Promise<GenericTermsResponse> {
    return firstValueFrom(
      this.http.get<GenericTermsResponse>(`${this.baseUrl}/generic-terms`)
    );
  }

  getDefaultInputVariables(): { [key: string]: string } {
    return {
      'ENTRY_AGE': 'Age of the policyholder at policy inception',
      'PREMIUM': 'Premium amount (annual/monthly/quarterly)',
      'POLICY_TERM': 'Total duration of the policy',
      'SA': 'Sum Assured - guaranteed amount on maturity/death'
    };
  }

  getDefaultOutputVariables(): string[] {
    return [
      'SURRENDER_VALUE',
      'MATURITY_BENEFIT',
      'DEATH_BENEFIT'
    ];
  }

  validateVariableName(name: string): boolean {
    // Variable names should be uppercase, alphanumeric with underscores
    const variablePattern = /^[A-Z][A-Z0-9_]*$/;
    return variablePattern.test(name);
  }

  sanitizeVariableName(name: string): string {
    return name.trim().toUpperCase().replace(/[^A-Z0-9_]/g, '_');
  }

  validateVariableDescription(description: string): boolean {
    return description.trim().length >= 5;
  }

  getCommonInsuranceVariables(): { [key: string]: string } {
    return {
      'PREMIUM': 'Insurance premium amount',
      'DEDUCTIBLE': 'Insurance deductible amount',
      'COVERAGE': 'Coverage amount or limit',
      'POLICY_TERM': 'Policy term duration',
      'SUM_ASSURED': 'Sum assured amount',
      'ENTRY_AGE': 'Age at policy entry',
      'MATURITY_AGE': 'Age at policy maturity',
      'SURRENDER_VALUE': 'Policy surrender value',
      'CASH_VALUE': 'Policy cash value',
      'DEATH_BENEFIT': 'Death benefit amount',
      'MATURITY_BENEFIT': 'Maturity benefit amount',
      'BONUS': 'Bonus amount',
      'LOADING': 'Loading percentage',
      'DISCOUNT': 'Discount percentage',
      'COMMISSION': 'Commission amount or rate',
      'INTEREST_RATE': 'Interest rate percentage',
      'INFLATION_RATE': 'Inflation rate percentage',
      'MORTALITY_RATE': 'Mortality rate',
      'LAPSE_RATE': 'Policy lapse rate'
    };
  }

  getCommonFinancialVariables(): { [key: string]: string } {
    return {
      'PRINCIPAL': 'Principal amount',
      'INTEREST': 'Interest rate or amount',
      'TIME': 'Time period',
      'RATE': 'Rate or percentage',
      'AMOUNT': 'Total amount',
      'FV': 'Future value',
      'PV': 'Present value',
      'PMT': 'Payment amount',
      'NPV': 'Net present value',
      'IRR': 'Internal rate of return',
      'ROI': 'Return on investment',
      'TAX_RATE': 'Tax rate percentage',
      'DISCOUNT_RATE': 'Discount rate',
      'COMPOUND_FREQUENCY': 'Compounding frequency',
      'YIELD': 'Yield percentage'
    };
  }

  getAllGenericTerms(): { [key: string]: string } {
    return {
      ...this.getCommonInsuranceVariables(),
      ...this.getCommonFinancialVariables()
    };
  }
}