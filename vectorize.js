const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

// ==============================================================================
// PARSING ARGUMENTS
// ==============================================================================
function parseArgs() {
    const args = process.argv.slice(2);
    let inputFolder = '';
    let outputFolder = '';
    let checkFolder = '';

    for (let i = 0; i < args.length; i++) {
        if (args[i] === '--input' || args[i] === '-i') {
            inputFolder = args[i + 1] || '';
            i++;
        } else if (args[i] === '--output' || args[i] === '-o') {
            outputFolder = args[i + 1] || '';
            i++;
        } else if (args[i] === '--check' || args[i] === '-c') {
            checkFolder = args[i + 1] || '';
            i++;
        }
    }
    return { inputFolder, outputFolder, checkFolder };
}

const parsed = parseArgs();
const INPUT_FOLDER = parsed.inputFolder || 'D:/MicroStock/ADOBESTOCK/STOK READY UP/natal series/KLOTER1/PNG';
const OUTPUT_FOLDER = parsed.outputFolder || INPUT_FOLDER;
const CHECK_FOLDER = parsed.checkFolder || '';

const USER_DATA_DIR = path.join(__dirname, 'puppeteer_chrome_profile');
const SUPPORTED_EXTENSIONS = ['.jpg', '.jpeg', '.png'];

const delay = ms => new Promise(r => setTimeout(r, ms));
function rnd(min = 1500, max = 3000) {
    return Math.floor(Math.random() * (max - min + 1) + min);
}

// ==============================================================================
// HELPER: Menutup modal / dialog / cookie banner jika muncul
// ==============================================================================
async function dismissAnyModal(page) {
    try {
        await page.evaluate(() => {
            const modalSelectors = [
                'button[aria-label="Close"]',
                '.modal-close',
                '.close-btn',
                '[data-dismiss="modal"]'
            ];
            for (const sel of modalSelectors) {
                const btn = document.querySelector(sel);
                if (btn && btn.getBoundingClientRect().width > 0) {
                    btn.click();
                    return;
                }
            }
            const btns = Array.from(document.querySelectorAll('button, a'));
            for (const b of btns) {
                const t = (b.innerText || b.textContent || '').trim().toLowerCase();
                if (['accept all', 'accept cookies', 'got it', 'i agree', 'dismiss', 'close', 'ok'].includes(t)) {
                    if (b.getBoundingClientRect().width > 0) {
                        b.click();
                        return;
                    }
                }
            }
        });
    } catch (e) {}
}

// ==============================================================================
// HELPER: Klik elemen berdasarkan teks exact match (dalam area tertentu) dengan retry
// ==============================================================================
async function clickText(page, text, options = {}) {
    const { contains = false, retries = 3 } = options;
    for (let r = 0; r < retries; r++) {
        try {
            const clicked = await page.evaluate((searchText, useContains) => {
                const els = Array.from(document.querySelectorAll(
                    'button, a, div, span, label, input[type="radio"], [role="button"], [role="radio"], [role="tab"], [role="option"]'
                ));
                const target = els.find(e => {
                    if (e.offsetParent === null && !e.closest('[class*="panel"], [class*="settings"], [class*="download"]')) return false;
                    const t = (e.innerText || e.textContent || '').trim();
                    const rect = e.getBoundingClientRect();
                    const isVisible = rect.width > 0 && rect.height > 0;
                    if (!isVisible) return false;
                    if (useContains) return t.toLowerCase().includes(searchText.toLowerCase());
                    return t === searchText || t.toLowerCase() === searchText.toLowerCase();
                });
                if (target) {
                    target.scrollIntoView({ behavior: 'auto', block: 'center' });
                    target.click();
                    return true;
                }
                return false;
            }, text, contains);
            if (clicked) {
                console.log(`     [OK] "${text}"`);
                return true;
            }
        } catch (e) {}
        if (r < retries - 1) await delay(300);
    }
    console.log(`     [--] "${text}" tidak ditemukan`);
    return false;
}

