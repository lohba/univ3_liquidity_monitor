import os
from dotenv import load_dotenv
import time
from datetime import datetime, timedelta
from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport
import requests
from telegram import Bot
import asyncio

load_dotenv()

# Constants
WSTETH_ETH_POOL = "0x109830a1aaad605bbf02a9dfa7b0b92ec2fb7daa"
CHECK_INTERVAL = 30

# Get keys from env variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")
GRAPH_API_KEY = os.getenv("GRAPH_API_KEY")

# Mock position configuration priced in wsteth based on current mid-price
MOCK_POSITION = {
   'lower_price': 0.83832102,  # Fixed lower bound
   'upper_price': 0.84252314,  # Fixed upper bound
}

# Define thresholds for alerts
TOLERANCE_MARGIN = 0.0005  # Tolerance for minor price fluctuations
SIGNIFICANT_RATIO_CHANGE = 0.003  # 0.3% ratio change threshold
SIGNIFICANT_TVL_CHANGE = 0.05  # 5% TVL change threshold

# Track last values to avoid redundant alerts
last_price = None
last_volume = None
last_ratio = None
last_tvl = None

async def send_telegram_alert(message: str):
   """Send alert to Telegram"""
   try:
       bot = Bot(token=TELEGRAM_BOT_TOKEN)
       await bot.send_message(
           chat_id=TELEGRAM_CHAT_ID,
           text=message,
           parse_mode='HTML'
       )
       print(f"Telegram alert sent: {message}")  # Debug log
   except Exception as e:
       print(f"Failed to send Telegram alert: {e}")
async def test_telegram():
    """Test Telegram connection"""
    test_msg = "🔔 Testing Telegram connection..."
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=test_msg,
            parse_mode='HTML'
        )
        print("Telegram test successful!")
    except Exception as e:
        print(f"Telegram test failed: {e}")


print("Testing Telegram connection...")
asyncio.run(test_telegram())

def send_alert(message: str):
   """Synchronous wrapper for sending Telegram alerts"""
   asyncio.run(send_telegram_alert(message))

def get_gas_status():
   """Check if current gas price is lower or higher than the 3-day average."""
   try:
       # Get current gas price
       response = requests.get(
           'https://api.etherscan.io/api',
           params={
               'module': 'gastracker',
               'action': 'gasoracle',
               'apikey': ETHERSCAN_API_KEY
           }
       )
       current_gas = float(response.json()['result']['SafeGasPrice'])
       
       # Get the last 3 days of gas data
       end_date = datetime.now().strftime('%Y-%m-%d')
       start_date = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
       response = requests.get(
           'https://api.etherscan.io/api',
           params={
               'module': 'stats',
               'action': 'dailygasoracle',
               'startdate': start_date,
               'enddate': end_date,
               'apikey': ETHERSCAN_API_KEY
           }
       )
       
       recent_gas = [float(day['SafeGasPrice']) for day in response.json()['result']]
       avg_gas = sum(recent_gas) / len(recent_gas)
       
       status = "CHEAP" if current_gas < avg_gas else "EXPENSIVE"
       
       return {
           'price': current_gas,
           'avg_gas': avg_gas,
           'status': status
       }
   except Exception as e:
       print(f"Error checking gas: {e}")
       return None

def check_tvl(client):
   """Monitor TVL changes in the pool"""
   global last_tvl
   query = gql('''
   {
       pool(id: "0x109830a1aaad605bbf02a9dfa7b0b92ec2fb7daa") {
           totalValueLockedUSD
       }
   }
   ''')

   try:
       result = client.execute(query)
       current_tvl = float(result['pool']['totalValueLockedUSD'])
       #print(f"[TVL Check] Current TVL: ${current_tvl:,.2f}")

       if last_tvl is not None:
           tvl_change = ((current_tvl - last_tvl) / last_tvl) * 100
           #print(f"[TVL Check] Change: {tvl_change:.2f}%")
           
           if abs(tvl_change) >= SIGNIFICANT_TVL_CHANGE * 100:
               alert_msg = (
                   "💰 <b>Significant TVL Change</b>\n"
                   f"Change: {tvl_change:.2f}%\n"
                   f"Current TVL: ${current_tvl:,.2f}\n"
                   f"Previous TVL: ${last_tvl:,.2f}"
               )
               send_alert(alert_msg)

       last_tvl = current_tvl
       return current_tvl

   except Exception as e:
       print(f"Error checking TVL: {e}")
       return None

