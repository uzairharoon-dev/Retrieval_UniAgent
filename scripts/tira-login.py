"""Prompt locally for a TIRA key without putting it in command arguments or logs."""
import getpass
import sys

from tira.rest_api_client import Client


def main():
    token = getpass.getpass('TIRA API key (hidden): ').strip()
    if not token:
        sys.exit('No API key entered.')
    client = Client(api_key=token)
    # Client.login prints the token when validation fails; avoid that code path.
    try:
        valid = client.api_key_is_valid()
    except Exception:
        valid = False
    if not valid:
        sys.exit('TIRA login failed. Check the API key and internet connection.')
    client.update_settings('api_key', token)
    client.update_settings('api_user_name', client.api_user_name)
    print('TIRA login saved locally. The key was not printed.')


if __name__ == '__main__':
    main()
