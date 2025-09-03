import chalk from 'chalk'
import cliProgress from 'cli-progress'
import { Command } from 'commander'
import fs from 'fs-extra'
import inquirer from 'inquirer'
import ora from 'ora'
import path from 'path'
import WebSocket from 'ws'
import { AimdocAPI } from '../api'
import { ensureApiConnection } from '../middleware/api-connection'
import { JobPhase, JobStatus, ScrapeRequest, WebSocketJobUpdate } from '../types'
import { extractDomainName, isValidUrl, printError, printInfo, printSuccess, validateOutputDirectory } from '../utils'

export function createScrapeCommand(): Command {
  const scrapeCommand = new Command('scrape')

  scrapeCommand
    .description('Start a new documentation scraping job')
    .argument('[url]', 'URL of the documentation site to scrape')
    .option('-n, --name <name>', 'Project name (defaults to the domain name)')
    .option('-o, --output-dir <dir>', 'Output directory for the documentation', './docs')
    .action(async (url: string | undefined, options) => {
      try {
        // Ensure API connection with centralized retry logic
        const api = await ensureApiConnection()

        // Get scrape parameters
        const scrapeRequest = await getScrapeRequest(url, options)

        // Get output directory
        const outputDir = await getOutputDirectory(options)
        const folderName = scrapeRequest.name // Use project name as folder name

        // Create job
        const createSpinner = ora({
          text: 'Creating scrape job...',
          discardStdin: false,
        }).start()
        const job = await api.createScrapeJob(scrapeRequest)
        createSpinner.succeed(`Job created: ${chalk.bold(job.job_id)}`)

        // Wait for job completion and download results
        await waitForCompletionWithWebSocket(api, job.job_id, scrapeRequest.name, outputDir, folderName)
      } catch (error) {
        console.error('Detailed error:', error)
        printError('Failed to create scrape job', error as Error)
        process.exit(1)
      }
    })

  return scrapeCommand
}

async function getScrapeRequest(url: string | undefined, options: any): Promise<ScrapeRequest> {
  const request: Partial<ScrapeRequest> = {}

  // Get URL
  if (url) {
    if (!isValidUrl(url)) {
      throw new Error(`Invalid URL: ${url}`)
    }
    request.url = url
  } else {
    const urlAnswer = await inquirer.prompt([
      {
        type: 'input',
        name: 'url',
        message: 'Documentation URL:',
        validate: (input: string) => {
          if (!input.trim()) return 'URL is required'
          if (!isValidUrl(input)) return 'Please enter a valid URL'
          return true
        },
      },
    ])
    request.url = urlAnswer.url
  }

  // Get name
  if (options.name) {
    request.name = options.name
  } else {
    const defaultName = extractDomainName(request.url!)
    const nameAnswer = await inquirer.prompt([
      {
        type: 'input',
        name: 'name',
        message: 'Project name:',
        default: defaultName,
        validate: (input: string) => (input.trim() ? true : 'Project name is required'),
      },
    ])
    request.name = nameAnswer.name
  }

  // MVP mode is always 'bundle' which is the default on the backend. No need to set it.

  return request as ScrapeRequest
}

async function getOutputDirectory(options: any): Promise<string> {
  let outputDir = options.outputDir

  const dirAnswer = await inquirer.prompt([
    {
      type: 'input',
      name: 'outputDir',
      message: 'Output directory:',
      default: outputDir || './docs',
      validate: async (input: string) => {
        if (!input.trim()) return 'Output directory is required'
        const isValid = await validateOutputDirectory(input)
        return isValid ? true : 'Directory is not writable or cannot be created'
      },
    },
  ])
  outputDir = dirAnswer.outputDir

  // Validate the provided directory
  const isValid = await validateOutputDirectory(outputDir)
  if (!isValid) {
    printError(`Directory '${outputDir}' is not writable or cannot be created`)
    process.exit(1)
  }

  return outputDir
}

// Helper functions to avoid TypeScript control flow issues
function stopSpinner(spinner: ReturnType<typeof ora> | null): void {
  if (spinner) {
    spinner.stop()
  }
}

function succeedSpinner(spinner: ReturnType<typeof ora> | null, message: string): void {
  if (spinner) {
    spinner.succeed(message)
  }
}

function stopProgressBar(bar: cliProgress.SingleBar | null): void {
  if (bar) {
    bar.stop()
  }
}