// ==============================================================================
// HELPER: Set toggle ON/OFF berdasarkan label
// ==============================================================================
async function setToggle(page, labelText, wantOn) {
    try {
        const result = await page.evaluate((label, wantOn) => {
            const allElements = Array.from(document.querySelectorAll('label, span, div, p, button'));
            const matchingLabel = allElements.find(e => {
                const t = (e.innerText || e.textContent || '').trim();
                const isVis = e.getBoundingClientRect().width > 0;
                return isVis && t.toLowerCase() === label.toLowerCase();
            }) || allElements.find(e => {
                const t = (e.innerText || e.textContent || '').trim();
                const isVis = e.getBoundingClientRect().width > 0;
                return isVis && t.toLowerCase().includes(label.toLowerCase());
            });

            if (!matchingLabel) return 'LABEL_NOT_FOUND';

            let container = matchingLabel;
            for (let i = 0; i < 5; i++) {
                if (container.parentElement && container.parentElement.children.length <= 10) {
                    container = container.parentElement;
                } else break;
            }

            const sw = container.querySelector(
                'button[role="switch"], input[type="checkbox"], [role="switch"], [class*="switch"], [class*="toggle"]'
            ) || container.querySelector('button, input');

            if (!sw) return 'SWITCH_NOT_FOUND';

            let isOn = false;
            if (sw.tagName === 'INPUT') {
                isOn = sw.checked;
            } else if (sw.hasAttribute('aria-checked')) {
                isOn = sw.getAttribute('aria-checked') === 'true';
            } else if (sw.hasAttribute('data-state')) {
                isOn = sw.getAttribute('data-state') === 'checked' || sw.getAttribute('data-state') === 'on';
            } else {
                const cls = (sw.className || '');
                isOn = cls.includes('checked') || cls.includes('active') || cls.includes('on');
            }

            if (isOn !== wantOn) {
                sw.scrollIntoView({ behavior: 'auto', block: 'center' });
                sw.click();
                if (sw.tagName === 'INPUT') {
                    sw.dispatchEvent(new Event('change', { bubbles: true }));
                }
                return 'TOGGLED -> ' + (wantOn ? 'ON' : 'OFF');
            }
            return 'ALREADY ' + (wantOn ? 'ON' : 'OFF');
        }, labelText, wantOn);

        console.log(`     [Toggle] ${labelText}: ${result}`);
    } catch (e) {
        console.log(`     [Toggle ERR] ${labelText}: ${e.message.substring(0, 50)}`);
    }
}

