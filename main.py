pip install requests

import requests
import configparser
import os

def create_workspace(api_token, workspace_group_id, workspace_name, size):
    """
    Spins up a new workspace in SingleStore Helios using the REST API.
    """
    url = "https://api.singlestore.com/v1/workspaces"
    
    # Configure your workspace settings using the passed variables
    payload = {
        "name": workspace_name,
        "size": size,
        "workspaceGroupID": workspace_group_id,
        "enableKai": False # Optional: Set to True to enable the SingleStore Kai (MongoDB) API
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_token}"
    }
    
    try:
        print(f"Initiating creation of workspace: '{workspace_name}'...")
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status() 
        
        workspace_data = response.json()
        print("Success! Workspace creation has started.")
        print(f"Workspace ID: {workspace_data.get('workspaceID')}")
        print(f"Current State: {workspace_data.get('state')}")
        
        return workspace_data
        
    except requests.exceptions.RequestException as e:
        print(f"Error creating workspace: {e}")
        if e.response is not None:
            print(f"API Response: {e.response.text}")
        return None

def load_config(config_file='config.ini'):
    """
    Safely loads configuration from the specified INI file.
    """
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Configuration file '{config_file}' not found in the current directory.")
        
    config = configparser.ConfigParser()
    config.read(config_file)
    return config

if __name__ == "__main__":
    try:
        # 1. Load the configuration file
        config = load_config('config.ini')
        
        # 2. Extract the variables from the [SingleStore] section
        API_TOKEN = config.get('SingleStore', 'api_token')
        WORKSPACE_GROUP_ID = config.get('SingleStore', 'workspace_group_id')
        WORKSPACE_NAME = config.get('SingleStore', 'workspace_name')
        WORKSPACE_SIZE = config.get('SingleStore', 'size')
        
        # 3. Execute the API call with the config values
        create_workspace(
            api_token=API_TOKEN,
            workspace_group_id=WORKSPACE_GROUP_ID,
            workspace_name=WORKSPACE_NAME,
            size=WORKSPACE_SIZE
        )
        
    except FileNotFoundError as e:
        print(f"Setup Error: {e}")
        print("Please ensure you have created a 'config.ini' file.")
    except configparser.NoSectionError as e:
        print(f"Config Error: Missing section in config file. {e}")
    except configparser.NoOptionError as e:
        print(f"Config Error: Missing configuration option. {e}")
