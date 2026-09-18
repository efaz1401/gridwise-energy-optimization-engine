import puppeteer from 'puppeteer-core'
import path from 'path'

const EDGE_PATH = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const OUT_DIR = 'C:\\Users\\MSI\\.gemini\\antigravity\\brain\\157bb21b-8415-4417-91a6-4461658f20a8'

async function run() {
  console.log('Launching Edge with puppeteer-core...')
  const browser = await puppeteer.launch({
    executablePath: EDGE_PATH,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu']
  })

  const page = await browser.newPage()
  
  const errors = []
  page.on('console', msg => {
    if (msg.type() === 'error') {
      errors.push(msg.text())
    }
  })
  page.on('pageerror', err => {
    errors.push(err.toString())
  })

  // 1. Desktop View
  console.log('Navigating to http://127.0.0.1:8000/ (Desktop 1280x960)...')
  await page.setViewport({ width: 1280, height: 960, deviceScaleFactor: 1 })
  await page.goto('http://127.0.0.1:8000/', { waitUntil: 'networkidle0', timeout: 15000 })
  await new Promise(r => setTimeout(r, 1000))

  const desktopShot = path.join(OUT_DIR, 'desktop_view.png')
  await page.screenshot({ path: desktopShot, fullPage: true })
  console.log('Saved desktop screenshot to:', desktopShot)

  // Test interactive scenario click
  console.log('Testing click on C2 preset...')
  const buttons = await page.$$('button')
  for (const b of buttons) {
    const text = await (await b.getProperty('textContent')).jsonValue()
    if (text.includes('C2:')) {
      await b.click()
      break
    }
  }
  await new Promise(r => setTimeout(r, 1200))
  const c2Shot = path.join(OUT_DIR, 'c2_scenario_view.png')
  await page.screenshot({ path: c2Shot, fullPage: false })
  console.log('Saved C2 scenario screenshot to:', c2Shot)

  // 2. Mobile View
  console.log('Testing Mobile View (390x844)...')
  await page.setViewport({ width: 390, height: 844, deviceScaleFactor: 2, isMobile: true })
  await page.goto('http://127.0.0.1:8000/', { waitUntil: 'networkidle0', timeout: 15000 })
  await new Promise(r => setTimeout(r, 1000))

  const mobileShot = path.join(OUT_DIR, 'mobile_view.png')
  await page.screenshot({ path: mobileShot, fullPage: true })
  console.log('Saved mobile screenshot to:', mobileShot)

  await browser.close()

  console.log('--- BROWSER VERIFICATION SUMMARY ---')
  console.log('Console Errors count:', errors.length)
  if (errors.length > 0) {
    console.log('Errors:', errors)
  } else {
    console.log('Clean page load: 0 console errors.')
  }
}

run().catch(err => {
  console.error('Fatal browser test error:', err)
  process.exit(1)
})