// ==============================================================================
// FUNGSI UTAMA: Terapkan semua pengaturan di halaman download (sesuai SS)
// ==============================================================================
async function applyAllSettings(page) {
    console.log('  -> [4/6] Menerapkan pengaturan...');
    await delay(1200);

    // 1. Pilih format SVG
    await page.evaluate(() => {
        const els = Array.from(document.querySelectorAll('*'));
        const formatSection = els.find(e => (e.innerText || '').trim().startsWith('File format'));
        if (!formatSection) return;
        const svgEl = Array.from(formatSection.querySelectorAll('*')).find(e => {
            const t = (e.innerText || e.textContent || '').trim();
            return t === 'SVG';
        });
        if (svgEl) svgEl.click();
    });
    await delay(600);
    console.log('     [OK] SVG format dipilih');

    // 2. Optimize for: Custom
    await clickText(page, 'Custom');
    await delay(400);

    // 3. SVG Version: Adobe*
    await clickText(page, 'Adobe*');
    await delay(400);

    // 4. Toggle Fixed size ON
    await setToggle(page, 'Fixed size', true);
    await delay(400);

    // 5. Buka Advanced section HANYA jika belum terbuka
    const isAdvAlreadyOpen = await page.evaluate(() => {
        const els = Array.from(document.querySelectorAll('*'));
        return els.some(e => {
            const t = (e.innerText || e.textContent || '').trim();
            const rect = e.getBoundingClientRect();
            return (t === 'Filled shapes' || t === 'Cut-outs' || t === 'Line fit' || t === 'Simple shapes')
                && rect.width > 0 && rect.height > 0;
        });
    });

    if (!isAdvAlreadyOpen) {
        console.log('     [>>] Membuka Advanced section...');
        await page.evaluate(() => {
            const els = Array.from(document.querySelectorAll('*'));
            const adv = els.find(e => {
                const t = (e.innerText || e.textContent || '').trim();
                const rect = e.getBoundingClientRect();
                return (t === '▶ Advanced' || t.includes('▶') && t.includes('Advanced'))
                    && rect.width > 0 && rect.height > 0;
            }) || els.find(e => {
                const t = (e.innerText || e.textContent || '').trim();
                const rect = e.getBoundingClientRect();
                return t.toLowerCase() === 'advanced' && rect.width > 0;
            });
            if (adv) {
                adv.scrollIntoView({ behavior: 'auto', block: 'center' });
                adv.click();
            }
        });
        await delay(1200);
    } else {
        console.log('     [>>] Advanced section sudah terbuka.');
    }

    // 6. Size: Unchanged
    await clickText(page, 'Unchanged');
    await delay(300);

    // 7. Draw: Filled shapes
    await clickText(page, 'Filled shapes');
    await delay(300);

    // 8. Stack: Cut-outs
    await clickText(page, 'Cut-outs');
    await delay(300);

    // 9. Group by: Color (sesuai SS user!)
    await clickText(page, 'Color');
    await delay(300);

    // 10. Line fit: Medium
    await clickText(page, 'Medium');
    await delay(300);

    // 11. Toggles di Advanced (sesuai SS user)
    await setToggle(page, 'Simple shapes', true); await delay(250);
    await setToggle(page, 'Lines', true); await delay(250);
    await setToggle(page, 'Cubic Bezier', true); await delay(250);
    await setToggle(page, 'Quadratic Bezier', false); await delay(250);
    await setToggle(page, 'Circular', false); await delay(250);
    await setToggle(page, 'Elliptical', false); await delay(250);

    // 12. KHUSUS: Pastikan Fill Gaps / Gap Filler OFF (mati)
    console.log('     [>>] Mematikan Fill gaps...');
    await setToggle(page, 'Fill gaps', false); await delay(250);

    // Cek tambahan langsung ke DOM untuk memastikan switch Fill gaps mati
    await page.evaluate(() => {
        const labels = Array.from(document.querySelectorAll('label, span, div, p'));
        const fgLabel = labels.find(e => (e.innerText || e.textContent || '').trim() === 'Fill gaps');
        if (fgLabel) {
            let p = fgLabel.parentElement;
            for (let i = 0; i < 4; i++) {
                if (!p) break;
                const sw = p.querySelector('button[role="switch"], input[type="checkbox"], [role="switch"]');
                if (sw) {
                    const isChecked = sw.tagName === 'INPUT' ? sw.checked : (sw.getAttribute('aria-checked') === 'true');
                    if (isChecked) {
                        sw.click();
                    }
                    break;
                }
                p = p.parentElement;
            }
        }
    });
    await delay(300);

    console.log('  -> [4/6] Pengaturan selesai!');
}

// ==============================================================================
// HELPER: Bersihkan lock file dan proses orphan Chrome
// ==============================================================================
function cleanupChromeProfile(profileDir) {
    if (process.platform === 'win32') {
        try {
            const { execSync } = require('child_process');
            const psScript = "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'chrome.exe' -and ($_.CommandLine -like '*puppeteer_chrome_profile*' -or $_.CommandLine -like '*win64-154.0.8037.57*') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }";
            const encoded = Buffer.from(psScript, 'utf16le').toString('base64');
            execSync(`powershell -NoProfile -EncodedCommand ${encoded}`, { stdio: 'ignore' });
        } catch (e) {}
    }

    if (fs.existsSync(profileDir)) {
        const lockNames = ['lockfile', 'SingletonLock', 'SingletonCookie', 'SingletonSocket', 'DevToolsActivePort'];
        for (const name of lockNames) {
            const p = path.join(profileDir, name);
            if (fs.existsSync(p)) {
                try {
                    fs.unlinkSync(p);
                } catch (e) {}
            }
        }
        const defaultLock = path.join(profileDir, 'Default', 'Profile.lock');
        if (fs.existsSync(defaultLock)) {
            try { fs.unlinkSync(defaultLock); } catch (e) {}
        }
        const defaultLock2 = path.join(profileDir, 'Default', 'LOCK');
        if (fs.existsSync(defaultLock2)) {
            try { fs.unlinkSync(defaultLock2); } catch (e) {}
        }
    }
}

