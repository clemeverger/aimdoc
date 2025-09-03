export interface ScrapeRequest {
  name: string
  url: string
}

export interface JobResponse {
  job_id: string
  status: JobStatus
  created_at: string
  message: string
}

export enum JobStatus {
  PENDING = 'pending',
  RUNNING = 'running',
  COMPLETED = 'completed',
  FAILED = 'failed',
}

export interface JobStatusResponse {
  job_id: string
  status: JobStatus
  created_at: string
  started_at?: string
  completed_at?: string
  progress?: {
    pages_found?: number
    pages_scraped?: number
    files_created?: number
  }
  error_message?: string
  result_summary?: {
    files_created?: number
    build_size?: number
    build_path?: string
  }
  request?: ScrapeRequest
}

export interface JobListResponse {
  jobs: JobStatusResponse[]
  total: number
}

export interface JobResults {
  job_id: string
  status: JobStatus
  files: string[]
  build_path: string
  metadata: any
}

export interface Config {
  api_url: string
  timeout: number
}

export interface CLIError extends Error {
  statusCode?: number
}

export interface WebSocketJobUpdate {
  type: 'status_update' | 'pong'
  status?: JobStatus
  message?: string
  progress?: {
    pages_found?: number
    pages_scraped?: number
    files_created?: number
  }
  result_summary?: {
    files_created?: number
    build_size?: number
    build_path?: string
  }
  error?: string
}
