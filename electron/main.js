const { app, BrowserWindow, Menu } = require('electron')
const path = require('path')
const { spawn } = require('child_process')

let mainWindow
let backendProcess

const isDev = process.env.NODE_ENV === 'development'
const BACKEND_PORT = 8000
const FRONTEND_PORT = 5173

function startBackend() {
  const python = process.platform === 'win32' ? 'python' : 'python3'
  backendProcess = spawn(python, [
    '-m', 'uvicorn', 'backend.main:app',
    '--host', '0.0.0.0', '--port', String(BACKEND_PORT),
  ], {
    cwd: path.join(__dirname, '..'),
    stdio: 'pipe',
  })
  backendProcess.stdout.on('data', (data) => {
    console.log(`[backend] ${data}`)
  })
  backendProcess.stderr.on('data', (data) => {
    console.error(`[backend] ${data}`)
  })
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
  startBackend()
  setTimeout(createWindow, 2000)
})

app.on('window-all-closed', () => {
  if (backendProcess) {
    backendProcess.kill()
  }
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('activate', () => {
  if (mainWindow === null) {
    createWindow()
  }
})

app.on('before-quit', () => {
  if (backendProcess) {
    backendProcess.kill()
  }
})
