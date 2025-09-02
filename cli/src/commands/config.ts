import { Command } from 'commander';
import inquirer from 'inquirer';
import chalk from 'chalk';
import { getConfig, saveConfig, getConfigPath } from '../config';
import { isValidUrl, printError, printSuccess, printInfo } from '../utils';

export function createConfigCommand(): Command {
  const configCommand = new Command('config');
  
  configCommand
    .description('Manage CLI configuration')
    .option('--show', 'Show current configuration')
    .option('--reset', 'Reset to default configuration')
    .option('--api-url <url>', 'Set API URL')
    .option('--timeout <ms>', 'Set request timeout in milliseconds')
    .action(async (options) => {
      try {
        if (options.show) {
          const config = getConfig();
          console.log(`\n${chalk.bold('Current Configuration')}`);
          console.log(`API URL: ${chalk.cyan(config.api_url)}`);
          console.log(`Timeout: ${chalk.cyan(config.timeout)}ms`);
          console.log(`Config file: ${chalk.gray(getConfigPath())}`);
          console.log('');
          return;
        }
        
        if (options.reset) {
          const answer = await inquirer.prompt([
            {
              type: 'confirm',
              name: 'confirm',
              message: 'Are you sure you want to reset the configuration?',
              default: false
            }
          ]);
          
          if (answer.confirm) {
            saveConfig({
              api_url: 'http://localhost:8000',
              timeout: 30000
            });
            printSuccess('Configuration reset to defaults');
          }
          return;
        }
        
        // Set specific options
        let updated = false;
        const updates: any = {};
        
        if (options.apiUrl) {
          if (!isValidUrl(options.apiUrl)) {
            printError(`Invalid API URL: ${options.apiUrl}`);
            process.exit(1);
          }
          updates.api_url = options.apiUrl;
          updated = true;
        }
        
        if (options.timeout) {
          const timeout = parseInt(options.timeout);
          if (isNaN(timeout) || timeout < 1000) {
            printError('Timeout must be a number >= 1000 milliseconds');
            process.exit(1);
          }
          updates.timeout = timeout;
          updated = true;
        }
        
        if (updated) {
          saveConfig(updates);
          printSuccess('Configuration updated');
          
          // Show updated config
          const config = getConfig();
          console.log(`API URL: ${chalk.cyan(config.api_url)}`);
          console.log(`Timeout: ${chalk.cyan(config.timeout)}ms`);
          return;
        }
        
        // Interactive configuration
        const currentConfig = getConfig();
        
        const answers = await inquirer.prompt([
          {
            type: 'input',
            name: 'api_url',
            message: 'API URL:',
            default: currentConfig.api_url,
            validate: (input: string) => {
              if (!input.trim()) return 'API URL is required';
              if (!isValidUrl(input)) return 'Please enter a valid URL';
              return true;
            }
          },
          {
            type: 'number',
            name: 'timeout',
            message: 'Request timeout (ms):',
            default: currentConfig.timeout,
            validate: (input: number) => {
              if (!input || input < 1000) return 'Timeout must be >= 1000 milliseconds';
              return true;
            }
          }
        ]);
        
        saveConfig(answers);
        printSuccess('Configuration saved');
        
      } catch (error) {
        printError('Failed to update configuration', error as Error);
        process.exit(1);
      }
    });

  return configCommand;
}