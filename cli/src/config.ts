import * as fs from 'fs-extra'
import * as os from 'os'
import * as path from 'path'
import { Config } from './types'

const DEFAULT_CONFIG: Config = {
  api_url: 'https://aimdoc.onrender.com',
  /* api_url: 'http://0.0.0.0:8000', */
  timeout: 30000,
}

const CONFIG_DIR = path.join(os.homedir(), '.aimdoc')
const CONFIG_FILE = path.join(CONFIG_DIR, 'config.json')

export function getConfig(): Config {
  try {
    if (fs.existsSync(CONFIG_FILE)) {
      const userConfig = fs.readJsonSync(CONFIG_FILE)
      return { ...DEFAULT_CONFIG, ...userConfig }
    }
  } catch (error) {
    // Ignore errors and use default config
  }

  return DEFAULT_CONFIG
}

export function saveConfig(config: Partial<Config>): void {
  const currentConfig = getConfig()
  const newConfig = { ...currentConfig, ...config }

  fs.ensureDirSync(CONFIG_DIR)
  fs.writeJsonSync(CONFIG_FILE, newConfig, { spaces: 2 })
}

export function getConfigPath(): string {
  return CONFIG_FILE
}
