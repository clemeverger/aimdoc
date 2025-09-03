import axios, { AxiosInstance, AxiosResponse } from 'axios';
import WebSocket from 'ws';
import fs from 'fs-extra';
import {
  ScrapeRequest,
  JobResponse,
  JobStatusResponse,
  JobListResponse,
  JobResults,
  Config,
  CLIError,
  WebSocketJobUpdate
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

  async downloadJobZip(jobId: string, outputPath: string): Promise<void> {
    const response = await this.client.get(`/api/v1/jobs/${jobId}/download-zip`, {
      responseType: 'arraybuffer'
    });
    
    const buffer = Buffer.from(response.data);
    await fs.writeFile(outputPath, buffer);
  }

  createJobWebSocket(jobId: string): WebSocket {
    const wsUrl = this.config.api_url.replace(/^http/, 'ws') + `/api/v1/jobs/${jobId}/ws`;
    return new WebSocket(wsUrl);
  }

  async connectToJobWebSocket(
    jobId: string,
    onUpdate: (update: WebSocketJobUpdate) => void,
    onError?: (error: Error) => void,
    onClose?: () => void
  ): Promise<WebSocket> {
    return new Promise((resolve, reject) => {
      const ws = this.createJobWebSocket(jobId);

      ws.on('open', () => {
        resolve(ws);
      });

      ws.on('message', (data: string) => {
        try {
          const update: WebSocketJobUpdate = JSON.parse(data);
          onUpdate(update);
        } catch (error) {
          onError?.(new Error('Failed to parse WebSocket message'));
        }
      });

      ws.on('error', (error: Error) => {
        onError?.(error);
        reject(error);
      });

      ws.on('close', () => {
        onClose?.();
      });

      // Set up keepalive
      const keepAliveInterval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send('ping');
        }
      }, 30000);

      ws.on('close', () => {
        clearInterval(keepAliveInterval);
      });
    });
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