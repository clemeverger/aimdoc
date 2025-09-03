import { Command } from 'commander';
import inquirer from 'inquirer';
import ora from 'ora';
import chalk from 'chalk';
import path from 'path';
import fs from 'fs-extra';
import WebSocket from 'ws';
import { AimdocAPI } from '../api';
import { ScrapeRequest, JobStatus, WebSocketJobUpdate } from '../types';
import { isValidUrl, formatJobStatus, printError, printSuccess, printInfo } from '../utils';

export function createScrapeCommand(): Command {
  const scrapeCommand = new Command('scrape');
  
  scrapeCommand
    .description('Start a new documentation scraping job')
    .argument('[url]', 'URL of the documentation site to scrape')
    .option('-n, --name <name>', 'Project name')
    .option('-m, --mode <mode>', 'Output mode (bundle|single)', 'bundle')
    .option('--no-wait', 'Don\'t wait for job completion (just create and exit)')
    .option('--no-progress', 'Disable progress monitoring')
    .option('--no-auto-download', 'Disable automatic download of results')
    .option('-o, --output <dir>', 'Output directory for downloaded results', '.')
    .action(async (url: string | undefined, options) => {
      try {
        const api = new AimdocAPI();
        
        // Health check
        const spinner = ora('Connecting to API...').start();
        const isHealthy = await api.healthCheck();
        
        if (!isHealthy) {
          spinner.fail('API is not available. Make sure the server is running.');
          process.exit(1);
        }
        spinner.succeed('Connected to API');
        
        // Get scrape parameters
        const scrapeRequest = await getScrapeRequest(url, options);
        
        // Create job
        const createSpinner = ora('Creating scrape job...').start();
        const job = await api.createScrapeJob(scrapeRequest);
        createSpinner.succeed(`Job created: ${chalk.bold(job.job_id)}`);
        
        printInfo(`Job URL: ${chalk.underline(`http://localhost:8000/docs#/jobs/get_job_status_api_v1_jobs__job_id__get`)}`);
        
        if (!options.noWait) {
          await waitForCompletionWithWebSocket(
            api, 
            job.job_id, 
            scrapeRequest.name,
            !options.noProgress,
            !options.noAutoDownload,
            options.output
          );
        } else {
          printInfo(`Use ${chalk.bold(`aimdoc status ${job.job_id}`)} to check progress`);
          printInfo(`Use ${chalk.bold(`aimdoc download ${job.job_id}`)} to download results when complete`);
        }
        
      } catch (error) {
        console.error('Detailed error:', error);
        printError('Failed to create scrape job', error as Error);
        process.exit(1);
      }
    });

  return scrapeCommand;
}

async function getScrapeRequest(url: string | undefined, options: any): Promise<ScrapeRequest> {
  const request: ScrapeRequest = {
    name: '',
    url: ''
  };
  
  // Get URL
  if (url) {
    if (!isValidUrl(url)) {
      throw new Error(`Invalid URL: ${url}`);
    }
    request.url = url;
  } else {
    const urlAnswer = await inquirer.prompt([
      {
        type: 'input',
        name: 'url',
        message: 'Documentation URL:',
        validate: (input: string) => {
          if (!input.trim()) return 'URL is required';
          if (!isValidUrl(input)) return 'Please enter a valid URL';
          return true;
        }
      }
    ]);
    request.url = urlAnswer.url;
  }
  
  // Get name
  if (options.name) {
    request.name = options.name;
  } else {
    const defaultName = new URL(request.url).hostname.replace(/^www\./, '');
    const nameAnswer = await inquirer.prompt([
      {
        type: 'input',
        name: 'name',
        message: 'Project name:',
        default: defaultName,
        validate: (input: string) => input.trim() ? true : 'Project name is required'
      }
    ]);
    request.name = nameAnswer.name;
  }
  
  // Set mode
  if (options.mode && ['bundle', 'single'].includes(options.mode)) {
    request.output_mode = options.mode as 'bundle' | 'single';
  }
  
  return request;
}

async function waitForCompletionWithWebSocket(
  api: AimdocAPI, 
  jobId: string, 
  projectName: string,
  showProgress: boolean, 
  autoDownload: boolean,
  outputDir: string
): Promise<void> {
  const spinner = showProgress ? ora('Connecting to job...').start() : null;
  let ws: WebSocket | null = null;

  try {
    ws = await api.connectToJobWebSocket(
      jobId,
      async (update: WebSocketJobUpdate) => {
        if (update.type === 'status_update') {
          if (showProgress && spinner) {
            let message = update.message || 'Processing...';
            
            if (update.progress) {
              const { pages_found = 0, pages_scraped = 0, files_created = 0 } = update.progress;
              if (pages_found > 0 || pages_scraped > 0 || files_created > 0) {
                message = `Found ${pages_found} pages, scraped ${pages_scraped}, created ${files_created} files`;
              }
            }
            
            spinner.text = message;
          }

          if (update.status === JobStatus.COMPLETED) {
            if (spinner) spinner.succeed('Scraping completed successfully!');
            
            if (update.result_summary) {
              printSuccess(`Created ${update.result_summary.files_created} files from ${update.progress?.pages_scraped || 0} pages`);
            }

            // Auto-download results if enabled
            if (autoDownload) {
              await downloadResults(api, jobId, projectName, outputDir);
            } else {
              printInfo(`Use ${chalk.bold(`aimdoc download ${jobId}`)} to download the results`);
            }
            
            ws?.close();
          } else if (update.status === JobStatus.FAILED) {
            if (spinner) spinner.fail('Scraping failed');
            printError(update.error || update.message || 'Job failed with unknown error');
            ws?.close();
            process.exit(1);
          }
        }
      },
      (error: Error) => {
        console.log('WebSocket error, falling back to polling...');
        // Don't exit, let it fall through to fallback
      },
      () => {
        // WebSocket closed
      }
    );

    if (spinner) spinner.text = 'Connected! Starting scrape...';

  } catch (error) {
    // Fallback to polling if WebSocket fails
    if (spinner) {
      spinner.text = 'WebSocket unavailable, falling back to polling...';
    }
    await waitForCompletionFallback(api, jobId, projectName, showProgress, autoDownload, outputDir);
  }
}

async function downloadResults(api: AimdocAPI, jobId: string, projectName: string, outputDir: string): Promise<void> {
  const downloadSpinner = ora('Downloading results...').start();
  
  try {
    const outputPath = path.join(outputDir, `${projectName}-results.zip`);
    await fs.ensureDir(path.dirname(outputPath));
    
    await api.downloadJobZip(jobId, outputPath);
    
    downloadSpinner.succeed(`Results downloaded to: ${chalk.underline(outputPath)}`);
    printInfo(`Extract with: ${chalk.bold(`unzip "${outputPath}"`)}`);
  } catch (error) {
    downloadSpinner.fail('Failed to download results');
    printError('Download error', error as Error);
    printInfo(`You can try downloading manually: ${chalk.bold(`aimdoc download ${jobId}`)}`);
  }
}

async function waitForCompletionFallback(
  api: AimdocAPI, 
  jobId: string, 
  projectName: string,
  showProgress: boolean, 
  autoDownload: boolean,
  outputDir: string
): Promise<void> {
  const spinner = showProgress ? ora('Starting scrape...').start() : null;
  
  let lastStatus: JobStatus | null = null;
  let lastProgress: any = null;
  
  while (true) {
    try {
      const status = await api.getJobStatus(jobId);
      
      if (showProgress && spinner) {
        if (status.status !== lastStatus || 
            JSON.stringify(status.progress) !== JSON.stringify(lastProgress)) {
          
          let message = 'Processing...';
          if (status.progress) {
            const { pages_found = 0, pages_scraped = 0, files_created = 0 } = status.progress;
            if (pages_found > 0) {
              message = `Found ${pages_found} pages, scraped ${pages_scraped}, created ${files_created} files`;
            }
          }
          
          spinner.text = message;
          lastStatus = status.status;
          lastProgress = status.progress;
        }
      }
      
      if (status.status === JobStatus.COMPLETED) {
        if (spinner) spinner.succeed('Scraping completed successfully!');
        
        if (status.result_summary) {
          printSuccess(`Created ${status.result_summary.files_created} files`);
        }
        
        if (autoDownload) {
          await downloadResults(api, jobId, projectName, outputDir);
        } else {
          printInfo(`Use ${chalk.bold(`aimdoc download ${jobId}`)} to download the results`);
        }
        break;
      }
      
      if (status.status === JobStatus.FAILED) {
        if (spinner) spinner.fail('Scraping failed');
        printError(status.error_message || 'Job failed with unknown error');
        process.exit(1);
      }
      
      // Wait before checking again
      await new Promise(resolve => setTimeout(resolve, 2000));
      
    } catch (error) {
      if (spinner) spinner.fail('Error checking job status');
      printError('Failed to check job status', error as Error);
      process.exit(1);
    }
  }
}