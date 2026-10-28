# GitHub App — preparação da V0.3

A escolha do proprietário foi GitHub App com instalação por repositório. O conector disponível não cria Apps; implementamos o fluxo oficial de manifesto, separado da execução de agentes.

```powershell
.\tools\setup-github-app.ps1
```

O comando imprime um endereço temporário em 127.0.0.1. Abra-o, revise as permissões e siga para o GitHub. A App deve ser privada e pertencer a `igorcastro1010`. O GitHub pede confirmação do registro; depois a página local recebe um código de uso único, troca-o diretamente pela configuração e salva a chave no cofre do sistema. O serviço expira em 15 minutos, não registra URLs de callback e não grava tokens/PEM em arquivos.

Entre no GitHub no mesmo navegador antes de usar o botão de cadastro. Sempre inicie pela página local: o botão envia um formulário `POST`, com `Content-Type: application/x-www-form-urlencoded` e o parâmetro `manifest` contendo JSON. Abrir/recarregar diretamente a URL `github.com/settings/apps/new?state=...` via GET não transporta esse JSON e pode produzir `"url" wasn't supplied`. Nesse caso, retorne à página local e reenvie pelo botão; gere novo endereço se o fluxo tiver expirado.

O manifesto contém `url` na raiz e em `hook_attributes`, ambas apontando para `https://github.com/igorcastro1010/ai-team`. O webhook permanece desativado, sem eventos. Antes de renderizar o formulário, o código valida essas URLs e o `redirect_url` loopback da porta atual, com caminho `/callback`. `callback_urls` é omitido porque este registro não usa OAuth de usuário; o retorno do manifesto usa `redirect_url`. O `state` aleatório acompanha a ação do formulário e é validado no retorno antes de qualquer troca de código.

Permissões solicitadas: `contents:write`, `issues:write`, `pull_requests:write`, `metadata:read`. Sem administração, exclusão de repositórios, pagamentos ou workflows. Webhook desativado e nenhum evento assinado. Não solicitamos OAuth de usuário.

Após o registro, clique no link de instalação e escolha **Only select repositories → ai-team**. Não selecione todos os repositórios. A integração operacional só será declarada pronta após validar autenticação da App, instalação, restrição ao repositório e chamadas reais de desenvolvimento.

O cofre preserva apenas App ID, slug e PEM. Segredos OAuth/webhook não utilizados são descartados. Chaves grandes são divididas em entradas curtas para respeitar o limite do cofre Windows; metadados de conclusão só são gravados depois das partes. Sem fallback para armazenamento em texto. Configuração existente nunca é sobrescrita automaticamente.

Se o cadastro já tiver concluído, executar o comando novamente abre uma página local de revisão da App existente e seu link de instalação, sem formulário de criação nem troca de novas credenciais. Isso evita duplicar a App ao repetir a configuração. Durante esta correção, o callback original concluiu e confirmou a gravação da App `ai-team-igorcastro1010` no cofre; sua instalação e acesso real à API ainda não foram homologados.

Estado, prazo e uso único protegem o callback. A origem de conversão é fixa em `api.github.com`; a conta proprietária é validada antes de salvar. O serviço só aceita o Host da própria porta loopback. Não compartilhe o endereço temporário de registro.

Testes locais cobrem manifesto/permissões, armazenamento em partes, descarte de segredos não usados, falha parcial, conta errada, state inválido e replay. Esses testes não substituem o registro e a instalação reais no GitHub. Nenhuma ferramenta GitHub está habilitada nos agentes neste preparo.

Regressões adicionais verificam o formulário HTML decodificado e sua serialização URL-encoded, JSON válido com os dois campos `url`, método POST, preservação de state, rejeição de configuração incompleta, expiração e falha na conversão sem persistir credenciais. Reprodução no navegador: o formulário servido com ambas as URLs chegou ao login do GitHub sem o erro de manifesto. A causa exata da navegação anterior sem configuração não foi observada; a URL da página de erro, isoladamente, não informa se ela recebeu POST ou GET.

Fontes: [manifesto oficial](https://docs.github.com/en/apps/sharing-github-apps/registering-a-github-app-from-a-manifest), [API de GitHub Apps](https://docs.github.com/en/rest/apps/apps?apiVersion=2026-03-10).

## Validação própria da instalação
Execute `.venv\Scripts\python.exe -m ai_team.github_client`. O comando usa somente a chave do cofre, JWT RS256 de nove minutos e API REST oficial. Confere a identidade da App, a conta, seleção por repositório, permissões e ausência de suspensão. Um token temporário com apenas leitura de metadados consulta o escopo real da instalação: é obrigatório conter exatamente o repositório privado `igorcastro1010/ai-team`. Nenhum token é gravado nem exibido; redirects e retries estão desativados e erros da API são sanitizados.

Homologação real em 28/10/2026: App `ai-team-igorcastro1010`, instalação `176042197`, repositório privado `igorcastro1010/ai-team`, branch padrão `main`; autenticação e leitura aprovadas. Esta evidência não valida ainda branches, commits, issues ou PRs. Testes adicionais usam chave RSA sintética em memória e transporte simulado, incluindo escopo amplo, repositório errado e erro de API contendo segredo.
