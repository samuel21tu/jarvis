# Rollout do roteador de IA (ominiroute)

> Este documento substitui o antigo plano de rollout do OpenRouter. O Hub agora usa
> um roteador de provedores compatível com Chat Completions para **respostas** e
> **resumo de memória**. Gemini não participa mais do caminho de inferência.

## Escopo

O provedor efetivo é definido por `LLM_PROVIDER=ominiroute` (padrão). O adapter
`RouterProvider` fala com qualquer gateway compatível com a API de Chat
Completions, configurado por variáveis de ambiente — nenhum host fica fixo no
código.

## Variáveis de ambiente

No servidor, provisionar os valores reais fora do repositório:

```env
# OmniRoute local (endpoint OpenAI-compatible)
LLM_PROVIDER=ominiroute
LLM_ROUTER_API_KEY=
LLM_ROUTER_BASE_URL=http://localhost:20128/v1
LLM_ROUTER_MODEL=auto/chat
LLM_ROUTER_FALLBACK_MODELS=grok-cli/grok-4.7-low
LLM_ROUTER_ALLOWED_HOSTS=localhost
```

- `LLM_ROUTER_BASE_URL` aceita `http://localhost`/`127.0.0.1` (gateway local) ou
  HTTPS para hosts remotos. IP privado e HTTP remoto são rejeitados.
- Chave é opcional em localhost; obrigatória para qualquer host remoto.
- `LLM_ROUTER_MODEL=auto/chat` deixa o OmniRoute escolher o provedor disponível;
  use um ID fixo de `/v1/models` se precisar de determinismo.
- `LLM_ROUTER_ALLOWED_HOSTS` (CSV) restringe o host do roteador. Vazio aceita
  qualquer host permitido pela regra acima; prefira preenchê-lo em produção.
- `LLM_ROUTER_API_KEY` é segredo: nunca commitar, imprimir, passar em argumentos
  de processo ou incluir no tarball de deploy.
- `LLM_ROUTER_MODEL` deve vir de uma allowlist revisada; nunca aceitar modelo
  arbitrário informado pelo usuário ou pela requisição.
- Se nenhum modelo reserva for informado, uma falha do modelo principal encerra
  a resposta com mensagem amigável — não há fallback para Gemini.

As demais variáveis (`NEXUS_API_KEY`, `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`,
`OBSIDIAN_VAULT_PATH`, `MEMORY_DB_PATH`, `TZ` e, se necessário, `ALLOWED_ORIGINS`)
continuam conforme o `.env.example`.

## Provisionamento seguro no CasaOS

1. Criar o `.env` diretamente no servidor, fora do repositório e do contexto de build.
2. Aplicar permissões restritas (`0600`) ao arquivo.
3. Preferir Docker secrets ou secret manager; nunca inserir segredos no
   `docker-compose.yml`, Dockerfile, scripts ou tarballs.
4. Validar a presença das variáveis obrigatórias antes de `docker compose up`,
   sem exibir seus valores.
5. Rotacionar qualquer chave que tenha aparecido em log, terminal ou histórico.
6. Usar chave SSH/`ssh-agent` para o deploy e manter verificação estrita de `known_hosts`.

## Validações antes de liberar produção

- `LLM_ROUTER_API_KEY` não aparece em `git diff`, logs, tarball ou lista de processos.
- O `.env` não é copiado pelo script de empacotamento.
- O endpoint usa TLS e a porta do Hub não fica exposta além do reverse proxy/firewall.
- Modelo, base_url, allowlist de host e metadados são definidos por configuração controlada.
- Há limites de custo/uso no roteador e alertas configurados.
- Existe procedimento testado de rotação da chave e substituição do roteador.
