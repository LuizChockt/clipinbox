# Validação da versão 0.1.0

Este documento separa cobertura automatizada de aceitação prática. A existência
de um teste ou workflow não comprova que tenha sido executado. Os resultados
efetivos estão nos relatórios `test-results.xml`, `smoke-result.json` e nos logs
da execução correspondente em GitHub Actions.

## Verificações locais já executadas

- Linux, Python 3.12.14: 91 testes aprovados, 10 testes Windows ignorados.
- Ruff: lint e formatação verificados.
- Não há desktop Windows no ambiente de desenvolvimento local.
- Nenhum teste interativo humano Windows foi executado localmente.

Esses números descrevem a execução local inicial; novos testes podem ampliar a
contagem. O relatório do commit/release específico é a referência para sua execução.

## O que cada camada prova

| Camada | Verifica | Não verifica |
|---|---|---|
| Núcleo no Linux/Windows | Bytes anteriores, UTF-8/BOM, LF/CRLF, timestamp, concorrência, falhas e JSON | Comportamento visual do Windows |
| Win32 no Windows | Registro/conflito/liberação de atalho, mutex, bloqueio de arquivo, ABI | Pressionamento físico em outro aplicativo |
| Mensagem sintética WM_HOTKEY | Entrega ao callback fora da thread Tk | Tecla física ou ausência de interferência no foco |
| Tk no runner isolado | Clipboard real com texto fictício e retenção de rascunho | Área de transferência do usuário e aplicativos diversos |
| EXE com `--smoke-test` | Recursos, Tk, bandeja inicializada, registro nativo, salvamento manual automatizado e encerramento | Menu clicado por pessoa, notificação visível, tecla física, SmartScreen |

O smoke test usa Inbox temporário e nunca acessa o clipboard pessoal nem modifica
preferências ou inicialização do usuário. O teste de clipboard habilitado por
`CLIPINBOX_DESKTOP_TESTS=1` altera o clipboard do runner descartável.

## Checklist humano Windows — pendente

Usa um Inbox de teste e não um documento pessoal para a primeira conferência.

| ID | Verificação | Estado humano |
|---|---|---|
| A01–A02 | Extrair ZIP e configurar arquivo existente/novo | Pendente |
| A03–A05 | Copiar do Bloco de Notas/navegador e apertar Ctrl+Alt+M | Pendente |
| A06–A08 | Conferir bytes anteriores, Unicode e horário | Núcleo automatizado; prática pendente |
| A09 | Repetir captura com Obsidian fechado | Pendente; código não depende de Obsidian |
| A10–A11 | Usar nota manual, Ctrl+Enter, Esc, menu e notificações | Pendente |
| A12 | Reiniciar e conferir configurações e mudança de atalho | Pendente |
| A13 | Testar arquivo bloqueado/somente leitura e recuperar rascunho | Núcleo automatizado; prática pendente |
| A14 | Sair, conferir ausência do processo e liberação do atalho | Smoke automatizado quando executado; prática pendente |
| A15 | Iniciar em máquina sem Python instalado | Pendente; CI inicia pacote autossuficiente em runner com Python |
| A16 | Capturar somente por comando explícito | Fluxo revisado e testado; sem listener de clipboard |
| A17 | Conferir resultado dos testes no commit da release | Consultar logs |
| A18 | Seguir README desde o download | Documentado; prática pendente |

Conferências adicionais: segurar a tecla sem repetição, pressionar novamente para
salvar texto idêntico, segunda instância, conflito com outro aplicativo, ABNT2/AltGr,
100%/150%/200% de escala, foco externo, notificações bloqueadas, autostart ativado e
desativado e associação padrão de `.md`. Repetir em Windows 10 e Windows 11.

## Limitações da integridade

Falha parcial não é revertida nem repetida. O rascunho fica em memória, sem fila
persistente. Um encerramento forçado ou falha de energia pode perdê-lo. Bloqueio
de compartilhamento é temporário; após o fechamento um editor pode sobrescrever
o arquivo. A validação em cache usa identidade, tamanho e timestamps; não é um
sistema de versionamento contra alterações externas deliberadamente invisíveis.
