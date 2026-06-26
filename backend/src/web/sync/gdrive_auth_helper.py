import sys
import json
from google_auth_oauthlib.flow import InstalledAppFlow

def main():
    try:
        # Read payload from stdin
        input_data = json.loads(sys.stdin.read())
        client_secrets_data = input_data["client_secrets_data"]
        token_file = input_data["token_file"]
        scopes = input_data["scopes"]

        # Initialize the InstalledAppFlow
        flow = InstalledAppFlow.from_client_config(
            client_secrets_data, scopes=scopes
        )
        
        # Run the local server flow.
        # This will launch the default browser and listen on a local port.
        creds = flow.run_local_server(
            port=0,
            authorization_prompt_message="Please visit this URL to authorize: {url}"
        )

        # Save the token to the token file
        if token_file and creds:
            import os
            token_dir = os.path.dirname(token_file)
            if token_dir:
                os.makedirs(token_dir, exist_ok=True)
            with open(token_file, "w") as f:
                f.write(creds.to_json())
        
        print("SUCCESS")
        sys.exit(0)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
