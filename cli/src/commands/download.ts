import { Command } from 'commander';
import * as fs from 'fs-extra';
import * as path from 'path';
import ora from 'ora';
import chalk from 'chalk';
import inquirer from 'inquirer';
import { AimdocAPI } from '../api';
import { sanitizeFilename, printError, printSuccess, printInfo } from '../utils';

export function createDownloadCommand(): Command {
  const downloadCommand = new Command('download');
  
  downloadCommand
    .description('Download results from a completed job')
    .argument('<job-id>', 'Job ID to download')
    .option('-o, --output <dir>', 'Output directory', '.')
    .option('-f, --file <file>', 'Download specific file only')
    .option('--overwrite', 'Overwrite existing files')
    .action(async (jobId: string, options) => {
      try {
        const api = new AimdocAPI();
        
        // Get job results
        const spinner = ora('Getting job results...').start();
        const results = await api.getJobResults(jobId);
        spinner.succeed(`Found ${results.files.length} files`);
        
        if (results.files.length === 0) {
          printInfo('No files to download.');
          return;
        }
        
        // Determine what to download
        let filesToDownload = results.files;
        
        if (options.file) {
          const requestedFile = results.files.find(f => 
            f === options.file || f.endsWith(`/${options.file}`) || f.includes(options.file)
          );
          
          if (!requestedFile) {
            printError(`File '${options.file}' not found in job results`);
            console.log('\nAvailable files:');
            results.files.forEach(file => console.log(`  ${file}`));
            process.exit(1);
          }
          
          filesToDownload = [requestedFile];
        }
        
        // Prepare output directory
        const outputDir = path.resolve(options.output);
        await fs.ensureDir(outputDir);
        
        // Check for existing files
        if (!options.overwrite) {
          const existingFiles = [];
          for (const file of filesToDownload) {
            const outputPath = path.join(outputDir, file);
            if (await fs.pathExists(outputPath)) {
              existingFiles.push(file);
            }
          }
          
          if (existingFiles.length > 0) {
            console.log(chalk.yellow('The following files already exist:'));
            existingFiles.forEach(file => console.log(`  ${file}`));
            
            const answer = await inquirer.prompt([
              {
                type: 'confirm',
                name: 'overwrite',
                message: 'Do you want to overwrite them?',
                default: false
              }
            ]);
            
            if (!answer.overwrite) {
              console.log('Download cancelled.');
              return;
            }
          }
        }
        
        // Download files
        const downloadSpinner = ora(`Downloading ${filesToDownload.length} files...`).start();
        let downloadedCount = 0;
        
        for (const file of filesToDownload) {
          try {
            const fileData = await api.downloadFile(jobId, file);
            const outputPath = path.join(outputDir, file);
            
            // Ensure directory exists
            await fs.ensureDir(path.dirname(outputPath));
            
            // Write file
            await fs.writeFile(outputPath, fileData);
            downloadedCount++;
            
            downloadSpinner.text = `Downloaded ${downloadedCount}/${filesToDownload.length} files...`;
            
          } catch (error) {
            downloadSpinner.warn(`Failed to download ${file}: ${(error as Error).message}`);
          }
        }
        
        if (downloadedCount === filesToDownload.length) {
          downloadSpinner.succeed(`Downloaded all ${downloadedCount} files`);
        } else {
          downloadSpinner.warn(`Downloaded ${downloadedCount}/${filesToDownload.length} files (some failed)`);
        }
        
        printSuccess(`Files saved to: ${chalk.underline(outputDir)}`);
        
        // Show what was downloaded
        if (downloadedCount > 0) {
          console.log('\nDownloaded files:');
          for (const file of filesToDownload.slice(0, 10)) { // Show first 10
            const outputPath = path.join(outputDir, file);
            if (await fs.pathExists(outputPath)) {
              const stats = await fs.stat(outputPath);
              console.log(`  ${file} ${chalk.gray(`(${stats.size} bytes)`)}`);
            }
          }
          
          if (filesToDownload.length > 10) {
            console.log(chalk.gray(`  ... and ${filesToDownload.length - 10} more files`));
          }
        }
        
      } catch (error) {
        printError('Failed to download job results', error as Error);
        process.exit(1);
      }
    });

  return downloadCommand;
}