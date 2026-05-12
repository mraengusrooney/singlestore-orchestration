print( "first run pip install requests singlestoredb" ) 

import requests
import configparser
import os
import sys
import time
import singlestoredb as s2

def make_api_request(method, endpoint, api_token, payload=None):
    """
    Helper function to standardize requests to the SingleStore API.
    """
    url = f"https://api.singlestore.com/v1/{endpoint}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_token}"
    }
    
    try:
        if method.upper() == 'POST':
            response = requests.post(url, headers=headers, json=payload)
        elif method.upper() == 'GET':
            response = requests.get(url, headers=headers)
        else:
            raise ValueError("Unsupported HTTP method")
            
        response.raise_for_status()
        return response.json()
        
    except requests.exceptions.RequestException as e:
        print(f"\n[!] API Error during {method} to /{endpoint}: {e}")
        if e.response is not None:
            print(f"API Response: {e.response.text}")
        sys.exit(1)

def get_entity_id_by_name(api_token, endpoint, name, id_key):
    """
    Queries the API for existing entities and returns the ID if the name matches.
    """
    data = make_api_request('GET', endpoint, api_token)
    
    items = []
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        for val in data.values():
            if isinstance(val, list):
                items = val
                break

    for item in items:
        if item.get('name') == name:
            return item.get(id_key)
            
    return None

def check_and_create_project(api_token, project_name, edition):
    print(f"1. Checking for Project: '{project_name}'...")
    project_id = get_entity_id_by_name(api_token, 'projects', project_name, 'projectID')
    
    if project_id:
        print(f"   [Skip] Project already exists (ID: {project_id})\n")
        return project_id
        
    print(f"   Initiating creation of Project: '{project_name}' (Edition: {edition})...")
    payload = {"name": project_name, "edition": edition}
    data = make_api_request('POST', 'projects', api_token, payload)
    project_id = data.get('projectID')
    print(f"   Success! Project created (ID: {project_id})\n")
    return project_id

def check_and_create_wsg(api_token, wsg_name, region_id, admin_password, project_id, firewall_ranges):
    print(f"2. Checking for Workspace Group: '{wsg_name}'...")
    wsg_id = get_entity_id_by_name(api_token, 'workspaceGroups', wsg_name, 'workspaceGroupID')
    
    if wsg_id:
        print(f"   [Skip] Workspace Group already exists (ID: {wsg_id})\n")
        return wsg_id
        
    print(f"   Initiating creation of Workspace Group: '{wsg_name}'...")
    payload = {
        "name": wsg_name,
        "regionID": region_id,
        "adminPassword": admin_password,
        "projectID": project_id,
        "firewallRanges": firewall_ranges
    }
    data = make_api_request('POST', 'workspaceGroups', api_token, payload)
    wsg_id = data.get('workspaceGroupID')
    print(f"   Success! Workspace Group created (ID: {wsg_id})\n")
    return wsg_id

def check_and_create_workspace(api_token, workspace_name, wsg_id, size):
    print(f"3. Checking for Workspace: '{workspace_name}'...")
    
    # FIX: Added the workspaceGroupID as a required query parameter to the GET request
    endpoint_with_query = f"workspaces?workspaceGroupID={wsg_id}"
    workspace_id = get_entity_id_by_name(api_token, endpoint_with_query, workspace_name, 'workspaceID')
    
    if workspace_id:
        print(f"   [Skip] Workspace already exists (ID: {workspace_id})\n")
        return workspace_id
        
    print(f"   Initiating creation of Workspace: '{workspace_name}'...")
    payload = {
        "name": workspace_name,
        "workspaceGroupID": wsg_id,
        "size": size,
        "enableKai": False 
    }
    data = make_api_request('POST', 'workspaces', api_token, payload)
    workspace_id = data.get('workspaceID')
    state = data.get('state')
    
    print("   Success! Workspace deployment has started.")
    print(f"   Workspace ID: {workspace_id}")
    print(f"   Current State: {state}\n")
    return workspace_id

