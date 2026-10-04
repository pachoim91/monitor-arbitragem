# Monitor de arbitragem (somente alertas)

Compara livros de ofertas spot da Binance e Bybit para BTC/USDT, ETH/USDT e SOL/USDT. Não envia ordens e não precisa de chaves API das corretoras.

Esta versão não envia mensagem de inicialização ao Telegram, para evitar avisos repetidos. Falhas de uma corretora são registradas nos logs e não derrubam o processo inteiro. Para gerar oportunidades, as duas corretoras precisam estar acessíveis.

## Importante
- `CAPITAL_USDT` é o orçamento em USDT por comparação, não reais.
- Taxas são estimativas; ajuste conforme suas taxas reais.
- Transferências, conversão BRL/USDT, impostos e risco de execução não estão incluídos.
- Alertas são indicativos, não garantia de lucro. É preciso confirmar saldos e execução.
- Nunca publique o token do Telegram. Se ele vazar, revogue-o no BotFather.

## Atualização
Substitua os arquivos do repositório pelos arquivos deste ZIP e aguarde o Render fazer o deploy. Não é necessário alterar o token secreto se ele já estiver configurado.
