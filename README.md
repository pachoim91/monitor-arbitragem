# Monitor de arbitragem (somente alertas)

Compara livros de ofertas spot da Binance e Bybit para BTC/USDT, ETH/USDT e SOL/USDT, nos dois sentidos. Não envia ordens e não precisa de chaves API das corretoras.

## Importante
- `CAPITAL_USDT` é o orçamento em USDT por comparação, não reais. Ajuste conforme o valor convertido e disponível em cada corretora.
- Taxas padrão são estimativas. Ajuste `FEE_BUY` e `FEE_SELL` para suas taxas reais (formato decimal: 0.001 = 0,10%).
- Transferências entre corretoras, custos de conversão BRL/USDT, impostos e risco de execução não estão incluídos.
- Alertas são oportunidades indicativas, não garantia de lucro. Para arbitragem prática, normalmente é preciso já ter saldo/ativos nas duas corretoras.
- O monitor percorre níveis do livro para estimar execução, mas o livro pode mudar antes da ordem.
- Nunca publique o token do Telegram. Se ele vazar, revogue-o no BotFather.

## Deploy no Render
Crie um repositório GitHub privado, envie estes arquivos e conecte o repositório ao Render como **Background Worker**. Configure `TELEGRAM_TOKEN` como variável secreta no Render. O `render.yaml` já define as demais configurações.

## Variáveis principais
- `TELEGRAM_TOKEN`: token do BotFather (secreto)
- `TELEGRAM_CHAT_ID`: seu chat id
- `CAPITAL_USDT`: orçamento em USDT usado para simulação
- `MIN_NET_SPREAD`: limite líquido, 0.005 = 0,5%
- `FEE_BUY`, `FEE_SELL`: taxas estimadas por lado
- `SAFETY_MARGIN`: margem adicional
- `POLL_SECONDS`: intervalo entre ciclos