def wait_for_workspace(api_token, workspace_id):
    print("4. Checking Workspace state...")
    while True:
        data = make_api_request('GET', f'workspaces/{workspace_id}', api_token)
        state = data.get('state')
        
        if state == "ACTIVE":
            endpoint = data.get('endpoint')
            print(f"   Success! Workspace is ACTIVE.")
            print(f"   Endpoint: {endpoint}\n")
            return endpoint
        elif state in ["FAILED", "TERMINATED"]:
            print(f"   [!] Workspace creation ended in state: {state}")
            sys.exit(1)
            
        print(f"   Status is currently {state}. Sleeping for 30 seconds...")
        time.sleep(30)

def check_and_create_database(endpoint, admin_password, db_name):
    print(f"5. Checking for Database: '{db_name}'...")
    
    try:
        # FIX: Connect using explicit parameters instead of a URL string 
        # This prevents special characters in the password from breaking the connection
        conn = s2.connect(
            host=endpoint,
            port=3306,
            user="admin",
            password=admin_password
        )
        with conn.cursor() as cursor:
            cursor.execute("SHOW DATABASES;")
            existing_dbs = [row[0] for row in cursor.fetchall()]
            
            if db_name in existing_dbs:
                print(f"   [Skip] Database '{db_name}' already exists.\n")
            else:
                print(f"   Initiating creation of Database: '{db_name}'...")
                cursor.execute(f"CREATE DATABASE {db_name};")
                print(f"   Success! Database '{db_name}' has been created.\n")
    except Exception as e:
        print(f"\n[!] SQL Error during Database Check/Creation: {e}")
        sys.exit(1)


def load_config(config_file='config.ini'):
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Configuration file '{config_file}' not found.")
    config = configparser.ConfigParser()
    config.read(config_file)
    return config

if __name__ == "__main__":
    try:
        # Load environment variables
        config = load_config('config.ini')
        
        API_TOKEN = config.get('SingleStore', 'api_token')
        PROJECT_NAME = config.get('SingleStore', 'project_name')
        EDITION = config.get('SingleStore', 'edition', fallback='STANDARD')
        
        WSG_NAME = config.get('SingleStore', 'workspace_group_name')
        REGION_ID = config.get('SingleStore', 'region_id')
        ADMIN_PASSWORD = config.get('SingleStore', 'admin_password')
        
        # Parse firewall ranges into a list, defaulting to allow-all if not present
        raw_firewall = config.get('SingleStore', 'firewall_ranges', fallback='0.0.0.0/0')
        FIREWALL_RANGES = [ip.strip() for ip in raw_firewall.split(',')]
        
        WORKSPACE_NAME = config.get('SingleStore', 'workspace_name')
        WORKSPACE_SIZE = config.get('SingleStore', 'size')
        DATABASE_NAME = config.get('SingleStore', 'database_name')
        
        print("Starting SingleStore infrastructure deployment...\n" + "-"*50)
        
        # Step 1: Check/Create Project
        project_id = check_and_create_project(API_TOKEN, PROJECT_NAME, EDITION)
        
        # Step 2: Check/Create Workspace Group
        wsg_id = check_and_create_wsg(
            API_TOKEN, WSG_NAME, REGION_ID, ADMIN_PASSWORD, project_id, FIREWALL_RANGES
        )
        
        # Step 3: Check/Create Workspace
        workspace_id = check_and_create_workspace(
            API_TOKEN, WORKSPACE_NAME, wsg_id, WORKSPACE_SIZE
        )
        
        # Step 4: Wait for Cloud Hardware Provisioning & Get Endpoint
        endpoint = wait_for_workspace(API_TOKEN, workspace_id)
        
        # Step 5: Check/Create the Database via SQL
        check_and_create_database(endpoint, ADMIN_PASSWORD, DATABASE_NAME)
        
        print("-" * 50 + "\nDeployment sequence complete!")

    except Exception as e:
        print(f"\n[!] Setup Error: {e}")
