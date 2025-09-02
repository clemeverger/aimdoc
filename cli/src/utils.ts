import chalk from 'chalk';
import { JobStatus, JobStatusResponse } from './types';

export function formatJobStatus(job: JobStatusResponse): string {
  const statusColor = getStatusColor(job.status);
  const duration = job.completed_at 
    ? `(${formatDuration(new Date(job.created_at), new Date(job.completed_at))})`
    : job.started_at 
      ? `(${formatDuration(new Date(job.started_at), new Date())})`
      : '';
  
  return `${chalk.bold(job.job_id.substring(0, 8))} ${statusColor(job.status.toUpperCase())} ${duration}`;
}

export function getStatusColor(status: JobStatus): (text: string) => string {
  switch (status) {
    case JobStatus.PENDING:
      return chalk.yellow;
    case JobStatus.RUNNING:
      return chalk.blue;
    case JobStatus.COMPLETED:
      return chalk.green;
    case JobStatus.FAILED:
      return chalk.red;
    default:
      return chalk.gray;
  }
}

export function formatDuration(start: Date, end: Date): string {
  const diff = end.getTime() - start.getTime();
  const seconds = Math.floor(diff / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);

  if (hours > 0) {
    return `${hours}h ${minutes % 60}m`;
  } else if (minutes > 0) {
    return `${minutes}m ${seconds % 60}s`;
  } else {
    return `${seconds}s`;
  }
}

export function formatFileSize(bytes: number): string {
  const sizes = ['B', 'KB', 'MB', 'GB'];
  if (bytes === 0) return '0 B';
  
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i];
}

export function isValidUrl(str: string): boolean {
  try {
    new URL(str);
    return true;
  } catch {
    return false;
  }
}

export function sanitizeFilename(filename: string): string {
  return filename.replace(/[^a-z0-9.-]/gi, '_');
}

export function printError(message: string, error?: Error): void {
  console.error(chalk.red('✗'), chalk.red(message));
  if (error && process.env.DEBUG) {
    console.error(chalk.gray(error.stack));
  }
}

export function printSuccess(message: string): void {
  console.log(chalk.green('✓'), message);
}

export function printWarning(message: string): void {
  console.log(chalk.yellow('⚠'), chalk.yellow(message));
}

export function printInfo(message: string): void {
  console.log(chalk.blue('ℹ'), message);
}