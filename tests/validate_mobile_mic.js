/**
 * Validação E2E Playwright - Botão de Microfone & FSM Mobile do Jarvis
 * 
 * Simula ambiente Mobile (Pixel 7 / Android Chrome) com:
 * 1. Concessão de permissões de microfone
 * 2. Injeção de Mock da Web Speech API antes do carregamento dos scripts da página
 * 3. Validação do Estado Inicial (MUTED)
 * 4. Toque de ativação (transição para ACTIVE)
 * 5. Prevenção de ghost clicks / duplo toque acidental (mantém ACTIVE)
 * 6. Toque de silenciamento (transição limpa para MUTED sem bloqueio)
 * 7. Reativação após mute (sem travar em MUTED)
 */

const { chromium, devices } = require('playwright');

async function runMobileMicValidation() {
    console.log("=== INICIANDO VALIDAÇÃO DO BOTÃO DE MICROFONE NO MOBILE ===");

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
        locale: 'pt-BR',
        userAgent: 'Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'
    });

    // Injeta mock da Web Speech API ANTES de carregar qualquer script da página
    await context.addInitScript(() => {
        window.mockSpeechInstances = [];
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
                window.mockSpeechInstances.push(this);
            }
            start() {
                setTimeout(() => {
                    if (typeof this.onstart === 'function') this.onstart();
                }, 30);
            }
            stop() {
                setTimeout(() => {
                    if (typeof this.onend === 'function') this.onend();
                }, 30);
            }
            abort() {
                setTimeout(() => {
                    if (typeof this.onend === 'function') this.onend();
                }, 30);
            }
        }
        window.SpeechRecognition = MockSpeechRecognition;
        window.webkitSpeechRecognition = MockSpeechRecognition;
        console.log("[QA Injection] MockSpeechRecognition injetado com sucesso no contexto mobile.");
    });

    const page = await context.newPage();

    page.on('console', msg => {
        console.log(`[Browser ${msg.type()}]: ${msg.text()}`);
    });

    try {
        console.log("\n1. Carregando interface mobile em https://jarvis.samuel21tu.space/ ...");
        await page.goto('https://jarvis.samuel21tu.space/', { waitUntil: 'domcontentloaded', timeout: 30000 });

        await page.waitForSelector('#btn-microphone', { timeout: 10000 });
        await page.waitForSelector('#mic-btn-text', { timeout: 10000 });
        console.log("-> Página carregada com sucesso.");

        // Teste A: Estado inicial
        console.log("\n2. Validando estado inicial do microfone...");
        let micText = await page.$eval('#mic-btn-text', el => el.textContent.trim());
        let micClass = await page.$eval('#btn-microphone', el => el.className);
        console.log(`-> Texto inicial: "${micText}" | Classe: "${micClass}"`);
        if (!micText.includes("MUTED")) {
            throw new Error(`Estado inicial inválido: esperado conter MUTED, obtido "${micText}"`);
        }

        // Teste B: Toque simples para ATIVAR o microfone
        console.log("\n3. Executando toque simples para ATIVAR...");
        await page.tap('#btn-microphone');
        await page.waitForTimeout(250);

        micText = await page.$eval('#mic-btn-text', el => el.textContent.trim());
        micClass = await page.$eval('#btn-microphone', el => el.className);
        console.log(`-> Após 1º toque: "${micText}" | Classe: "${micClass}"`);
        if (!micClass.includes("active") && !micClass.includes("starting")) {
            throw new Error(`Falha na ativação: classe não reflete active/starting: "${micClass}"`);
        }

        // Teste C: Teste de Ghost Clicks / Duplo Toque Rápido (dentro de 400ms)
        console.log("\n4. Testando prevenção de disparo duplo / ghost clicks (<400ms)...");
        await page.tap('#btn-microphone');
        await page.waitForTimeout(100);
        micText = await page.$eval('#mic-btn-text', el => el.textContent.trim());
        micClass = await page.$eval('#btn-microphone', el => el.className);
        console.log(`-> Após duplo toque imediato (ignorado com sucesso pelo debounce): "${micText}" | Classe: "${micClass}"`);
        if (!micClass.includes("active") && !micClass.includes("starting")) {
            throw new Error(`Double-click/Ghost click inadvertidamente alterou o estado!`);
        }

        // Teste D: Desativação limpa (MUTE) após janela de debounce (>400ms)
        console.log("\n5. Executando toque para DESATIVAR (MUTE)...");
        await page.waitForTimeout(500); // Aguarda término da janela de debounce
        await page.tap('#btn-microphone');
        await page.waitForTimeout(250);

        micText = await page.$eval('#mic-btn-text', el => el.textContent.trim());
        micClass = await page.$eval('#btn-microphone', el => el.className);
        console.log(`-> Após toque de desativação: "${micText}" | Classe: "${micClass}"`);
        if (!micText.includes("MUTED")) {
            throw new Error(`Falha ao silenciar: esperado MUTED, obtido "${micText}"`);
        }

        // Teste E: Reativação subsequente (verifica que não ocorre bloqueio visual permanente)
        console.log("\n6. Executando toque para REATIVAR após mute...");
        await page.waitForTimeout(500);
        await page.tap('#btn-microphone');
        await page.waitForTimeout(250);

        micText = await page.$eval('#mic-btn-text', el => el.textContent.trim());
        micClass = await page.$eval('#btn-microphone', el => el.className);
        console.log(`-> Reativação bem sucedida: "${micText}" | Classe: "${micClass}"`);
        if (!micClass.includes("active") && !micClass.includes("starting")) {
            throw new Error(`Falha ao reativar microfone após ter sido mutado: "${micText}"`);
        }

        // Teste F: Silenciamento final para repouso limpo
        console.log("\n7. Silenciando novamente para concluir em estado seguro...");
        await page.waitForTimeout(500);
        await page.tap('#btn-microphone');
        await page.waitForTimeout(250);

        micText = await page.$eval('#mic-btn-text', el => el.textContent.trim());
        console.log(`-> Estado final: "${micText}"`);
        if (!micText.includes("MUTED")) {
            throw new Error(`Falha no silenciamento final: "${micText}"`);
        }

        console.log("\n=== SUCESSO: VALIDAÇÃO DO BOTÃO DE MUTE/MIC NO MOBILE CONCLUÍDA SEM ERROS ===");
    } catch (err) {
        console.error("\n[FALHA NO TESTE]:", err);
        throw err;
    } finally {
        await browser.close();
    }
}

runMobileMicValidation().catch(e => {
    console.error(e);
    process.exit(1);
});
