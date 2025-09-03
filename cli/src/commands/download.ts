import chalk from 'chalk'
import { Command } from 'commander'
import * as fs from 'fs-extra'
import inquirer from 'inquirer'
import ora from 'ora'
import * as path from 'path'
import { AimdocAPI } from '../api'
import { printError, printInfo, printSuccess, sanitizeFilename, validateOutputDirectory } from '../utils'

async function generateReadmeIndex(docsPath: string): Promise<void> {
  try {
    const readmePath = path.join(docsPath, 'README.md')

    // Check if README already exists (it should have been created by the backend).
    if (await fs.pathExists(readmePath)) {
      return
    }

    // Fallback README generation if it's missing.
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
    if (mdFiles.length === 0) return

    const structure: Record<string, string[]> = {}
    mdFiles.forEach((file) => {
      const dir = path.dirname(file)
      if (!structure[dir]) structure[dir] = []
      structure[dir].push(path.basename(file, '.md'))
    })

    const readmeContent = `# Documentation Index\n\n${Object.entries(structure)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([dir, files]) => {
        const header = dir === '.' ? '' : `### ${dir}\n\n`
        return header + files.map((file) => `- [${file}](./${path.join(dir, file)}.md)`).join('\n')
      })
      .join('\n\n')}`

    await fs.writeFile(readmePath, readmeContent, 'utf-8')
    printSuccess(`Generated fallback README.md index with ${mdFiles.length} files`)
  } catch (error) {
    console.warn('Warning: Could not generate fallback README.md index')
  }
}

export function createDownloadCommand(): Command {
  const downloadCommand = new Command('download')

  downloadCommand
    .description('Download results from a completed job')
    .argument('<job-id>', 'Job ID to download')
    .option('-o, --output-dir <dir>', 'Output directory for the documentation', './docs')
    .option('--overwrite', 'Overwrite existing files if they already exist')
    .action(async (jobId: string, options) => {
      const spinner = ora('Initializing download...').start()
      try {
        const api = new AimdocAPI()

        // 1. Get job status to find the project name.
        spinner.text = 'Fetching job details...'
        const status = await api.getJobStatus(jobId)
        if (!status || !status.result_summary) {
          spinner.fail(`Could not retrieve details for job ${jobId}. Ensure the job has completed successfully.`)
          process.exit(1)
        }
        const projectName = sanitizeFilename(status.request?.name || jobId)

        // 2. Get the list of files to download.
        spinner.text = 'Fetching file list...'
        const results = await api.getJobResults(jobId)
        if (!results || results.files.length === 0) {
          spinner.succeed('No files available to download for this job.')
          return
        }
        spinner.succeed(`Found ${results.files.length} files to download.`)

        // 3. Set up the local destination directory.
        const finalDir = path.join(options.outputDir, projectName)
        await fs.ensureDir(finalDir)
        const isValid = await validateOutputDirectory(finalDir)
        if (!isValid) {
          spinner.fail(`Output directory '${finalDir}' is not writable or cannot be created.`)
          process.exit(1)
        }

        // 4. Check for existing files and confirm overwrite if necessary.
        if (!options.overwrite) {
          const existingFiles = (await Promise.all(results.files.map((file) => fs.pathExists(path.join(finalDir, file))))).filter(Boolean)
          if (existingFiles.length > 0) {
            spinner.stop()
            const { confirmOverwrite } = await inquirer.prompt([
              {
                type: 'confirm',
                name: 'confirmOverwrite',
                message: `${existingFiles.length} file(s) already exist in the destination. Overwrite?`,
                default: false,
              },
            ])
            if (!confirmOverwrite) {
              printInfo('Download cancelled.')
              return
            }
            spinner.start()
          }
        }

        // 5. Download all files.
        spinner.text = `Downloading ${results.files.length} files...`
        let downloadedCount = 0
        for (const file of results.files) {
          try {
            const fileData = await api.downloadFile(jobId, file)
            const outputPath = path.join(finalDir, file)
            await fs.ensureDir(path.dirname(outputPath))
            await fs.writeFile(outputPath, fileData)
            downloadedCount++
            spinner.text = `Downloaded ${downloadedCount}/${results.files.length} files...`
          } catch (error) {
            spinner.warn(`Failed to download ${file}: ${(error as Error).message}`)
          }
        }

        if (downloadedCount === results.files.length) {
          spinner.succeed(`Successfully downloaded all ${downloadedCount} files.`)
        } else {
          spinner.warn(`Downloaded ${downloadedCount}/${results.files.length} files, some failed.`)
        }

        printSuccess(`Documentation saved in: ${chalk.underline(finalDir)}`)

        // 6. Generate a fallback README if the backend didn't provide one.
        await generateReadmeIndex(finalDir)
      } catch (error) {
        spinner.fail('An unexpected error occurred during download.')
        printError('Download failed', error as Error)
        process.exit(1)
      }
    })

  return downloadCommand
}