// ==============================================================================
// HELPER: Launch Browser Chrome
// ==============================================================================
async function launchBrowser() {
    cleanupChromeProfile(USER_DATA_DIR);
    await delay(500);

    let browser;
    try {
        browser = await puppeteer.launch({
            headless: false,
            userDataDir: USER_DATA_DIR,
            defaultViewport: null,
            args: ['--start-maximized', '--no-sandbox', '--disable-setuid-sandbox']
        });
    } catch (launchErr) {
        if (launchErr.message.includes('already running') || launchErr.message.includes('userDataDir')) {
            console.log('[WARN] Terdeteksi sisa lock pada profile Chrome. Membersihkan & mencoba ulang...');
            cleanupChromeProfile(USER_DATA_DIR);
            await delay(1000);
            browser = await puppeteer.launch({
                headless: false,
                userDataDir: USER_DATA_DIR,
                defaultViewport: null,
                args: ['--start-maximized', '--no-sandbox', '--disable-setuid-sandbox']
            });
        } else {
            throw launchErr;
        }
    }
    return browser;
}

function attachPageHandlers(page) {
    page.on('dialog', async dialog => {
        try {
            console.log(`     [DIALOG] Browser dialog (${dialog.type()}): "${dialog.message()}". Menerima otomatis...`);
            await dialog.accept();
        } catch (e) {}
    });
}

