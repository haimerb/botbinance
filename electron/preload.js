const { contextBridge } = require('electron')

const backendUrlArg = process.argv.find(a => a.startsWith('--backend-url='))
const backendUrl = backendUrlArg ? backendUrlArg.slice('--backend-url='.length) : null

contextBridge.exposeInMainWorld('electronAPI', {
  platform: process.platform,
  isElectron: true,
  backendUrl,
})
