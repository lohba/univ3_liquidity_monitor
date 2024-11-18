# Overview
Our objective is to efficiently manage a $1 million liquidity position in the wstETH/ETH Uniswap V3 pool This script monitors the position and alerts via Telegram when action is needed. The system tracks key metrics like price bounds, pool activity, and gas price to balance yields with rebalancing costs.

## Position Strategy
- Allocate 45% to wstETH, 45% to ETH, and 10% for operational reserves.
- Set a conservative ±0.25% range from the mid-price of wstETH/ETH. The range was set to maximize time in range and yield from backtesting data from [revert.finance](https://revert.finance/#/initiator?network=mainnet&exchange=uniswapv3&token1=0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2-native&token0=0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0)

## Rebalancing Strategy
Position adjustment involves assessing the need for rebalancing based on alerts and market conditions. We will use a multi-sig wallet and require multiple signers for any on-chain activity. We will conduct frequent backtesting to evaluate the profitability of our price ranges. This enables us to improve our allocation and rebalancing strategies using empiracle data and market trends. We manage risks by continuously monitoring market volatility, adjusting price ranges, or temporarily withdrawing liquidity during extreme conditions.

## Monitoring
Essential metrics such as price bounds, pool activity, and gas prices are continuously monitored. Alerts are triggered when:
- Price approaches/exits defined range
- Volume changes >10%
- TVL changes >5%
- wstETH/ETH price ratio changes by >0.3%
- Gas prices favorable for rebalancing

## Assumptions
Given that the wstETH/ETH pool frequently experiences volume changes exceeding 50%+, we set a volume change alert threshold at greater than 10% to capture significant shifts. Since Total Value Locked (TVL) is generally less volatile, we use a 5% threshold to capture meaningful fluctuations. The wstETH/ETH price ratio typically changes by around 0.1% over 24 hours and up to 0.2% over longer periods. To identify more substantial movements, we set the price ratio change threshold at greater than 0.3%. For gas price alerts, we employ a simplified approach by calculating the average gas price over the past three days and comparing it to the current gas price. If the current gas price is lower than the three-day average, it indicates favorable conditions for rebalancing.

## Failure Handling
- Positions and TVL functions have try-except blocks that catch exceptions during data fetching and processing
- In the main function's while True loop, exceptions are caught to prevent the script from crashing unexpectedly.




# Setup Instructions
1. Install the dependencies in the package
```
pip install python-dotenv gql requests python-telegram-bot
```
2. Create Telegram Bot

Open Telegram app
Search for "@BotFather"
Click "Start"
Send "/newbot" command
Choose bot name (e.g., "My Position Monitor")
Choose username (must end in 'bot')
Save the API token BotFather provides

3. Get Your Chat ID

Search for your new bot using provided username
Click "Start" or send "/start"
Send any message to bot
Visit: https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
Find "chat":{"id": YOUR_CHAT_ID} in response

3. Get API Keys

Etherscan API: https://etherscan.io/apis
The Graph API: https://thegraph.com/studio/apikeys/

4. Create `.env` file with your API keys:
```
TELEGRAM_BOT_TOKEN="your_bot_token"
TELEGRAM_CHAT_ID="your_chat_id"
ETHERSCAN_API_KEY="your_etherscan_key"
GRAPH_API_KEY="your_graph_key"
```

5. Run monitor.py
```
python monitor.py
```