import chalk from 'chalk'
import { Command } from 'commander'
import fs from 'fs-extra'
import path from 'path'
import { AimdocAPI } from '../api'
import { printError, printInfo, printSuccess } from '../utils'

export function createDiagnoseCommand(): Command {
  const diagnoseCommand = new Command('diagnose')

  diagnoseCommand
    .description('Diagnose a completed or failed scraping job')
    .argument('<job_id>', 'ID of the job to diagnose')
    .option('--verbose', 'Show detailed information about failed pages')
    .action(async (jobId: string, options) => {
      try {
        const api = new AimdocAPI()

        // Get job status
        const job = await api.getJobStatus(jobId)
        if (!job) {
          printError(`Job ${jobId} not found`)
          process.exit(1)
        }

        console.log(`\n=== Job Diagnosis: ${chalk.bold(jobId)} ===`)
        console.log(`Status: ${getStatusDisplay(job.status)}`)
        console.log(`Created: ${job.created_at}`)
        if (job.started_at) console.log(`Started: ${job.started_at}`)
        if (job.completed_at) console.log(`Completed: ${job.completed_at}`)

        // Show summary if available
        if (job.result_summary) {
          const summary = job.result_summary
          console.log(`\n=== Results Summary ===`)
          console.log(`📄 Files created: ${chalk.bold(summary.files_created || 0)}`)
          console.log(`✅ Pages scraped: ${chalk.bold(summary.pages_scraped || 0)}`)
          console.log(`❌ Pages failed: ${chalk.bold(summary.pages_failed || 0)}`)
          console.log(`🔍 Pages discovered: ${chalk.bold(summary.pages_discovered || 'Unknown')}`)
          
          if (summary.build_size) {
            const sizeInMB = (summary.build_size / (1024 * 1024)).toFixed(2)
            console.log(`📦 Build size: ${sizeInMB} MB`)
          }
        }

        // Try to read scraping summary file for detailed diagnostics
        if (options.verbose) {
          try {
            // Attempt to find the job directory and read the scraping summary
            const jobsDir = path.join(process.cwd(), 'jobs')
            const jobDir = path.join(jobsDir, jobId)
            const summaryFile = path.join(jobDir, 'scraping_summary.json')

            if (await fs.pathExists(summaryFile)) {
              const summaryData = await fs.readJson(summaryFile)
              
              console.log(`\n=== Detailed Diagnostics ===`)
              console.log(`Spider close reason: ${summaryData.spider_close_reason || 'Unknown'}`)
              
              // Show discovery errors first as they're often the root cause
              if (summaryData.discovery_errors && summaryData.discovery_errors.length > 0) {
                console.log(`\n❌ Discovery Errors (${summaryData.discovery_errors.length}):`)
                summaryData.discovery_errors.forEach((error: any, index: number) => {
                  console.log(`  ${index + 1}. ${chalk.red(error.url)}`)
                  console.log(`     Error: ${error.error_type}: ${error.error}`)
                })
                
                // Add helpful explanation for common sitemap issues
                const sitemapErrors = summaryData.discovery_errors.filter((e: any) => 
                  e.url.includes('sitemap') || e.url.includes('robots.txt'))
                if (sitemapErrors.length > 0) {
                  console.log(`\n💡 ${chalk.yellow('Tip:')} This website appears to have no sitemap or an inaccessible sitemap.`)
                  console.log(`   Consider trying a different website that has a sitemap.xml file.`)
                  console.log(`   You can check if a site has a sitemap by visiting: ${chalk.underline('[website-url]/sitemap.xml')}`)
                }
              }
              
              if (summaryData.failed_pages && summaryData.failed_pages.length > 0) {
                console.log(`\n❌ Failed Pages (${summaryData.failed_pages.length}):`)
                summaryData.failed_pages.forEach((failed: any, index: number) => {
                  console.log(`  ${index + 1}. ${chalk.red(failed.url)}`)
                  console.log(`     Reason: ${failed.reason}`)
                  if (failed.status) {
                    console.log(`     Status: ${failed.status}`)
                  }
                })
              } else if (!summaryData.discovery_errors || summaryData.discovery_errors.length === 0) {
                console.log(`\n✅ No failed pages`)
              }

              if (summaryData.chapters) {
                console.log(`\n📚 Chapters discovered:`)
                Object.entries(summaryData.chapters).forEach(([chapter, count]) => {
                  console.log(`  • ${chapter}: ${count} pages`)
                })
              }
            } else {
              printInfo('Detailed diagnostics not available (scraping_summary.json not found)')
            }
          } catch (error) {
            printError('Failed to read detailed diagnostics', error as Error)
          }
        } else {
          printInfo('Use --verbose for detailed diagnostics including failed pages')
        }

        // Show error message if job failed
        if (job.error_message) {
          console.log(`\n❌ Error: ${chalk.red(job.error_message)}`)
        }

      } catch (error) {
        console.error('Detailed error:', error)
        printError('Failed to diagnose job', error as Error)
        process.exit(1)
      }
    })

  return diagnoseCommand
}

function getStatusDisplay(status: string): string {
  const statusColors = {
    'completed': chalk.green('✅ COMPLETED'),
    'failed': chalk.red('❌ FAILED'),
    'running': chalk.yellow('🔄 RUNNING'),
    'pending': chalk.blue('⏳ PENDING')
  }
  
  return statusColors[status as keyof typeof statusColors] || chalk.gray(`❓ ${status.toUpperCase()}`)
}