"""Show authentication status without displaying credentials."""
import json
from tira.rest_api_client import Client

client = Client()
configured = client.api_key != 'no-api-key'
valid = bool(client.api_key_is_valid()) if configured else False
print(json.dumps({'login_configured': configured, 'authenticated': valid}))
