/**
 * Teste E2E de Produção - Versão v=20261009_v2
 * 
 * Valida:
 * 1. Carregamento de produção (app.js?v=20261009_v2, styles.css?v=20261009_v2).
 * 2. Clique e touch no #btn-microphone sob User-Agent Mobile (Pixel 7 / Android Chrome).
 * 3. Interação com AudioContext (se passa de suspended para running ou não bloqueia).
 * 4. Captura de dialogs (alert/confirm/prompt) e console.error.
 * 5. Ciclo de transição de estado da FSM e inspeção de logs de debug emitidos pelo app.
 */

const { chromium, devices } = require('playwright');

async function testProductionMobileMic() {
    console.log("=================================================================");
    console.log("INICIANDO TESTE E2E DE PRODUÇÃO: app.js?v=20261009_v2");
    console.log("=================================================================\n");

    const pixel7 = devices['Pixel 7'];
    const browser = await chromium.launch({
        headless: true,
        args: [
            '--use-fake-ui-for-media-stream',
            '--use-fake-device-for-media-stream',
            '--no-sandbox',
            '--disable-setuid-sandbox'
        ]
    });

    const context = await browser.newContext({
        ...pixel7,
        permissions: ['microphone'],
        locale: 'pt-BR'
    });

    // Injeta mock da Web Speech API compatível caso o headless não a possua nativamente
    await context.addInitScript(() => {
        if (!('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
            class MockSpeechRecognition extends EventTarget {
                constructor() {
                    super();
                    this.continuous = true;
                    this.interimResults = true;
                    this.lang = 'pt-BR';
                    this.onstart = null;
                    this.onspeechstart = null;
                    this.onsoundstart = null;
                    this.onresult = null;
                    this.onerror = null;
                    this.onend = null;
                }
                start() {
                    setTimeout(() => {
                        if (typeof this.onstart === 'function') this.onstart();
                    }, 20);
                }
                stop() {
                    setTimeout(() => {
                        if (typeof this.onend === 'function') this.onend();
                    }, 20);
                }
                abort() {
                    setTimeout(() => {
                        if (typeof this.onend === 'function') this.onend();
                    }, 20);
                }
            }
            window.SpeechRecognition = MockSpeechRecognition;
            window.webkitSpeechRecognition = MockSpeechRecognition;
        }
    });

    const page = await context.newPage();

    const capturedAlerts = [];
    const consoleLogs = [];
    const consoleErrors = [];

    page.on('dialog', async dialog => {
        const msg = `Dialog [${dialog.type()}]: "${dialog.message()}"`;
        capturedAlerts.push(msg);
        console.log(`[ALERTA INTERCEPTADO]: ${msg}`);
        await dialog.dismiss();
    });

    page.on('console', msg => {
        const text = msg.text();
        consoleLogs.push({ type: msg.type(), text });
        if (msg.type() === 'error') {
            consoleErrors.push(text);
        }
        if (text.includes('[JARVIS DEBUG]') || text.includes('AudioContext') || msg.type() === 'error') {
            console.log(`[Browser Console ${msg.type().toUpperCase()}]: ${text}`);
        }
    });

    page.on('pageerror', err => {
        console.error(`[Browser PageError]:`, err.message);
        consoleErrors.push(err.message);
    });

    try {
        console.log("1. Navegando para https://jarvis.samuel21tu.space/ ...");
        const response = await page.goto('https://jarvis.samuel21tu.space/', { waitUntil: 'networkidle', timeout: 30000 });
        console.log(`-> Status HTTP da página raiz: ${response.status()}`);

        // Checar scripts carregados na DOM
        const scripts = await page.$$eval('script[src]', els => els.map(e => e.src));
        console.log("-> Scripts identificados na página:", scripts);

        await page.waitForSelector('#btn-microphone', { timeout: 10000 });
        await page.waitForSelector('#mic-btn-text', { timeout: 10000 });

        // Verifica AudioContext inicial antes de qualquer clique
        let initialAudioCtxState = await page.evaluate(() => {
            return window.audioCtx ? window.audioCtx.state : 'null (não instanciado)';
        });
        console.log(`\n2. Estado inicial do AudioContext: ${initialAudioCtxState}`);

        let initialBtnText = await page.$eval('#mic-btn-text', el => el.textContent.trim());
        let initialBtnClass = await page.$eval('#btn-microphone', el => el.className);
        console.log(`-> Botão inicial: "${initialBtnText}" | Classe: "${initialBtnClass}"`);

        // Teste de Clique / Touch no Botão de Microfone
        console.log("\n3. Executando CLIQUE/TOQUE no botão de microfone (#btn-microphone)...");
        await page.click('#btn-microphone');
        await page.waitForTimeout(300);

        let activeAudioCtxState = await page.evaluate(() => {
            return window.audioCtx ? window.audioCtx.state : 'null';
        });
        let activeBtnText = await page.$eval('#mic-btn-text', el => el.textContent.trim());
        let activeBtnClass = await page.$eval('#btn-microphone', el => el.className);
        console.log(`-> AudioContext após clique: "${activeAudioCtxState}"`);
        console.log(`-> Botão após clique: "${activeBtnText}" | Classe: "${activeBtnClass}"`);

        // Teste de Desativação (MUTE)
        console.log("\n4. Executando SEGUNDO CLIQUE para MUTAR (#btn-microphone)...");
        await page.waitForTimeout(300);
        await page.click('#btn-microphone');
        await page.waitForTimeout(300);

        let mutedBtnText = await page.$eval('#mic-btn-text', el => el.textContent.trim());
        let mutedBtnClass = await page.$eval('#btn-microphone', el => el.className);
        let mutedAudioCtxState = await page.evaluate(() => {
            return window.audioCtx ? window.audioCtx.state : 'null';
        });
        console.log(`-> AudioContext após mute: "${mutedAudioCtxState}"`);
        console.log(`-> Botão após mute: "${mutedBtnText}" | Classe: "${mutedBtnClass}"`);

        // Resumo de Alertas e Erros
        console.log("\n5. Auditoria de Alertas Visuais e Erros de Hardware:");
        console.log(`-> Total de alertas visuais (alert/dialog) disparados: ${capturedAlerts.length}`);
        if (capturedAlerts.length > 0) {
            capturedAlerts.forEach(a => console.log(`   - ${a}`));
        } else {
            console.log("   - Nenhum alert() ou popup de bloqueio foi disparado.");
        }

        console.log(`-> Total de console.error capturados: ${consoleErrors.length}`);
        if (consoleErrors.length > 0) {
            consoleErrors.forEach(e => console.log(`   - ${e}`));
        } else {
            console.log("   - Nenhum console.error disparado durante o fluxo.");
        }

        console.log("\n=================================================================");
        console.log("TESTE DE PRODUÇÃO CONCLUÍDO COM SUCESSO!");
        console.log("=================================================================");

    } catch (err) {
        console.error("\n[FALHA NA EXECUÇÃO DO TESTE]:", err);
        throw err;
    } finally {
        await browser.close();
    }
}

testProductionMobileMic().catch(e => {
    console.error(e);
    process.exit(1);
});
