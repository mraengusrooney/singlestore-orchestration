import requests
import configparser

def load_api_key():
    config = configparser.ConfigParser()
    config.read('config.ini')
    return config.get('SingleStore', 'api_token')

def list_regions():
    api_token = load_api_key()
    url = "https://api.singlestore.com/v1/regions"
    headers = {
        "Authorization": f"Bearer {api_token}"
    }
    
    print("Fetching available SingleStore regions...\n")
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    regions = response.json()
    
    # Print a formatted table of the regions
    print(f"{'REGION ID (UUID)':<40} | {'PROVIDER':<10} | {'REGION NAME'}")
    print("-" * 80)
    
    for r in regions:
        region_id = r.get('regionID')
        provider = r.get('provider')
        name = r.get('name')
        print(f"{region_id:<40} | {provider:<10} | {name}")

if __name__ == "__main__":
    list_regions()
