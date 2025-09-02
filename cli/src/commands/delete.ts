import { Command } from 'commander';
import inquirer from 'inquirer';
import chalk from 'chalk';
import { AimdocAPI } from '../api';
import { printError, printSuccess } from '../utils';

export function createDeleteCommand(): Command {
  const deleteCommand = new Command('delete');
  
  deleteCommand
    .description('Delete a job and all its files')
    .argument('<job-id>', 'Job ID to delete')
    .option('-f, --force', 'Skip confirmation prompt')
    .action(async (jobId: string, options) => {
      try {
        const api = new AimdocAPI();
        
        // Get job status first to show what we're deleting
        let jobInfo;
        try {
          jobInfo = await api.getJobStatus(jobId);
        } catch (error) {
          printError(`Job ${jobId} not found`);
          process.exit(1);
        }
        
        if (!options.force) {
          console.log(`\n${chalk.bold('Job to delete:')}`);
          console.log(`ID: ${chalk.bold(jobInfo.job_id)}`);
          console.log(`Status: ${chalk.yellow(jobInfo.status.toUpperCase())}`);
          console.log(`Created: ${new Date(jobInfo.created_at).toLocaleString()}`);
          
          if (jobInfo.result_summary) {
            console.log(`Files: ${jobInfo.result_summary.files_created || 0}`);
          }
          
          const answer = await inquirer.prompt([
            {
              type: 'confirm',
              name: 'confirm',
              message: `Are you sure you want to delete job ${jobId}?`,
              default: false
            }
          ]);
          
          if (!answer.confirm) {
            console.log('Delete cancelled.');
            return;
          }
        }
        
        // Delete the job
        await api.deleteJob(jobId);
        printSuccess(`Job ${jobId} deleted successfully`);
        
        if (jobInfo.status === 'running') {
          console.log(chalk.yellow('Note: Running job was cancelled and deleted.'));
        }
        
      } catch (error) {
        printError('Failed to delete job', error as Error);
        process.exit(1);
      }
    });

  return deleteCommand;
}