#!/usr/bin/env node

import { Command } from 'commander';
import chalk from 'chalk';
import { createScrapeCommand } from './commands/scrape';
import { createStatusCommand } from './commands/status';
import { createListCommand } from './commands/list';
import { createDownloadCommand } from './commands/download';
import { createResultsCommand } from './commands/results';
import { createDeleteCommand } from './commands/delete';
import { createConfigCommand } from './commands/config';
import { printError } from './utils';

const program = new Command();

// Set up the main program
program
  .name('aimdoc')
  .description('AI-friendly documentation scraper CLI')
  .version('1.0.0')
  .helpOption('-h, --help', 'Display help for command');

// Add commands
program.addCommand(createScrapeCommand());
program.addCommand(createStatusCommand());
program.addCommand(createListCommand());
program.addCommand(createDownloadCommand());
program.addCommand(createResultsCommand());
program.addCommand(createDeleteCommand());
program.addCommand(createConfigCommand());

// Add global error handling
process.on('unhandledRejection', (reason, promise) => {
  if (process.env.DEBUG) {
    console.error('Unhandled Rejection at:', promise, 'reason:', reason);
  }
  printError('An unexpected error occurred');
  process.exit(1);
});

process.on('uncaughtException', (error) => {
  if (process.env.DEBUG) {
    console.error('Uncaught Exception:', error);
  }
  printError('An unexpected error occurred');
  process.exit(1);
});

// Custom help
program.on('--help', () => {
  console.log('');
  console.log('Examples:');
  console.log('  $ aimdoc scrape https://react.dev');
  console.log('  $ aimdoc scrape https://docs.python.org --name python --mode single');
  console.log('  $ aimdoc list');
  console.log('  $ aimdoc status abc123def');
  console.log('  $ aimdoc download abc123def');
  console.log('  $ aimdoc config --api-url http://localhost:8000');
  console.log('');
  console.log('Environment variables:');
  console.log('  DEBUG=1          Enable debug output');
  console.log('');
  console.log('For more information, visit: https://github.com/your-org/aimdoc');
});

// Parse command line arguments
program.parse();

// If no command was provided, show help
if (!process.argv.slice(2).length) {
  program.outputHelp();
}