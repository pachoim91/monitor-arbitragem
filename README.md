# Monitor de arbitragem Bybit + OKX

Monitor de livros públicos spot, apenas para alertas. Não envia ordens nem precisa de chaves das corretoras.

## Variáveis no Render
- `TELEGRAM_BOT_TOKEN`: token do bot (mantenha secreto)
- `TELEGRAM_CHAT_ID`: seu chat id
- `CAPITAL_USDT`: orçamento de referência em USDT
- `MIN_NET_SPREAD_PCT`: spread líquido mínimo percentual
- `FEE_PER_SIDE_PCT`: taxa estimada por lado
- `SAFETY_MARGIN_PCT`: margem de segurança percentual
- `POLL_SECONDS`: intervalo entre consultas (mínimo 5)
- `ALERT_COOLDOWN_SECONDS`: intervalo mínimo entre alertas iguais

## Observações
O cálculo é estimativo e não considera conversão BRL/USDT, saques, transferências, impostos, diferenças de taxas por conta nem a disponibilidade de saldo nas duas corretoras. Oportunidades podem desaparecer antes da execução. Não é recomendação financeira.