async function waitForCompletionWithWebSocket(api: AimdocAPI, jobId: string, projectName: string, outputDir: string, folderName: string): Promise<void> {
  let ws: WebSocket | null = null
  let progressBar: cliProgress.SingleBar | null = null
  let currentSpinner: ReturnType<typeof ora> | null = null
  let lastProgress = { pages_scraped: 0, files_created: 0, pages_found: 0 }
  let currentPhase: JobPhase | null = null
  let connectionMessageHandled = false

  // Start connection spinner
  const connectionSpinner = ora({
    text: 'Connecting to job...',
    discardStdin: false,
  }).start()

  try {
    ws = await api.connectToJobWebSocket(
      jobId,
      async (update: WebSocketJobUpdate) => {
        if (update.type === 'status_update') {
          // Handle initial connection message (only once)
          if (update.message && update.message.includes('Connected to job') && !connectionMessageHandled) {
            connectionMessageHandled = true
            connectionSpinner.succeed('Connected to job')
          }

          const phase = update.phase || JobPhase.DISCOVERING
          const { pages_found = 0, pages_scraped = 0, files_created = 0 } = update.progress || {}

          // Handle phase transitions
          if (phase !== currentPhase) {
            // Stop current progress indicator
            stopProgressBar(progressBar)
            progressBar = null
            stopSpinner(currentSpinner)
            currentSpinner = null

            currentPhase = phase

            // Start appropriate progress indicator for new phase
            if (phase === JobPhase.DISCOVERING) {
              currentSpinner = ora({
                text: 'Discovering sitemap and pages...',
                discardStdin: false,
              }).start()
            } else if (phase === JobPhase.SCRAPING && pages_found > 0) {
              succeedSpinner(currentSpinner, `Found ${pages_found} pages to scrape`)
              currentSpinner = null
              progressBar = new cliProgress.SingleBar(
                {
                  format: 'Scraping |{bar}| {value}/{total} pages',
                  barCompleteChar: '\u2588',
                  barIncompleteChar: '\u2591',
                  hideCursor: true,
                  clearOnComplete: false,
                  stopOnComplete: false,
                  barsize: 40,
                },
                cliProgress.Presets.shades_classic
              )
              progressBar.start(pages_found, pages_scraped, { files_created })
            } else if (phase === JobPhase.CONVERTING) {
              stopProgressBar(progressBar)
              progressBar = null
              currentSpinner = ora({
                text: 'Converting pages to markdown...',
                discardStdin: false,
              }).start()
            } else if (phase === JobPhase.DOWNLOADING) {
              stopSpinner(currentSpinner)
              currentSpinner = null
              currentSpinner = ora({
                text: 'Preparing files for download...',
                discardStdin: false,
              }).start()
            }
          }

          // Update progress indicators
          if (phase === JobPhase.SCRAPING && progressBar) {
            progressBar.update(pages_scraped, { files_created })
          } else if (phase === JobPhase.CONVERTING && currentSpinner) {
            currentSpinner.text = `Converting to markdown... ${files_created} files created`
          } else if (currentSpinner && update.message) {
            currentSpinner.text = update.message
          }

          lastProgress = { pages_scraped, files_created, pages_found }

          if (update.status === JobStatus.COMPLETED) {
            // Stop all progress indicators
            if (progressBar) {
              progressBar.update(pages_scraped, { files_created })
              stopProgressBar(progressBar)
            }
            succeedSpinner(currentSpinner, 'Scraping completed!')
            currentSpinner = null

            console.log('\n✅ Scraping completed successfully!')
            if (update.result_summary) {
              const summary = update.result_summary
              const successMessage = `✓ Created ${summary.files_created} files from ${pages_scraped} pages`

              // Add diagnostic info if there were failed pages
              if (summary.pages_failed && summary.pages_failed > 0) {
                console.log(`${successMessage} (${summary.pages_failed} pages failed)`)
                console.log(`ℹ️  ${chalk.yellow(`${summary.pages_discovered || 'Unknown'} pages discovered, ${summary.pages_failed} failed to scrape`)}`)
              } else {
                console.log(successMessage)
                if (summary.pages_discovered) {
                  console.log(`ℹ️  ${chalk.green(`All ${summary.pages_discovered} discovered pages scraped successfully`)}`)
                }
              }
            }

            await downloadResults(api, jobId, projectName, outputDir, folderName)
            ws?.close()
          } else if (update.status === JobStatus.FAILED) {
            // Stop all progress indicators
            stopProgressBar(progressBar)
            if (currentSpinner) {
              currentSpinner.fail('Scraping failed')
            }
            console.log('\n❌ Scraping failed')
            printError(update.error || update.message || 'Job failed with unknown error')
            ws?.close()
            process.exit(1)
          }
        }
      },
      (error: Error) => {
        connectionSpinner.fail('WebSocket connection failed')
        printError('WebSocket connection failed', error)
        process.exit(1)
      },
      () => {
        // WebSocket closed
      }
    )

    // Connection message will come from WebSocket initial update
  } catch (error) {
    connectionSpinner.fail('WebSocket unavailable')
    printError('WebSocket unavailable', error as Error)
    process.exit(1)
  }
}

