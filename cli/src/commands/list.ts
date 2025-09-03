import chalk from 'chalk'
import { Command } from 'commander'
import { ensureApiConnection } from '../middleware/api-connection'
import { formatJobStatus, printError } from '../utils'

export function createListCommand(): Command {
  const listCommand = new Command('list')

  listCommand
    .description('List all scraping jobs')
    .option('-l, --limit <number>', 'Maximum number of jobs to show', '10')
    .option('-a, --all', 'Show all jobs (ignore limit)')
    .action(async (options) => {
      try {
        const api = await ensureApiConnection()
        const limit = options.all ? undefined : parseInt(options.limit)
        const response = await api.listJobs(limit)

        if (response.jobs.length === 0) {
          console.log('No jobs found.')
          return
        }

        console.log(`\n${chalk.bold('Recent Jobs')} ${chalk.gray(`(${response.jobs.length} of ${response.total})`)}`)
        console.log('')

        for (const job of response.jobs) {
          const line = formatJobStatus(job)
          let details = ''

          if (job.progress?.files_created) {
            details += chalk.gray(` • ${job.progress.files_created} files`)
          }

          if (job.error_message) {
            details += chalk.red(' • Error: ') + chalk.gray(job.error_message.substring(0, 50))
            if (job.error_message.length > 50) details += chalk.gray('...')
          }

          console.log(line + details)
        }

        console.log('')
        console.log(chalk.gray(`Use ${chalk.bold('aimdoc status <job-id>')} for detailed information`))
        console.log(chalk.gray(`Use ${chalk.bold('aimdoc download <job-id>')} to download completed jobs`))
        console.log('')
      } catch (error) {
        printError('Failed to list jobs', error as Error)
        process.exit(1)
      }
    })

  return listCommand
}