// ==============================================================================
// LOOP UTAMA
// ==============================================================================
async function vectorizeFolder() {
    const inputPath = path.resolve(INPUT_FOLDER);
    const outputPath = path.resolve(OUTPUT_FOLDER);
    const checkPath = CHECK_FOLDER ? path.resolve(CHECK_FOLDER) : outputPath;

    if (!fs.existsSync(inputPath)) {
        console.error(`[ERROR] Folder input tidak ditemukan: ${inputPath}`);
        process.exit(1);
    }

    if (!fs.existsSync(outputPath)) {
        fs.mkdirSync(outputPath, { recursive: true });
    }

    const allFiles = fs.readdirSync(inputPath).filter(f =>
        SUPPORTED_EXTENSIONS.includes(path.extname(f).toLowerCase())
    );

    if (allFiles.length === 0) {
        console.log('Tidak ada file gambar (.jpg, .jpeg, .png) di folder input.');
        process.exit(0);
    }

    // --------------------------------------------------------------------------
    // LOGIKA CEK FILE: Ambil semua nama file di folder output/cek (tanpa ekstensi)
    // --------------------------------------------------------------------------
    const checkedBaseNames = new Set();
    if (checkPath && fs.existsSync(checkPath)) {
        const checkFiles = fs.readdirSync(checkPath);
        for (const cf of checkFiles) {
            const base = path.parse(cf).name.trim().toLowerCase();
            if (base) {
                checkedBaseNames.add(base);
            }
        }
        console.log(`[CHECK] Memeriksa folder output: ${checkPath} (${checkedBaseNames.size} file sudah ada)`);
    }

    // Filter file: Skip file jika nama dasarnya sudah ada di folder output/cek
    const files = [];
    let skippedCount = 0;

    for (const f of allFiles) {
        const base = path.parse(f).name.trim().toLowerCase();
        if (checkedBaseNames.has(base)) {
            console.log(`  -> [SKIP] ${f} (sudah ada di folder output sebagai "${base}.*")`);
            skippedCount++;
        } else {
            files.push(f);
        }
    }

    if (skippedCount > 0) {
        console.log(`\n[INFO] Total file di-skip: ${skippedCount} file (sudah pernah diproses / ada di output).`);
    }

    if (files.length === 0) {
        console.log(`\n==================================================`);
        console.log(` Semua file gambar (${allFiles.length}) sudah ada di folder output.`);
        console.log(` Tidak ada file baru yang perlu divektorisasi. Selesai! 🎉`);
        console.log(`==================================================\n`);
        process.exit(0);
    }

    console.log(`\n==================================================`);
    console.log(` Total File Input : ${allFiles.length} file gambar`);
    console.log(` File Di-skip     : ${skippedCount} file (sudah ada di output)`);
    console.log(` File Diproses    : ${files.length} file`);
    console.log(` Input Folder     : ${inputPath}`);
    console.log(` Output Folder    : ${outputPath}`);
    console.log(`==================================================\n`);

    let browser = await launchBrowser();
    const pages = await browser.pages();
    let page = pages.length > 0 ? pages[0] : await browser.newPage();
    attachPageHandlers(page);

    let client = await page.createCDPSession();
    await client.send('Page.setDownloadBehavior', {
        behavior: 'allow',
        downloadPath: outputPath,
    });

    const MAX_RETRIES = 3;

    for (let i = 0; i < files.length; i++) {
        const filename = files[i];
        const filePath = path.join(inputPath, filename);
        const baseName = path.basename(filename, path.extname(filename));
        const expectedSvg = baseName + '.svg';

        let fileSucceeded = false;

        for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
            const attemptInfo = attempt > 1 ? ` (Percobaan ${attempt}/${MAX_RETRIES})` : '';
            console.log(`\n[${i + 1}/${files.length}] ===== ${filename}${attemptInfo} =====`);

            try {
                // Pastikan browser & page masih terhubung
                if (!browser || !browser.connected) {
                    console.log('  -> Browser terputus. Membuka browser baru...');
                    browser = await launchBrowser();
                    const curPages = await browser.pages();
                    page = curPages.length > 0 ? curPages[0] : await browser.newPage();
                    attachPageHandlers(page);
                    client = await page.createCDPSession();
                }

                if (page.isClosed()) {
                    page = await browser.newPage();
                    attachPageHandlers(page);
                    client = await page.createCDPSession();
                }

                // Setup CDP download memastikan download ke outputPath
                await client.send('Page.setDownloadBehavior', {
                    behavior: 'allow',
                    downloadPath: outputPath,
                }).catch(() => {});

                // STEP 1: Buka vectorizer.ai
                console.log('  -> [1/6] Buka vectorizer.ai...');
                try {
                    await page.goto('https://vectorizer.ai/', { waitUntil: 'domcontentloaded', timeout: 45000 });
                } catch (e) {
                    console.log('     goto warn (lanjut):', e.message.substring(0, 50));
                }
                await delay(rnd(1500, 2500));
                await dismissAnyModal(page);

                // STEP 2: Upload gambar
                console.log(`  -> [2/6] Upload: ${filename}`);
                const fileInput = await page.waitForSelector('input[type="file"]', { timeout: 30000 });
                if (!fileInput) throw new Error('Input file tidak ditemukan!');
                await fileInput.uploadFile(filePath);
                console.log('  -> [2/6] File diupload. Menunggu vektorisasi...');
                await fileInput.dispose();

                // STEP 3: Tunggu proses vektorisasi selesai (sampai URL menuju /edit)
                await page.waitForFunction(() => {
                    const url = window.location.href;
                    const text = document.body ? document.body.innerText : '';
                    if (text.includes('Error processing') || text.includes('Server error') || text.includes('Could not process') || text.includes('Failed to process')) {
                        throw new Error('Pesan error muncul di halaman Vectorizer');
                    }
                    return url.includes('/images/') &&
                        (url.endsWith('/edit') || url.includes('/edit?') || url.includes('/edit#')) &&
                        !url.includes('/images/processing');
                }, { timeout: 300000 });

                const editUrl = page.url();
                const downloadPageUrl = editUrl.split('?')[0].split('#')[0].replace(/\/edit\/?$/, '');
                console.log(`  -> [3/6] Vektorisasi selesai!`);
                console.log(`     Edit URL: ${editUrl.substring(0, 80)}...`);
                await delay(rnd(1500, 2500));

                // STEP 4: Navigate ke halaman settings/download
                console.log(`  -> [3/6] Membuka halaman pengaturan download...`);
                await page.goto(downloadPageUrl, { waitUntil: 'domcontentloaded', timeout: 60000 });
                await delay(rnd(2000, 3000));

                await page.waitForFunction(() => {
                    const body = document.body ? document.body.innerText : '';
                    return body.includes('File format') || body.includes('Optimize for');
                }, { timeout: 45000 });
                console.log('  -> [3/6] Halaman settings siap!');
                await delay(rnd(1500, 2500));

                // STEP 5: Terapkan pengaturan
                await applyAllSettings(page);
                await delay(rnd(1200, 2000));

                // STEP 6: Klik tombol Download FINAL
                console.log('  -> [5/6] Klik tombol Download final...');
                await page.evaluate(() => {
                    window.scrollTo({ top: document.body.scrollHeight, behavior: 'auto' });
                });
                await delay(800);

                // Setup CDP download kembali memastikan path download benar
                await client.send('Page.setDownloadBehavior', {
                    behavior: 'allow',
                    downloadPath: outputPath,
                }).catch(() => {});

                let downloaded = false;
                for (let clickAttempt = 0; clickAttempt < 5; clickAttempt++) {
                    downloaded = await page.evaluate(() => {
                        const els = Array.from(document.querySelectorAll('button, a, [role="button"]'));
                        const dlBtns = els.filter(el => {
                            const t = (el.innerText || el.textContent || '').trim().toUpperCase();
                            const rect = el.getBoundingClientRect();
                            return (t === 'DOWNLOAD' || t.startsWith('DOWNLOAD') || (t.includes('DOWNLOAD') && !t.includes('DESKTOP')))
                                && rect.width > 0 && rect.height > 0;
                        });
                        if (dlBtns.length === 0) return false;
                        const last = dlBtns[dlBtns.length - 1];
                        last.scrollIntoView({ behavior: 'auto', block: 'center' });
                        last.click();
                        return true;
                    });
                    if (downloaded) break;
                    await delay(800);
                }

                if (downloaded) console.log('  -> [5/6] Download diklik!');
                else throw new Error('Tombol Download tidak ditemukan.');

                // STEP 7: Verifikasi file di folder output
                console.log('  -> [6/6] Menunggu file SVG tersimpan...');
                let fileFound = false;
                for (let a = 0; a < 35; a++) {
                    await delay(2000);
                    const curFiles = fs.readdirSync(outputPath);
                    const found = curFiles.some(f => {
                        const low = f.toLowerCase();
                        return (
                            low === expectedSvg.toLowerCase() ||
                            low === `${baseName} (1).svg`.toLowerCase() ||
                            low === `${baseName} (2).svg`.toLowerCase() ||
                            (low.startsWith(baseName.toLowerCase()) && low.endsWith('.svg') && !low.endsWith('.crdownload'))
                        );
                    });
                    if (found) { fileFound = true; break; }
                    if (curFiles.some(f => f.endsWith('.crdownload'))) {
                        console.log(`     Mendownload... (${a + 1}/35)`);
                    }
                }

                if (fileFound) {
                    console.log(`  -> SUCCESS! ${expectedSvg} tersimpan. ✅`);
                    fileSucceeded = true;
                    await delay(rnd(1500, 2500));
                    break; // Berhasil! Keluar dari loop retry
                } else {
                    throw new Error('File SVG tidak terdeteksi di output setelah timeout download.');
                }

            } catch (error) {
                console.error(`  -> [ERROR] Percobaan ${attempt}/${MAX_RETRIES}: ${error.message}`);
                if (attempt < MAX_RETRIES) {
                    console.log(`  -> 🔄 Mengulang otomatis file ini (${attempt + 1}/${MAX_RETRIES}) dalam 3 detik...`);
                    try {
                        if (page && !page.isClosed()) {
                            await page.goto('https://vectorizer.ai/', { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {});
                        }
                    } catch (navErr) {}
                    await delay(3000);
                } else {
                    console.error(`  -> ❌ Gagal setelah ${MAX_RETRIES} percobaan. Lanjut ke file berikutnya.`);
                    await delay(rnd(2000, 3500));
                }
            }
        }
    }

    console.log('\n==================================================');
    console.log(' BATCH SELESAI!');
    console.log('==================================================');
    try {
        await browser.close();
    } catch (e) {}
}

vectorizeFolder();
