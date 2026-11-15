# Rollout do OpenRouter

## Escopo

Este documento prepara o deploy para uma futura integração com OpenRouter sem alterar o código do Hub. O provedor efetivo continua sendo Gemini até que a integração da aplicação seja implementada e validada.

## Variáveis de ambiente

No servidor, provisionar os valores reais fora do repositório:

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=<segredo-do-gemini>
OPENROUTER_API_KEY=<segredo-do-openrouter>
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=<modelo-aprovado-na-allowlist>
OPENROUTER_HTTP_REFERER=https://seu-dominio.example
OPENROUTER_X_TITLE=JARVIS
```

- `LLM_PROVIDER=gemini` mantém o comportamento atual; não selecionar `openrouter` antes de existir suporte correspondente no código.
- `OPENROUTER_API_KEY` é segredo e nunca deve ser commitado, impresso, passado em argumentos de processo ou incluído no tarball de deploy.
- `OPENROUTER_BASE_URL` deve permanecer no endpoint HTTPS oficial, salvo decisão documentada.
- `OPENROUTER_MODEL` deve ser escolhido de uma allowlist revisada; não aceitar modelo arbitrário informado por requisição.
- `OPENROUTER_HTTP_REFERER` e `OPENROUTER_X_TITLE` são metadados não secretos e opcionais.

As demais variáveis atuais (`NEXUS_API_KEY`, `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`, `OBSIDIAN_VAULT_PATH`, `MEMORY_DB_PATH`, `TZ` e, se necessário, `ALLOWED_ORIGINS`) continuam obrigatórias ou opcionais conforme o `.env.example` e o código atual.

## Provisionamento seguro no CasaOS

1. Criar o `.env` diretamente no servidor, fora do repositório e fora do contexto do build.
2. Aplicar permissões restritas (`0600`) e proprietário exclusivo do usuário que executa o Compose.
3. Preferir Docker secrets, secret manager ou mecanismo equivalente; não inserir segredos no `docker-compose.yml`, Dockerfile, scripts, tarballs ou histórico shell.
4. Validar a presença das variáveis obrigatórias antes de `docker compose up` sem exibir seus valores.
5. Rotacionar qualquer chave que tenha aparecido em arquivo local, log, terminal, backup ou histórico.
6. Usar chave SSH/`ssh-agent` para o deploy; não manter senha CasaOS em scripts. Manter verificação estrita de `known_hosts`.

## Sequência de rollout

1. **Preparação:** implementar e revisar o adapter OpenRouter no código, sem remover o fallback Gemini.
2. **Validação local:** testar autenticação, timeout, erros HTTP, limites, respostas vazias e indisponibilidade do provedor sem registrar o token.
3. **Staging:** usar uma chave OpenRouter dedicada, modelo da allowlist e tráfego limitado; manter `LLM_PROVIDER=gemini` até concluir os testes.
4. **Deploy:** transferir somente artefatos não secretos, confirmar que o `.env` remoto já existe e executar o build/recreate.
5. **Smoke test:** verificar health endpoint, autenticação do nó, uma requisição LLM e o fallback para Gemini.
6. **Ativação gradual:** habilitar OpenRouter somente por configuração e aumentar o tráfego progressivamente, observando latência, erros, custo e limites.
7. **Rollback:** retornar `LLM_PROVIDER=gemini`, recriar o container e confirmar o health check; preservar a imagem anterior para recuperação.

## Validações antes de liberar produção

- `OPENROUTER_API_KEY` não aparece em `git diff`, tarball, logs ou lista de processos.
- O `.env` não é copiado pelo script de empacotamento.
- O endpoint usa TLS e a porta do Hub não fica exposta além do reverse proxy/firewall necessário.
- Modelo, origem e título estão definidos por configuração controlada.
- Há limites de custo/uso no provedor e alertas configurados.
- Existe procedimento testado de rotação da chave e rollback para Gemini.
