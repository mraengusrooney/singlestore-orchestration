import requests
import configparser
import os
import sys
import time

def make_api_request(method, endpoint, api_token):
    """
    Helper function to standardize GET and DELETE requests to the SingleStore API.
    """
    url = f"https://api.singlestore.com/v1/{endpoint}"
    headers = {
        "Authorization": f"Bearer {api_token}"
    }
    
    try:
        if method.upper() == 'GET':
            response = requests.get(url, headers=headers)
        elif method.upper() == 'DELETE':
            response = requests.delete(url, headers=headers)
        else:
            raise ValueError("Unsupported HTTP method")
            
        # If we try to delete something that is already gone, skip gracefully
        if response.status_code == 404 and method.upper() == 'DELETE':
            return {}
            
        response.raise_for_status()
        
        # 204 No Content means success for DELETE, but there is no JSON payload
        if response.status_code == 204:
            return {}
            
        try:
            return response.json()
        except ValueError:
            return {}
            
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

def wait_for_deletion(api_token, endpoint_base, entity_id):
    """
    Polls the API until the entity is completely gone (404) or state becomes TERMINATED.
    """
    print(f"   Waiting for cloud hardware deprovisioning...")
    while True:
        try:
            url = f"https://api.singlestore.com/v1/{endpoint_base}/{entity_id}"
            headers = {"Authorization": f"Bearer {api_token}"}
            response = requests.get(url, headers=headers)
            
            # 404 Not Found means the resource is completely deleted
            if response.status_code == 404:
                print("   Success! Resource successfully removed.\n")
                return
                
            response.raise_for_status()
            data = response.json()
            state = data.get('state')
            
            if state == "TERMINATED":
                print("   Success! Resource state is TERMINATED.\n")
                return
                
            print(f"   Status is currently {state if state else 'Pending'}. Sleeping for 15 seconds...")
            time.sleep(15)
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                print("   Success! Resource successfully removed.\n")
                return
            print(f"   [!] Error checking status: {e}\n")
            return
        except Exception as e:
            print(f"   [!] Error checking status: {e}\n")
            return

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
        WSG_NAME = config.get('SingleStore', 'workspace_group_name')
        WORKSPACE_NAME = config.get('SingleStore', 'workspace_name')
        
        print("Starting SingleStore infrastructure TEARDOWN...\n" + "-"*50)
        
        # We need the IDs first to delete them
        project_id = get_entity_id_by_name(API_TOKEN, 'projects', PROJECT_NAME, 'projectID')
        wsg_id = get_entity_id_by_name(API_TOKEN, 'workspaceGroups', WSG_NAME, 'workspaceGroupID')
        
        # 1. Delete Workspace
        print(f"1. Checking for Workspace: '{WORKSPACE_NAME}'...")
        if wsg_id:
            # Requires workspaceGroupID query param to find the workspace
            endpoint_with_query = f"workspaces?workspaceGroupID={wsg_id}"
            workspace_id = get_entity_id_by_name(API_TOKEN, endpoint_with_query, WORKSPACE_NAME, 'workspaceID')
            
            if workspace_id:
                print(f"   Initiating deletion of Workspace (ID: {workspace_id})...")
                make_api_request('DELETE', f'workspaces/{workspace_id}', API_TOKEN)
                wait_for_deletion(API_TOKEN, 'workspaces', workspace_id)
            else:
                print("   [Skip] Workspace not found or already deleted.\n")
        else:
            print("   [Skip] Parent Workspace Group not found. Workspace is inherently deleted.\n")

        # 2. Delete Workspace Group (This physically drops your database)
        print(f"2. Checking for Workspace Group: '{WSG_NAME}'...")
        if wsg_id:
            print("   Initiating deletion of Workspace Group (This will permanently drop the attached Database)...")
            make_api_request('DELETE', f'workspaceGroups/{wsg_id}', API_TOKEN)
            wait_for_deletion(API_TOKEN, 'workspaceGroups', wsg_id)
        else:
            print("   [Skip] Workspace Group not found or already deleted.\n")

        # 3. Delete Project
        print(f"3. Checking for Project: '{PROJECT_NAME}'...")
        if project_id:
            print(f"   Initiating deletion of Project (ID: {project_id})...")
            make_api_request('DELETE', f'projects/{project_id}', API_TOKEN)
            wait_for_deletion(API_TOKEN, 'projects', project_id)
        else:
            print("   [Skip] Project not found or already deleted.\n")

        print("-" * 50 + "\nTeardown sequence complete! Environment is clean.")

    except Exception as e:
        print(f"\n[!] Teardown Error: {e}")
