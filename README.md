# ClipInbox

**Copiar → Ctrl+Alt+M → texto salvo no Inbox.md.**

Um utilitário pequeno para Windows que acrescenta o texto copiado a um arquivo
Markdown, com data e hora, sem abrir o Obsidian ou interromper o aplicativo em uso.
Também permite escrever uma anotação pela bandeja do sistema.

Versão **0.1.0** · Windows 10/11 x64 · MIT · interface em português brasileiro.

## Download e instalação

Baixa **`ClipInbox-v0.1.0-windows-x64.zip`** na
[página de releases](https://github.com/LuizChockt/clipinbox/releases).
O ZIP só é publicado após os testes e o build Windows do workflow passarem.
Se ainda não houver um ZIP, consulta o estado em
[Actions](https://github.com/LuizChockt/clipinbox/actions): código e workflow
disponíveis, por si só, não significam que já existe um executável publicado.

1. Extrai **todo o ZIP** para uma pasta permanente, como `Documentos\Aplicativos`.
2. Abre a pasta `ClipInbox` e executa **`ClipInbox.exe`**.
3. Seleciona teu `Inbox.md` ou clica em **Criar novo…** e confirma o caminho.
4. Clica em **Salvar**. O aplicativo permanece na bandeja, junto ao relógio.

Não precisa instalar Python, executar como administrador nem ter Obsidian instalado.
Mantém a pasta `_internal` junto ao executável. Não executa de dentro do ZIP.
Se o ícone estiver oculto, abre a seta de ícones junto ao relógio do Windows.

O executável não tem assinatura digital e pode gerar alertas do SmartScreen.
Confere a origem do download e seu hash; **não desativa o antivírus nem outras
proteções**. Um hash confirma integridade em relação ao arquivo publicado, não
substitui assinatura digital ou análise de segurança.

Para conferir o hash no PowerShell, executa na pasta do download:

```powershell
Get-FileHash .\ClipInbox-v0.1.0-windows-x64.zip -Algorithm SHA256
```

Compara com `SHA256SUMS.txt` da mesma release.

## Capturar um texto

1. Seleciona um trecho no navegador, PDF ou outro aplicativo.
2. Pressiona **Ctrl+C**.
3. Pressiona **Ctrl+Alt+M**.
4. Uma notificação confirma a gravação; a janela em uso mantém o foco.

O texto que estiver no clipboard no momento da leitura é salvo. O ClipInbox não
simula Ctrl+C e não transforma nem limpa o conteúdo. Imagens e arquivos não são
capturados. Copiar o mesmo texto e solicitar outra captura salva outra anotação.

Exemplo do arquivo:

```markdown
### 2026-01-02 14:30:00

Trecho de exemplo, com acentos.
Outra linha do mesmo trecho.

### 2026-01-02 14:32:10

- Uma anotação
- Outra ideia
```

Os horários são locais, conforme o relógio do Windows.

## Bandeja e anotações manuais

Clica com o botão direito no ícone:

| Opção | Ação |
|---|---|
| Capturar área de transferência | Salva o texto copiado, como o atalho |
| Nova anotação | Abre um campo multilinha; salva com Ctrl+Enter ou Salvar |
| Abrir Inbox | Abre o arquivo no programa associado a `.md` no Windows |
| Configurações | Altera destino, atalho e preferências |
| Sair | Encerra o processo e libera bandeja e atalho |

Esc, Cancelar e o botão de fechar cancelam a anotação; há confirmação se existir
texto não salvo. Fechar essa janela não encerra o aplicativo. Uma falha de
gravação mantém o rascunho para que possas corrigir o problema e tentar novamente.

## Configurações

**Destino:** seleciona um arquivo `.md` existente ou cria um novo dentro de uma
pasta que já existe. Um novo arquivo exige confirmação e nunca substitui um
arquivo existente. O destino pode estar em um vault do Obsidian ou em qualquer
outra pasta. Se o arquivo for removido, a captura falha; não o recria silenciosamente.

**Atalho:** padrão `Ctrl+Alt+M`. São aceitos pelo menos dois entre Ctrl, Alt e
Shift, seguidos de A–Z, 0–9 ou F1–F11. Exemplo: `Ctrl+Shift+F9`.
Win, F12, Ctrl+Alt+Del e atalhos simples de edição não são aceitos. Conflitos são
informados. Ao alterar o atalho, o anterior só é liberado depois que o novo foi
registrado. Em teclados ABNT2, AltGr pode se comportar como Ctrl+Alt; usa
Ctrl+Shift+F9 se isso conflitar com tua digitação.

**Notificações:** a confirmação de sucesso pode ser desativada. Erros continuam
sendo sinalizados. O Windows pode suprimir notificações; a gravação independe
delas. O último estado também fica no tooltip da bandeja e ao abrir Configurações.
As notificações não contêm o texto capturado.

**Iniciar com Windows:** desativado por padrão; disponível na distribuição
executável. Usa somente o valor `ClipInbox` em
`HKCU\Software\Microsoft\Windows\CurrentVersion\Run`. Não altera outras entradas.
Se mudares a pasta do programa, desativa e reativa a opção na nova localização.
Na execução pelo código-fonte não é possível ativá-la.

As preferências ficam em **`%APPDATA%\ClipInbox\config.json`**. São gravadas por
arquivo temporário seguido de substituição. JSON inválido abre uma configuração
recuperável e não altera o Inbox. O conteúdo de anotações nunca entra no JSON.

## Integridade, erros e limites

- Gravação binária em **append**, UTF-8, sem truncar nem reformatar bytes anteriores.
- Aceita UTF-8 com ou sem BOM. Rejeita UTF-16/32 identificado, texto inválido em
  UTF-8 e caracteres nulos. Não converte arquivos automaticamente.
- Preserva o texto recebido, inclusive espaços e quebras de linha. Os separadores
  novos seguem LF ou CRLF do arquivo; conteúdo de origens diferentes pode resultar
  em finais de linha mistos, sem reescrever notas anteriores.
- Valida o arquivo em blocos de 64 KiB na primeira escrita e após alteração externa
  detectada. Capturas seguintes usam o resultado em cache e leem somente a cauda.
  Arquivos grandes não são carregados inteiros na memória nem reescritos.
- Serializa as gravações internas. No Windows abre um handle que permite leitores,
  mas impede outros escritores e deleções durante a captura. Um editor já aberto
  com acesso de escrita pode causar uma falha de compartilhamento.
- Só informa sucesso depois de verificar a escrita, executar flush/fsync e conferir
  o tamanho final. Falhas parciais ou de sincronização são marcadas como **incertas**:
  confere o final do Inbox antes de repetir, pois o registro pode já estar nele.
- Não tenta novamente automaticamente e não trunca o arquivo para desfazer uma
  escrita parcial. Um erro de disco pode deixar um registro incompleto.
- Uma captura que falhou fica temporariamente em memória e pode ser recuperada
  em **Nova anotação**. Novas capturas aguardam essa recuperação. Não é histórico;
  apenas um rascunho pendente. Encerrar ou perder o processo pode perder esse rascunho.
- Enquanto uma captura estiver sendo gravada, outro comando informa que é preciso
  aguardar. `MOD_NOREPEAT` também evita repetições da tecla mantida pressionada.

**Não há transação universal com outros editores.** Depois que o ClipInbox fecha
o arquivo, um editor ou sincronizador pode substituí-lo usando uma cópia antiga.
Prefere uma pasta local, evita edições simultâneas do mesmo Inbox e mantém teus
backups habituais. Pastas de rede, arquivos somente online, permissões especiais
e caminhos excessivamente longos dependem do Windows/provedor e não são garantidos.

Blocos de código Markdown não fechados no texto original podem afetar a aparência
das anotações seguintes; o ClipInbox preserva o texto e não tenta corrigir Markdown.
Captura apenas o texto oferecido pelo aplicativo de origem, sem formatação rica.

## Privacidade

O aplicativo opera localmente e offline. Não usa rede, serviços externos, conta,
telemetria, analytics, logs de conteúdo, histórico de clipboard ou hooks de teclado.
Lê o clipboard **somente após comando explícito**. Não instala plugins no Obsidian,
não chama sua CLI e não abre o Obsidian durante uma captura.

O atalho salva o que tu copiaste, inclusive se for uma senha ou informação
confidencial. Usa-o somente para o que desejas registrar. A segurança e eventual
sincronização do arquivo escolhido seguem as configurações da tua pasta.

## Atualizar e remover

Para atualizar, usa **Sair**, extrai a nova versão para uma pasta permanente e
abre o novo executável. As preferências permanecem em AppData. Se o caminho do
executável mudar, atualiza a opção de inicialização com Windows.

Para remover, desativa **Iniciar ClipInbox com o Windows**, usa **Sair** e apaga a
pasta extraída. Se quiseres, remove também `%APPDATA%\ClipInbox`. O Inbox permanece
intacto. Caso tenhas apagado o executável primeiro, remove apenas o valor
`ClipInbox` da chave Run indicada acima; não apaga outras entradas.

## Desenvolvimento e testes

Python **3.12 ou superior**; versão usada no CI e no pacote: **3.12 x64**.
Runtime: Tkinter/ttk da biblioteca padrão, pystray 0.19.5 e Pillow 13.0.0.
As versões diretas ficam fixadas no `pyproject.toml`. O empacotamento só funciona
no Windows; não há compilação cruzada oficial do PyInstaller.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev,build]"
.\.venv\Scripts\python -m clipinbox
.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m ruff format --check .
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python scripts/build_windows.py
```

O build gera um pacote `onedir`, inicia o **executável empacotado** em uma pasta
com espaços e acentos, verifica inicialização e salvamento manual automatizado,
e produz ZIP, SHA-256 e `smoke-result.json` em `release/`.

Testes de núcleo funcionam também no Linux. Integrações Win32 são ignoradas fora
do Windows. O teste de clipboard real exige ambiente Windows descartável:

```powershell
$env:CLIPINBOX_DESKTOP_TESTS = "1"
.\.venv\Scripts\python -m pytest -q
```

Essa opção **altera o clipboard do ambiente de testes**. Não a uses durante trabalho
pessoal. A aplicação normal e o smoke test do executável não alteram o clipboard.

O CI roda lint, testes e build a cada push/PR. Apenas tags correspondentes à
versão (por exemplo, `v0.1.0`) publicam releases depois dos dois jobs aprovados.
O token é de leitura nos testes; somente o job de release recebe escrita.
Os Actions são fixados por SHA. Pull requests não publicam releases.

**Testes automatizados de widgets e APIs não equivalem a teste humano de uso.**
Notificação visível, tecla física, foco no aplicativo externo, menu da bandeja,
SmartScreen e escalas de tela precisam de conferência em desktop Windows.
Consulta [VALIDATION.md](docs/VALIDATION.md) para o checklist e o alcance da verificação.

## Por que outro utilitário?

QuickAdd oferece capturas dentro do Obsidian; PowerToys Advanced Paste converte e
cola conteúdo; Flow Launcher é um iniciador extensível. ClipInbox mantém um único
fluxo: acrescentar texto ao Markdown sem abrir o Obsidian, instalar plugins nele
ou manter serviços. Não tenta substituir essas ferramentas.

Não inclui OCR, imagens, IA, sincronização própria, vários destinos, atualizador,
histórico ou editor completo. Há somente uma instância por sessão Windows.

## Licença e referências

[MIT](LICENSE). Ícone original geométrico, reproduzível por `scripts/make_icon.py`.
A distribuição inclui avisos de licença de dependências em `licenses/`.

Decisões baseadas na documentação oficial:
[RegisterHotKey](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-registerhotkey),
[Tkinter](https://docs.python.org/3/library/tkinter.html),
[pystray](https://pystray.readthedocs.io/en/latest/usage.html),
[PyInstaller](https://pyinstaller.org/en/stable/usage.html),
[Obsidian CLI](https://obsidian.md/help/cli),
[QuickAdd](https://quickadd.obsidian.guide/docs/Choices/CaptureChoice/),
[Advanced Paste](https://learn.microsoft.com/en-us/windows/powertoys/advanced-paste),
[permissões do GitHub Actions](https://docs.github.com/en/actions/tutorials/authenticate-with-github_token).
