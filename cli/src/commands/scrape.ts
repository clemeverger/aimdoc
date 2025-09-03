import chalk from 'chalk'
import { Command } from 'commander'
import fs from 'fs-extra'
import inquirer from 'inquirer'
import ora from 'ora'
import path from 'path'
import WebSocket from 'ws'
import { AimdocAPI } from '../api'
import { JobStatus, ScrapeRequest, WebSocketJobUpdate } from '../types'
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
        const api = new AimdocAPI()

        // Health check
        const spinner = ora('Connecting to API...').start()
        const isHealthy = await api.healthCheck()

        if (!isHealthy) {
          spinner.fail('API is not available. Make sure the server is running.')
          process.exit(1)
        }
        spinner.succeed('Connected to API')

        // Get scrape parameters
        const scrapeRequest = await getScrapeRequest(url, options)

        // Get output directory
        const outputDir = await getOutputDirectory(options)
        const folderName = scrapeRequest.name // Use project name as folder name

        // Create job
        const createSpinner = ora('Creating scrape job...').start()
        const job = await api.createScrapeJob(scrapeRequest)
        createSpinner.succeed(`Job created: ${chalk.bold(job.job_id)}`)

        printInfo(`Job details can be found at: ${chalk.underline(`http://localhost:8000/docs#/jobs/get_job_status_api_v1_jobs__job_id__get`)}`)

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

async function waitForCompletionWithWebSocket(api: AimdocAPI, jobId: string, projectName: string, outputDir: string, folderName: string): Promise<void> {
  const spinner = ora('Connecting to job...').start()
  let ws: WebSocket | null = null

  try {
    ws = await api.connectToJobWebSocket(
      jobId,
      async (update: WebSocketJobUpdate) => {
        if (update.type === 'status_update') {
          if (spinner) {
            let message = update.message || 'Processing...'

            if (update.progress) {
              const { pages_found = 0, pages_scraped = 0, files_created = 0 } = update.progress
              if (pages_found > 0 || pages_scraped > 0 || files_created > 0) {
                message = `Found ${pages_found} pages, scraped ${pages_scraped}, created ${files_created} files`
              }
            }

            spinner.text = message
          }

          if (update.status === JobStatus.COMPLETED) {
            if (spinner) spinner.succeed('Scraping completed successfully!')

            if (update.result_summary) {
              printSuccess(`Created ${update.result_summary.files_created} files from ${update.progress?.pages_scraped || 0} pages`)
            }

            // Auto-download results
            await downloadResults(api, jobId, projectName, outputDir, folderName)

            ws?.close()
          } else if (update.status === JobStatus.FAILED) {
            if (spinner) spinner.fail('Scraping failed')
            printError(update.error || update.message || 'Job failed with unknown error')
            ws?.close()
            process.exit(1)
          }
        }
      },
      (error: Error) => {
        console.log('WebSocket error, falling back to polling...')
        // Don't exit, let it fall through to fallback
      },
      () => {
        // WebSocket closed
      }
    )

    if (spinner) spinner.text = 'Connected! Starting scrape...'
  } catch (error) {
    // Fallback to polling if WebSocket fails
    if (spinner) {
      spinner.text = 'WebSocket unavailable, falling back to polling...'
    }
    await waitForCompletionFallback(api, jobId, projectName, outputDir, folderName)
  }
}

async function downloadResults(api: AimdocAPI, jobId: string, projectName: string, outputDir: string, folderName: string): Promise<void> {
  const downloadSpinner = ora('Downloading results...').start()

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

async function waitForCompletionFallback(api: AimdocAPI, jobId: string, projectName: string, outputDir: string, folderName: string): Promise<void> {
  const spinner = ora('Starting scrape...').start()

  let lastStatus: JobStatus | null = null
  let lastProgress: any = null

  while (true) {
    try {
      const status = await api.getJobStatus(jobId)

      if (spinner) {
        if (status.status !== lastStatus || JSON.stringify(status.progress) !== JSON.stringify(lastProgress)) {
          let message = 'Processing...'
          if (status.progress) {
            const { pages_found = 0, pages_scraped = 0, files_created = 0 } = status.progress
            if (pages_found > 0) {
              message = `Found ${pages_found} pages, scraped ${pages_scraped}, created ${files_created} files`
            }
          }

          spinner.text = message
          lastStatus = status.status
          lastProgress = status.progress
        }
      }

      if (status.status === JobStatus.COMPLETED) {
        if (spinner) spinner.succeed('Scraping completed successfully!')

        if (status.result_summary) {
          printSuccess(`Created ${status.result_summary.files_created} files`)
        }

        await downloadResults(api, jobId, projectName, outputDir, folderName)
        break
      }

      if (status.status === JobStatus.FAILED) {
        if (spinner) spinner.fail('Scraping failed')
        printError(status.error_message || 'Job failed with unknown error')
        process.exit(1)
      }

      // Wait before checking again
      await new Promise((resolve) => setTimeout(resolve, 2000))
    } catch (error) {
      if (spinner) spinner.fail('Error checking job status')
      printError('Failed to check job status', error as Error)
      process.exit(1)
    }
  }
}