def check_position(client):
   """Check position status and alert on significant changes"""
   global last_price, last_volume, last_ratio
   query = gql('''
   {
       pool(id: "0x109830a1aaad605bbf02a9dfa7b0b92ec2fb7daa") {
           token0Price
           volumeUSD
           poolDayData(first: 2, orderBy: date, orderDirection: desc) {
               volumeUSD
           }
       }
   }
   ''')

   alerts = []
   try:
       # Fetch pool data
       result = client.execute(query)
       current_price = float(result['pool']['token0Price'])

       # Debug print for current price
       print(f"[Price Check] Current Price: {current_price} ETH")

       # Check if the price is within the set mock range with tolerance
       in_range = (MOCK_POSITION['lower_price'] * (1 - TOLERANCE_MARGIN) <= current_price <= MOCK_POSITION['upper_price'] * (1 + TOLERANCE_MARGIN))
       
       # Add early warning for approaching bounds (1% buffer)
       APPROACH_BUFFER = 0.01  # 1% buffer zone
       lower_approach = MOCK_POSITION['lower_price'] * (1 + APPROACH_BUFFER)
       upper_approach = MOCK_POSITION['upper_price'] * (1 - APPROACH_BUFFER)
       
       # Check if price is approaching bounds while still in range
       if in_range:
           if current_price <= lower_approach:
               alert_msg = (
                   "⚠️ <b>Price Approaching Lower Bound</b>\n"
                   f"Current: {current_price:.6f}\n"
                   f"Lower Bound: {MOCK_POSITION['lower_price']:.6f}\n"
                   "Consider preparing for rebalance"
               )
               send_alert(alert_msg)
           elif current_price >= upper_approach:
               alert_msg = (
                   "⚠️ <b>Price Approaching Upper Bound</b>\n"
                   f"Current: {current_price:.6f}\n"
                   f"Upper Bound: {MOCK_POSITION['upper_price']:.6f}\n"
                   "Consider preparing for rebalance"
               )
               send_alert(alert_msg)

       # Price alert if out of range and significant change from last alert
       if last_price is None or abs(current_price - last_price) / last_price >= TOLERANCE_MARGIN:
           if not in_range:
               if current_price < MOCK_POSITION['lower_price']:
                   alert_msg = (
                       "🚨 <b>CRITICAL: Position Below Range</b>\n"
                       f"Current Price: {current_price:.6f}\n"
                       f"Lower Bound: {MOCK_POSITION['lower_price']:.6f}\n"
                       "Not earning fees! Action required."
                   )
                   send_alert(alert_msg)
               else:
                   alert_msg = (
                       "🚨 <b>CRITICAL: Position Above Range</b>\n"
                       f"Current Price: {current_price:.6f}\n"
                       f"Upper Bound: {MOCK_POSITION['upper_price']:.6f}\n"
                       "Not earning fees! Action required."
                   )
                   send_alert(alert_msg)
               print(f"[Alert] Price out of range! Last Alerted Price: {last_price}, New Alert Price: {current_price}")
               last_price = current_price

       # Real-time volume change check
       current_volume = float(result['pool']['poolDayData'][0]['volumeUSD'])
       if last_volume is not None:
           volume_change = ((current_volume - last_volume) / last_volume) * 100
           print(f"[Volume Check] Current Volume: {current_volume} USD, Previous Volume: {last_volume} USD, Change: {volume_change:.2f}%")
           if abs(volume_change) > 10:
               alert_msg = (
                   "📊 <b>Significant Volume Change</b>\n"
                   f"Change: {volume_change:.1f}%\n"
                   f"Current Volume: ${current_volume:,.2f}\n"
                   f"Previous Volume: ${last_volume:,.2f}"
               )
               send_alert(alert_msg)
       
       last_volume = current_volume

       # Ratio change check
       if last_ratio is not None:
           ratio_change = abs(current_price - last_ratio) / last_ratio
           if ratio_change >= SIGNIFICANT_RATIO_CHANGE:
               alert_msg = (
                   "📈 <b>Significant Ratio Change</b>\n"
                   f"Change: {ratio_change * 100:.1f}%\n"
                   f"Previous: {last_ratio:.6f}\n"
                   f"Current: {current_price:.6f}"
               )
               send_alert(alert_msg)
               print(f"[Alert] Significant ratio change detected! Previous: {last_ratio}, Current: {current_price}")
       
       last_ratio = current_price

       # Gas status check for rebalancing
       gas_info = None
       if not in_range:
           gas_info = get_gas_status()
           if gas_info and gas_info['status'] == "CHEAP":
               alert_msg = (
                   "⛽ <b>Favorable Gas Conditions</b>\n"
                   f"Current Gas: {gas_info['price']} GWEI\n"
                   f"3-day Average: {gas_info['avg_gas']:.1f} GWEI\n"
                   "Good time to rebalance position"
               )
               send_alert(alert_msg)

       return {
           'current_price': current_price,
           'in_range': in_range,
           'alerts': alerts
       }

   except Exception as e:
       error_msg = f"Error checking position: {e}"
       print(error_msg)
       send_alert(f"🔥 <b>Error</b>\n{error_msg}")
       return None

def main():
   print("Starting continuous monitoring...")
   print(f"Monitoring position with range: {MOCK_POSITION['lower_price']:.6f} - {MOCK_POSITION['upper_price']:.6f}")
   
   # Set up the client
   transport = RequestsHTTPTransport(
       url=f'https://gateway.thegraph.com/api/{os.getenv("GRAPH_API_KEY")}/subgraphs/id/5zvR82QoaXYFyDEKLZ9t6v9adgnptxYpKpSbxtgVENFV',
       headers={'Content-Type': 'application/json'}
   )
   client = Client(transport=transport, fetch_schema_from_transport=False)

   # Send initial startup message
   startup_msg = (
       "🚀 <b>Position Monitor Started</b>\n"
       f"Monitoring Range: {MOCK_POSITION['lower_price']:.6f} - {MOCK_POSITION['upper_price']:.6f}\n"
       f"Check Interval: {CHECK_INTERVAL} seconds"
   )
   send_alert(startup_msg)

   while True:
       try:
           status = check_position(client)
           tvl = check_tvl(client)
           time.sleep(CHECK_INTERVAL)
       except KeyboardInterrupt:
           shutdown_msg = "🛑 Monitor stopped by user"
           send_alert(shutdown_msg)
           print(shutdown_msg)
           break
       except Exception as e:
           error_msg = f"🔥 Monitor error: {str(e)}"
           send_alert(error_msg)
           print(error_msg)
           time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
   main()