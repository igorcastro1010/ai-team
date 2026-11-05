# QA de interação para projetos Next.js

Continuação autorizada da entrega Next.js; implementação local autônoma, sem
merge, deploy ou edição de projetos existentes. Teste manual permanece opcional.

Decisão de implementação: estender o QA declarativo do runtime existente com
`browser_checks` opcionais, sem permitir scripts, selectors CSS, URLs ou comandos
do modelo. Alternativas: código Playwright livre amplia a superfície de execução;
preview persistente exigiria portas e ciclo de vida adicionais. Esta etapa usa
Chromium efêmero no mesmo Docker offline, com Playwright oficial fixo 1.64.1.

Contrato: manter `checks` HTML obrigatório; até 6 cenários de navegador, cada um
com nome, 1–6 ações e texto final visível. Click usa role button/link/checkbox e
nome acessível exato; fill usa label exata e valor limitado. Cada cenário começa
na raiz fixa com contexto novo em 390x844. Sem código QA executável.

O supervisor guarda os critérios em memória antes do build. Chromium sem sandbox
próprio, contido pelo mesmo Docker de proprietário único: usuário 65532, rede
none, cap-drop ALL, raiz read-only, sem mounts/portas/segredos. Não adicionar
SYS_ADMIN, IPC host ou seccomp unconfined. Não homologar código hostil público.
Bloquear URLs externas, downloads, service workers e WebSocket no contexto.
Browser tem teto global de 30 s dentro do limite total existente de 120 s;
2 CPUs, 1 GiB, 128 PIDs, tmpfs 256 MiB e saída 32 KiB permanecem.

Dependências e Chromium são instalados somente ao preparar a imagem, com lock
separado do projeto gerado. Imagem/fingerprint incluem os novos arquivos; a
aprovação cobre critérios e runtime. Históricos preservam seu snapshot.

Aceite: contrato estrito e limitado, clique e formulário reais positivos,
assertiva negativa falha, tentativa de destino externo bloqueada e isolamento
inalterado; regressão Python/texto, aprovação, ZIP e UI existente. Evidência
real de navegador sem consumo de modelo é suficiente para runtime; smoke Hermes
opt-in valida também geração do novo contrato com até cinco chamadas.
