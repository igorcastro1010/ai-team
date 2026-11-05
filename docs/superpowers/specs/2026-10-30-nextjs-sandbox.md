# Próxima entrega: projetos Next.js isolados

Continuação da sequência recomendada e aceita: Python primeiro, depois Next.js.
O proprietário pediu avançar e deixou seu teste manual para depois; esse teste
não bloqueia desenvolvimento nem amplia permissões de produção/GitHub.

Reutilizar o fluxo existente com escopo opt-in `nextjs_code`: CEO planeja, DEV
gera `app/page.tsx` e componentes `.tsx`, DESIGNER gera `app/globals.css`, QA
gera `tests/acceptance.json` com verificações declarativas do HTML renderizado.
Nenhum comando, URL externa, configuração npm ou dependência vem do modelo.

O servidor acrescenta scaffold revisado com package/lock/tsconfig/layout/config.
O hash aprovado cobre também esse scaffold. ZIP contém um projeto executável
localmente, sem node_modules ou binários. Versões iguais às já homologadas no
painel: Next 16.4.3, React 19.3.1, TypeScript 5.9.3 e Node 24.

Imagem preparada separadamente a partir do Node oficial por digest e lockfile
com integridade npm; scripts de instalação desativados. O build recebe somente
os arquivos revisados por stdin e não tem rede, mounts, credenciais ou acesso
ao repositório. Imagem local identificada por ID imutável e hash do runtime.

Limites: 2 CPUs, 1 GiB, 128 PIDs, tmpfs 256 MiB, 120 s e saída 32 KiB. Usuário
65532, rootfs somente leitura, cap-drop ALL, no-new-privileges e watchdog interno.
Build com comando fixo; em seguida servidor em loopback interno e verificações
de status/texto propostas pelo QA, executadas pelo supervisor confiável.
Não executar código QA, navegar em URLs do modelo, nem aceitar saída zero
prematura como aprovação. Testes não certificam código deliberadamente hostil.

Separar suíte e relatório CEO em dois turnos do worker: até 120 s cada, dentro
da lease atual de 180 s. O resultado persistido não é executado novamente.
Manter Python, relatórios textuais, agendas e recuperação de contêineres.

Aceite: validação dos caminhos/roles/JSON, scaffold imutável, hash completo,
aprovação/replay/cancelamento, suíte em dois turnos, ZIP válido, geração real,
build e HTML reais, falha/timeout/saída excessiva, isolamento e controles de UI.
Sem publicação, merge, edição de checkouts ou ampliação da GitHub App.
