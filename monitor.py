import os
import time
from datetime import datetime, timedelta
from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport
import requests

ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")
GRAPH_API_KEY = os.getenv("GRAPH_API_KEY")

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
        print(f"[TVL Check] Current TVL: ${current_tvl:,.2f}")
        return current_tvl

    except Exception as e:
        print(f"Error checking TVL: {e}")
        return None

def main():
    # Set up the client
    transport = RequestsHTTPTransport(
        url=f'https://gateway.thegraph.com/api/{GRAPH_API_KEY}/subgraphs/id/5zvR82QoaXYFyDEKLZ9t6v9adgnptxYpKpSbxtgVENFV',
        headers={'Content-Type': 'application/json'}
    )
    client = Client(transport=transport, fetch_schema_from_transport=False)

    # Run the functions and display the results
    gas_status = get_gas_status()
    if gas_status:
        print(f"Gas Status: {gas_status}")

    tvl = check_tvl(client)
    if tvl:
        print(f"TVL: {tvl}")

if __name__ == "__main__":
    main()
