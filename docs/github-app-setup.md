# GitHub App — preparação da V0.3

A escolha do proprietário foi GitHub App com instalação por repositório. O conector disponível não cria Apps; implementamos o fluxo oficial de manifesto, separado da execução de agentes.

```powershell
.\tools\setup-github-app.ps1
```

O comando imprime um endereço temporário em 127.0.0.1. Abra-o, revise as permissões e siga para o GitHub. A App deve ser privada e pertencer a `igorcastro1010`. O GitHub pede confirmação do registro; depois a página local recebe um código de uso único, troca-o diretamente pela configuração e salva a chave no cofre do sistema. O serviço expira em 15 minutos, não registra URLs de callback e não grava tokens/PEM em arquivos.

Permissões solicitadas: `contents:write`, `issues:write`, `pull_requests:write`, `metadata:read`. Sem administração, exclusão de repositórios, pagamentos ou workflows. Webhook desativado e nenhum evento assinado. Não solicitamos OAuth de usuário.

Após o registro, clique no link de instalação e escolha **Only select repositories → ai-team**. Não selecione todos os repositórios. A integração operacional só será declarada pronta após validar autenticação da App, instalação, restrição ao repositório e chamadas reais de desenvolvimento.

O cofre preserva apenas App ID, slug e PEM. Segredos OAuth/webhook não utilizados são descartados. Chaves grandes são divididas em entradas curtas para respeitar o limite do cofre Windows; metadados de conclusão só são gravados depois das partes. Sem fallback para armazenamento em texto. Configuração existente nunca é sobrescrita automaticamente.

Estado, prazo e uso único protegem o callback. A origem de conversão é fixa em `api.github.com`; a conta proprietária é validada antes de salvar. O serviço só aceita o Host da própria porta loopback. Não compartilhe o endereço temporário de registro.

Testes locais cobrem manifesto/permissões, armazenamento em partes, descarte de segredos não usados, falha parcial, conta errada, state inválido e replay. Esses testes não substituem o registro e a instalação reais no GitHub. Nenhuma ferramenta GitHub está habilitada nos agentes neste preparo.

Fontes: [manifesto oficial](https://docs.github.com/en/apps/sharing-github-apps/registering-a-github-app-from-a-manifest), [API de GitHub Apps](https://docs.github.com/en/rest/apps/apps?apiVersion=2026-03-10).