async function downloadResults(api: AimdocAPI, jobId: string, projectName: string, outputDir: string, folderName: string): Promise<void> {
  const downloadSpinner = ora({
    text: 'Downloading and organizing files...',
    discardStdin: false,
  }).start()

  try {
    // Create the final directory
    const finalDir = path.join(outputDir, folderName)
    await fs.ensureDir(finalDir)

    // Download files directly
    downloadSpinner.text = 'Getting file list...'

    // Get list of files
    const results = await api.getJobResults(jobId)

    if (results.files.length === 0) {
      downloadSpinner.warn('No files to download')
      return
    }

    downloadSpinner.text = `Downloading ${results.files.length} files...`

    // Track what we've downloaded
    let downloadedCount = 0
    const downloadedDirs = new Set<string>()

    // Download each file individually
    for (const filePath of results.files) {
      try {
        // Download file content
        const fileData = await api.downloadFile(jobId, filePath)

        // Determine target path

        const targetPath = path.join(finalDir, filePath)

        // Ensure directory exists
        const targetDir = path.dirname(targetPath)
        if (!downloadedDirs.has(targetDir)) {
          await fs.ensureDir(targetDir)

          downloadedDirs.add(targetDir)
        }

        // Write file
        await fs.writeFile(targetPath, fileData)
        downloadedCount++

        downloadSpinner.text = `Downloaded ${downloadedCount}/${results.files.length} files...`
      } catch (error) {
        console.warn(`Failed to download ${filePath}: ${(error as Error).message}`)
      }
    }

    if (downloadedCount === results.files.length) {
      downloadSpinner.succeed(`Downloaded all ${downloadedCount} files`)
    } else {
      downloadSpinner.warn(`Downloaded ${downloadedCount}/${results.files.length} files (some failed)`)
    }

    printSuccess(`Documentation organized in: ${chalk.underline(finalDir)}`)

    // Generate README index
    await generateReadmeIndex(finalDir)
  } catch (error) {
    downloadSpinner.fail('Failed to download results')
    printError('Download error', error as Error)
    printInfo(`You can try downloading manually: ${chalk.bold(`aimdoc download ${jobId}`)}`)
  }
}

async function generateReadmeIndex(docsPath: string): Promise<void> {
  try {
    const readmePath = path.join(docsPath, 'README.md')

    // Get all markdown files recursively
    const getAllMdFiles = async (dir: string, relativePath = ''): Promise<string[]> => {
      const files: string[] = []
      const entries = await fs.readdir(dir, { withFileTypes: true })

      for (const entry of entries) {
        if (entry.isDirectory()) {
          const subFiles = await getAllMdFiles(path.join(dir, entry.name), path.join(relativePath, entry.name))
          files.push(...subFiles)
        } else if (entry.name.endsWith('.md') && entry.name !== 'README.md') {
          files.push(path.join(relativePath, entry.name))
        }
      }
      return files
    }

    const mdFiles = await getAllMdFiles(docsPath)

    // Group files by directory
    const structure: Record<string, string[]> = {}
    mdFiles.forEach((file) => {
      const dir = path.dirname(file)
      if (!structure[dir]) structure[dir] = []
      structure[dir].push(path.basename(file, '.md'))
    })

    // Generate README content
    const readmeContent = `# Documentation Index

Generated on ${new Date().toISOString()}

## Structure

${Object.entries(structure)
  .sort(([a], [b]) => a.localeCompare(b))
  .map(([dir, files]) => {
    if (dir === '.') {
      return files.map((file) => `- [${file}](./${file}.md)`).join('\n')
    } else {
      return `\n### ${dir}\n\n${files.map((file) => `- [${file}](./${dir}/${file}.md)`).join('\n')}`
    }
  })
  .join('\n')}

---
*Generated with [aimdoc](https://github.com/anthropic/doc-pack)*
`

    await fs.writeFile(readmePath, readmeContent, 'utf-8')
    printSuccess(`Generated README.md index with ${mdFiles.length} files`)
  } catch (error) {
    // Don't fail the whole process if README generation fails
    console.warn('Warning: Could not generate README.md index')
  }
}
