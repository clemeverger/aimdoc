import chalk from 'chalk'
import cliProgress from 'cli-progress'
import { Command } from 'commander'
import { ensureApiConnection } from '../middleware/api-connection'
import { formatFileSize, formatJobStatus, printError, printInfo } from '../utils'

export function createStatusCommand(): Command {
  const statusCommand = new Command('status')

  statusCommand
    .description('Check the status of a scraping job')
    .argument('<job-id>', 'Job ID to check')
    .option('-v, --verbose', 'Show detailed information')
    .action(async (jobId: string, options) => {
      try {
        const api = await ensureApiConnection()
        const status = await api.getJobStatus(jobId)

        console.log(`\n${chalk.bold('Job Status')}`)
        console.log(`ID: ${chalk.bold(status.job_id)}`)
        console.log(`Status: ${formatJobStatus(status)}`)
        console.log(`Created: ${new Date(status.created_at).toLocaleString()}`)

        if (status.started_at) {
          console.log(`Started: ${new Date(status.started_at).toLocaleString()}`)
        }

        if (status.completed_at) {
          console.log(`Completed: ${new Date(status.completed_at).toLocaleString()}`)
        }

        if (status.progress) {
          console.log(`\n${chalk.bold('Progress')}`)
          const { pages_found = 0, pages_scraped = 0, files_created = 0 } = status.progress
          console.log(`Pages found: ${pages_found}`)
          console.log(`Pages scraped: ${pages_scraped}`)
          console.log(`Files created: ${files_created}`)

          // Add a progress bar visualization if we have pages found
          if (pages_found > 0) {
            const progressBar = new cliProgress.SingleBar(
              {
                format: 'Scraping progress |{bar}| {percentage}% | {value}/{total} pages',
                barCompleteChar: '\u2588',
                barIncompleteChar: '\u2591',
                hideCursor: false,
                clearOnComplete: false,
              },
              cliProgress.Presets.shades_classic
            )

            console.log('') // Empty line before progress bar
            progressBar.start(pages_found, pages_scraped)
            progressBar.update(pages_scraped)
            progressBar.stop()
          }
        }

        if (status.result_summary && options.verbose) {
          console.log(`\n${chalk.bold('Results')}`)
          console.log(`Files: ${status.result_summary.files_created}`)
          if (status.result_summary.build_size) {
            console.log(`Size: ${formatFileSize(status.result_summary.build_size)}`)
          }
          if (status.result_summary.build_path) {
            console.log(`Path: ${status.result_summary.build_path}`)
          }
        }

        if (status.error_message) {
          console.log(`\n${chalk.red('Error')}`)
          console.log(status.error_message)
        }

        // Show next steps
        if (status.status === 'completed') {
          printInfo(`\nUse ${chalk.bold(`aimdoc download ${jobId}`)} to download the results`)
          printInfo(`Use ${chalk.bold(`aimdoc results ${jobId}`)} to see file list`)
        } else if (status.status === 'running') {
          printInfo(`\nJob is still running. Check again in a few moments.`)
        }

        console.log('') // Empty line
      } catch (error) {
        printError('Failed to get job status', error as Error)
        process.exit(1)
      }
    })

  return statusCommand
}
