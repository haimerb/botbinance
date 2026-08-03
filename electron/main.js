const { app, BrowserWindow, Menu } = require('electron')
const path = require('path')
const fs = require('fs')

let mainWindow

const isDev = process.env.NODE_ENV === 'development'
const FRONTEND_PORT = 5173

function getBackendUrl() {
  if (process.env.BACKEND_URL) {
    return process.env.BACKEND_URL.replace(/\/+$/, '')
  }
  const configPath = path.join(app.getPath('userData'), 'config.json')
  try {
    const cfg = JSON.parse(fs.readFileSync(configPath, 'utf-8'))
    if (cfg.backendUrl) return String(cfg.backendUrl).replace(/\/+$/, '')
  } catch {}
  return 'http://localhost:8000'
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 900,
    minHeight: 600,
    backgroundColor: '#080b14',
    titleBarStyle: 'hiddenInset',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      additionalArguments: [`--backend-url=${getBackendUrl()}`],
    },
  })

  const url = isDev
    ? `http://localhost:${FRONTEND_PORT}`
    : `file://${path.join(__dirname, '..', 'frontend', 'dist', 'index.html')}`

  mainWindow.loadURL(url)

  if (isDev) {
    mainWindow.webContents.openDevTools({ mode: 'detach' })
  }

  const menuTemplate = [
    {
      label: 'Binance Bot',
      submenu: [
        { role: 'quit' }
      ]
    },
    {
      label: 'View',
      submenu: [
        { role: 'reload' },
        { role: 'toggleDevTools' },
        { type: 'separator' },
        { role: 'togglefullscreen' },
      ]
    }
  ]
  Menu.setApplicationMenu(Menu.buildFromTemplate(menuTemplate))

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

app.whenReady().then(() => {
  createWindow()
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('activate', () => {
  if (mainWindow === null) {
    createWindow()
  }
})
