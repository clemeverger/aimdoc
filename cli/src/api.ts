import axios, { AxiosInstance, AxiosResponse } from 'axios';
import {
  ScrapeRequest,
  JobResponse,
  JobStatusResponse,
  JobListResponse,
  JobResults,
  Config,
  CLIError
} from './types';
import { getConfig } from './config';

export class AimdocAPI {
  private client: AxiosInstance;
  private config: Config;

  constructor() {
    this.config = getConfig();
    this.client = axios.create({
      baseURL: this.config.api_url,
      timeout: this.config.timeout,
      headers: {
        'Content-Type': 'application/json'
      }
    });

    // Add response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        const err: CLIError = new Error(
          error.response?.data?.detail || 
          error.response?.data?.error || 
          error.message
        );
        err.statusCode = error.response?.status;
        throw err;
      }
    );
  }

  async createScrapeJob(request: ScrapeRequest): Promise<JobResponse> {
    const response: AxiosResponse<JobResponse> = await this.client.post('/api/v1/scrape', request);
    return response.data;
  }

  async getJobStatus(jobId: string): Promise<JobStatusResponse> {
    const response: AxiosResponse<JobStatusResponse> = await this.client.get(`/api/v1/jobs/${jobId}`);
    return response.data;
  }

  async listJobs(limit?: number): Promise<JobListResponse> {
    const params = limit ? { limit } : {};
    const response: AxiosResponse<JobListResponse> = await this.client.get('/api/v1/jobs', { params });
    return response.data;
  }

  async getJobResults(jobId: string): Promise<JobResults> {
    const response: AxiosResponse<JobResults> = await this.client.get(`/api/v1/jobs/${jobId}/results`);
    return response.data;
  }

  async downloadFile(jobId: string, filePath: string): Promise<Buffer> {
    const response = await this.client.get(`/api/v1/jobs/${jobId}/download/${filePath}`, {
      responseType: 'arraybuffer'
    });
    return Buffer.from(response.data);
  }

  async deleteJob(jobId: string): Promise<void> {
    await this.client.delete(`/api/v1/jobs/${jobId}`);
  }

  async cancelJob(jobId: string): Promise<void> {
    await this.client.post(`/api/v1/jobs/${jobId}/cancel`);
  }

  async healthCheck(): Promise<boolean> {
    try {
      await this.client.get('/health');
      return true;
    } catch {
      return false;
    }
  }
}