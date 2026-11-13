ClipInbox 0.1.0 — captura local de texto para Markdown no Windows 10/11 x64.

- Copia com Ctrl+C e captura com Ctrl+Alt+M, sem abrir o Obsidian.
- Nova anotação pela bandeja, configuração de destino/atalho e autostart opcional.
- Append UTF-8, verificação de gravação e rascunho mantido em caso de falha.

Baixa o ZIP, extrai toda a pasta e executa `ClipInbox.exe`. Python não é necessário.
Configura um `Inbox.md` em UTF-8. `SHA256SUMS.txt` permite conferir o download.

Esta publicação é condicionada a lint, testes Linux/Windows e build com inicialização
automatizada do executável. `smoke-result.json` registra o alcance do smoke test.
Não houve validação humana interativa do atalho físico, menu da bandeja, foco,
SmartScreen ou escalonamento de tela. O executável não tem assinatura digital.

Após erro parcial de escrita, confere o Inbox antes de repetir. Editores externos
podem substituir o arquivo posteriormente; evita edições simultâneas.
