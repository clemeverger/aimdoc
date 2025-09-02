import { Command } from 'commander';
import chalk from 'chalk';
import { AimdocAPI } from '../api';
import { formatFileSize, printError } from '../utils';

export function createResultsCommand(): Command {
  const resultsCommand = new Command('results');
  
  resultsCommand
    .description('Show results and file list for a completed job')
    .argument('<job-id>', 'Job ID to show results for')
    .action(async (jobId: string) => {
      try {
        const api = new AimdocAPI();
        const results = await api.getJobResults(jobId);
        
        console.log(`\n${chalk.bold('Job Results')}`);
        console.log(`Job ID: ${chalk.bold(results.job_id)}`);
        console.log(`Status: ${chalk.green(results.status.toUpperCase())}`);
        console.log(`Build Path: ${chalk.underline(results.build_path)}`);
        
        if (results.metadata) {
          console.log(`\n${chalk.bold('Metadata')}`);
          Object.entries(results.metadata).forEach(([key, value]) => {
            let formattedValue = value;
            if (key.includes('size') && typeof value === 'number') {
              formattedValue = formatFileSize(value);
            }
            console.log(`${key}: ${formattedValue}`);
          });
        }
        
        console.log(`\n${chalk.bold('Files')} ${chalk.gray(`(${results.files.length} total)`)}`);
        
        if (results.files.length === 0) {
          console.log('No files found.');
        } else {
          // Group files by directory
          const filesByDir: { [key: string]: string[] } = {};
          
          results.files.forEach(file => {
            const dir = file.includes('/') ? file.substring(0, file.lastIndexOf('/')) : '.';
            if (!filesByDir[dir]) {
              filesByDir[dir] = [];
            }
            filesByDir[dir].push(file);
          });
          
          // Sort directories
          const sortedDirs = Object.keys(filesByDir).sort((a, b) => {
            if (a === '.') return -1;
            if (b === '.') return 1;
            return a.localeCompare(b);
          });
          
          sortedDirs.forEach(dir => {
            if (dir !== '.') {
              console.log(`\n${chalk.blue(dir)}/`);
            }
            
            filesByDir[dir].sort().forEach(file => {
              const fileName = file.includes('/') ? file.substring(file.lastIndexOf('/') + 1) : file;
              const indent = dir === '.' ? '' : '  ';
              console.log(`${indent}${fileName}`);
            });
          });
        }
        
        console.log(`\n${chalk.bold('Download Options')}`);
        console.log(`All files: ${chalk.cyan(`aimdoc download ${jobId}`)}`);
        console.log(`Specific file: ${chalk.cyan(`aimdoc download ${jobId} -f <filename>`)}`);
        console.log(`Custom directory: ${chalk.cyan(`aimdoc download ${jobId} -o <directory>`)}`);
        console.log('');
        
      } catch (error) {
        printError('Failed to get job results', error as Error);
        process.exit(1);
      }
    });

  return resultsCommand;
}