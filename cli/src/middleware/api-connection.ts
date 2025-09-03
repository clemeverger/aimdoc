import ora from 'ora'
import { AimdocAPI } from '../api'

let globalApiInstance: AimdocAPI | null = null
let apiConnectionVerified = false

/**
 * Ensures API connection is established with retry logic for services like Render
 * Returns a verified API instance
 */
export async function ensureApiConnection(): Promise<AimdocAPI> {
  // Return existing instance if already verified
  if (globalApiInstance && apiConnectionVerified) {
    return globalApiInstance
  }

  const api = new AimdocAPI()

  // Health check with retry logic for services like Render that may be sleeping
  const spinner = ora({
    text: 'Connecting to API...',
    discardStdin: false,
  }).start()

  // Try quick health check first
  let isHealthy = await api.healthCheck()

  if (!isHealthy) {
    // Service might be sleeping (e.g., on Render), try with retries
    spinner.text = 'API unavailable, waiting for service to wake up...'

    const maxRetries = 12
    const initialDelay = 2000

    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        isHealthy = await api.healthCheck()
        if (isHealthy) {
          break
        }
      } catch {
        // Continue to retry
      }

      if (attempt < maxRetries) {
        const delay = Math.min(initialDelay * attempt, 10000)
        spinner.text = `API unavailable, retrying in ${delay / 1000}s... (attempt ${attempt}/${maxRetries})`
        await new Promise((resolve) => setTimeout(resolve, delay))
      }
    }
  }

  if (!isHealthy) {
    spinner.fail('API is not available after multiple attempts. Make sure the server is running.')
    process.exit(1)
  }

  spinner.succeed('Connected to API')

  // Cache the verified connection
  globalApiInstance = api
  apiConnectionVerified = true

  return api
}

/**
 * Creates a new API instance without connection verification
 * Use this for commands that might work offline or don't need immediate connection
 */
export function createApiInstance(): AimdocAPI {
  return new AimdocAPI()
}

/**
 * Reset the global API connection state (useful for testing)
 */
export function resetApiConnection(): void {
  globalApiInstance = null
  apiConnectionVerified = false
}
