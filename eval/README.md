# Eval do Radar (R-08)

Mede precisão, recall e alarmes falsos contra `data/gabarito.json`.

**Atenção: rodar o eval chama o modelo e custa.** Itere com `--limite N` (avalia só os N primeiros
registros) e rode completo só com o prompt pronto. O Sonnet só para o número final.

```powershell
python eval/rodar_eval.py --versao v1-prompt-a --limite 10   # barato, para iterar
python eval/rodar_eval.py --versao v1-prompt-a               # rodada completa
python eval/rodar_eval.py --comparar eval/resultados/A.json eval/resultados/B.json
python eval/rodar_eval.py --help
```

- Chama `radar.pipeline.analisar` (sem a pausa de aprovação) com `MODO_DEMO` desligado: o cache
  da demo nunca mascara o código atual.
- Só conta como alerta o que seria **postado** (`decidir_acao`); resumo e descarte não contam.
- Cada rodada grava `eval/resultados/AAAA-MM-DD_HHMM.json` e `.md` e uma linha em
  `eval_execucoes` (SQLite). `--sem-db` pula o banco.
- `--comparar` imprime a tabela "antes x depois" de duas rodadas (evidência para o slide).
