# AI TEAM — desenho e limites

## Objetivo
Centralizar projetos, solicitações, agentes, aprovações e histórico em português. Interface utilizável no navegador do Windows e na Web. Entregar por versões verificadas, com execução fora do painel.

## Decisões locais
O usuário definiu Next.js + FastAPI + LangGraph e autorizou decisões locais seguras. Adotamos monorepo independente; API e worker compartilham persistência transacional, nunca memória de processo como fonte de verdade. Painel usa proxy de mesma origem. Autenticação inicial de proprietário único com senha Argon2, sessão opaca com expiração e logout revogável. Cadastro do proprietário somente via CLI local, sem rota pública de registro. SQLite local; PostgreSQL/Supabase no servidor, sem expor tabelas à Data API.

## Alternativas consideradas
1. Supabase Auth obrigatório desde o primeiro boot: reduz manutenção de login, mas exige projeto externo antes de qualquer teste local. Reservado para eventual multiusuário.
2. Proprietário único no backend, banco SQL portável: permite instalação Windows sem conta externa. Escolha do implementador para V0.1.
3. Desktop empacotado com Electron: acrescenta runtime e distribuição antes do núcleo. Adiado; navegador local atende primeiro o Windows.

## Interface
Sala de operações escura, tipografia de sistema, verde ácido como acento e hierarquia editorial. Navegação para visão geral, CEO, projetos, tarefas, agentes, execuções, aprovações, histórico, relatórios e integrações. Sem números fictícios: estados vazios e indicadores derivados do banco. Formulários com labels, feedback, foco e alvos de toque de 44px. Responsiva desde 360px.

## Fluxo e contratos
V0.1: login -> criar projeto -> criar tarefa -> mover tarefa manual -> consultar histórico. Estado persistido e auditado. Sessões duram 12h. Limite de tentativas de login persiste no banco.
V0.2: solicitação -> fila persistente -> CEO planeja -> aprovação no modo manual/supervisionado -> DEV/DESIGNER -> QA -> CEO relata. Sem credencial de modelo, execução permanece bloqueada com explicação. Test doubles somente em testes. Nada de conclusão simulada.
V0.3: GitHub via SDK/API oficiais, repositórios permitidos, writes vinculados a aprovação e branch de trabalho.
V0.4: Codex SDK/CLI em executor próprio; Vercel inicialmente leitura, publicação exige aprovação de artefato específico.
V0.5: agendamento persistente, jobs isolados, limites e relatórios.
V1.0: somente após homologação real das integrações, PostgreSQL, recuperação e publicação autorizada.

## Segurança e falhas
API exige sessão para todos os dados. Mutações com cookie exigem origem permitida; proxy não aceita destino arbitrário. Inputs limitados. Senha e token de sessão nunca persistidos em claro. Não há shell nem acesso a outros checkouts em V0.1. Ações sensíveis não são executáveis por texto ou modo automático. Logs de falha não incluem exceções com segredos.

## O que não está decidido pelo usuário
Provedor/modelo, orçamento monetário, projeto Supabase e hospedagem de API/worker. Sem essas configurações não declarar integração homologada, produção pronta ou autonomia externa funcionando.
