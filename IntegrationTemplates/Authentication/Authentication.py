import demistomock as demisto
from CommonServerPython import *
from CommonServerUserPython import *

''' IMPORTS '''
from typing import cast, Any, Dict, Tuple, List, AnyStr
from xml.etree import ElementTree

import requests
import urllib3

# Disable insecure warnings
urllib3.disable_warnings()

''' GLOBALS/PARAMS '''
INTEGRATION_NAME: str = 'Authentication Integration'
# lowercase with `-` dividers
INTEGRATION_NAME_COMMAND: str = 'authentication'
# No dividers
INTEGRATION_NAME_CONTEXT: str = 'AuthenticationIntegration'


class Client:
    def __init__(self, server: str, use_ssl: bool):
        self.server: str = server.rstrip(chars='/')
        self.use_ssl: bool = use_ssl
        self.base_url: str = self.server + '/api/v2.0/'

    def _http_request(self, method: str, url_suffix: str, full_url: str = None, headers: Dict = None,
                      auth: Tuple = None, params: Dict = None, data: Dict = None, files: Dict = None,
                      timeout: float = 10, resp_type: str = 'json') -> Any:
        """A wrapper for requests lib to send our requests and handle requests
        and responses better

        Args:
            method:
                HTTP method, e.g. 'GET', 'POST' ... etc.
            url_suffix:
                API endpoint.
            full_url:
                Bypasses the use of BASE_URL + url_suffix. Useful if there is a need to
                make a request to an address outside of the scope of the integration
                API.
            headers:
                Headers to send in the request.
            auth:
                Auth tuple to enable Basic/Digest/Custom HTTP Auth.
            params:
                URL parameters.
            data:
                Data to be sent in a 'POST' request.
            files:
                File data to be sent in a 'POST' request.
            timeout:
                The amount of time in seconds a Request will wait for a client to
                establish a connection to a remote machine.
            resp_type:
                Determines what to return from having made the HTTP request. The default
                is 'json'. Other options are 'text', 'content' or 'response' if the user
                would like the full response object returned.

        Returns:
                Response JSON from having made the request.
        """
        try:
            address = full_url if full_url else self.base_url + url_suffix
            res = requests.request(
                method,
                address,
                verify=self.use_ssl,
                params=params,
                data=data,
                files=files,
                headers=headers,
                auth=auth,
                timeout=timeout
            )

            # Handle error responses gracefully
            if res.status_code not in (200, 201):
                err_msg = f'Error in {INTEGRATION_NAME} API call [{res.status_code}] - {res.reason}'
                try:
                    # Try to parse json error response
                    res_json = res.json()
                    message = res_json.get('message')
                    return_error(message)
                except json.decoder.JSONDecodeError:
                    if res.status_code in (400, 401, 501):
                        # Try to parse xml error response
                        resp_xml = ElementTree.fromstring(res.content)
                        codes = [child.text for child in resp_xml.iter() if child.tag == 'CODE']
                        messages = [child.text for child in resp_xml.iter() if child.tag == 'MESSAGE']
                        err_msg += ''.join([f'\n{code}: {msg}' for code, msg in zip(codes, messages)])
                    return_error(err_msg)

            resp_type = resp_type.casefold()
            try:
                if resp_type == 'json':
                    return res.json()
                elif resp_type == 'text':
                    return res.text
                elif resp_type == 'content':
                    return res.content
                else:
                    return res
            except json.decoder.JSONDecodeError:
                return_error(f'Failed to parse json object from response: {res.content}')

        except requests.exceptions.ConnectTimeout:
            err_msg = 'Connection Timeout Error - potential reasons may be that the Server URL parameter' \
                      ' is incorrect or that the Server is not accessible from your host.'
            return_error(err_msg)
        except requests.exceptions.SSLError:
            err_msg = 'SSL Certificate Verification Failed - try selecting \'Trust any certificate\' in' \
                      ' the integration configuration.'
            return_error(err_msg)
        except requests.exceptions.ProxyError:
            err_msg = 'Proxy Error - if \'Use system proxy\' in the integration configuration has been' \
                      ' selected, try deselecting it.'
            return_error(err_msg)
        except requests.exceptions.ConnectionError as e:
            # Get originating Exception in Exception chain
            while '__context__' in dir(e) and e.__context__:
                e = cast(Any, e.__context__)

            error_class = str(e.__class__)
            err_type = '<' + error_class[error_class.find('\'') + 1: error_class.rfind('\'')] + '>'
            err_msg = f'\nError Type: {err_type}\nError Number: [{e.errno}]\nMessage: {e.strerror}\n' \
                f'Verify that the server URL parameter' \
                f' is correct and that you have access to the server from your host.'
            return_error(err_msg)

    def test_module(self) -> bool:
        """Performs basic get request to get item samples

        Returns:
            True if request succeeded
        """
        self._http_request('GET', 'version')
        return True

    def fetch_credentials(self) -> Dict:
        """Gets all credentials from API.

        Returns:
            credentials
        """
        suffix = 'credentials'
        return self._http_request('GET', suffix)

    def lock_account_request(self, account: AnyStr) -> Dict:
        """Gets events from given IDS

        Args:
            account: account to lock

        Returns:
            locked account
        """
        # The service endpoint to request from
        suffix: str = 'account/lock'
        # Dictionary of params for the request
        params = {
            'account': account
        }
        return self._http_request('POST', suffix, params=params)

    def unlock_account_request(self, account: AnyStr):
        """Gets events from given IDS

        Args:
            account: account to unlock

        Returns:
            response json
        """
        # The service endpoint to request from
        suffix: str = 'account/unlock'
        # Dictionary of params for the request
        params = {
            'account': account
        }
        # Send a request using our http_request wrapper
        return self._http_request('POST', suffix, params=params)

    def reset_account_request(self, account: str):
        """Gets events from given IDS

        Args:
            account: account to unlock

        Returns:
            response json
        """
        # The service endpoint to request from
        suffix: str = 'account/reset'
        # Dictionary of params for the request
        params = {
            'account': account
        }
        # Send a request using our http_request wrapper
        return self._http_request('POST', suffix, params=params)

    def unlock_vault_request(self, vault_to_lock) -> Dict:
        """Unlocks vault

        Args:
            vault_to_lock: vault to lock

        Returns:
            locked state
        """
        suffix = 'vault/unlock'
        params = {'vault_id': vault_to_lock}
        return self._http_request('POST', suffix, params=params)

    def lock_vault_request(self, vault_to_lock: AnyStr) -> Dict:
        """Locks vault

        Args:
            vault_to_lock: vault to lock

        Returns:
            locked state
        """
        suffix = 'vault/lock'
        params = {'vault_id': vault_to_lock}
        return self._http_request('POST', suffix, params=params)


''' HELPER FUNCTIONS '''

''' COMMANDS '''


def test_module(client: Client):
    """
    Performs basic get request to get item samples
    """
    if client.test_module():
        demisto.results('ok')


def fetch_credentials(client: Client):
    """Uses to fetch credentials into Demisto
    Documentation: https://github.com/demisto/content/tree/master/docs/fetching_credentials
    """
    # Get credentials from api
    raw_response: Dict = client.fetch_credentials()
    raw_credentials: List[Dict] = raw_response.get('credentials', [])
    # Creates credentials entry
    credentials = [{
        'user': credential.get('username'),
        'password': credential.get('password'),
        'name': credential.get('name')
    } for credential in raw_credentials]
    demisto.credentials(credentials)


def lock_account(client: Client):
    """
    Gets details about a raw_response using IDs or some other filters
    """
    # Initialize main vars
    context: Dict = dict()
    # Get arguments from user
    account_to_lock: str = demisto.args().get('account_id', '')
    # Make request and get raw response
    raw_response: Dict = client.lock_account_request(account_to_lock)
    # Parse response into context & content entries
    if raw_response.get('locked_account') == account_to_lock:
        title: str = f'{INTEGRATION_NAME} - Account `{account_to_lock}` has been locked.'
        context_entry = {
            'IsLocked': True,
            'ID': account_to_lock
        }
        context[f'{INTEGRATION_NAME_CONTEXT}.Account(val.ID && val.ID === obj.ID)'] = context_entry
        # Creating human readable for War room
        human_readable: str = tableToMarkdown(title, context_entry)
        # Return data to Demisto
        return_outputs(human_readable, context, raw_response)
    else:
        return_error(f'{INTEGRATION_NAME} - Could not lock account `{account_to_lock}`')


def unlock_account(client: Client):
    """
    Gets details about a raw_response using IDs or some other filters
    """
    # Initialize main vars
    context: Dict = dict()
    # Get arguments from user
    account_to_unlock: str = demisto.args().get('account_id', '')
    # Make request and get raw response
    unlocked_account: str = client.unlock_account_request(account_to_unlock)
    # Parse response into context & content entries
    if unlocked_account == account_to_unlock:
        title: str = f'{INTEGRATION_NAME} - Account `{unlocked_account}` has been unlocked.'
        context_entry = {
            'IsLocked': False,
            'ID': account_to_unlock
        }

        context[f'{INTEGRATION_NAME_CONTEXT}.Account(val.ID && val.ID === obj.ID)'] = context_entry
        # Creating human readable for War room
        human_readable: str = tableToMarkdown(title, context_entry)
        # Return data to Demisto
        return_outputs(human_readable, context)
    else:
        return_error(f'{INTEGRATION_NAME} - Could not unlock account `{account_to_unlock}`')


def lock_vault(client: Client):
    vault_to_lock: str = demisto.args().get('vault', '')
    raw_response = client.lock_vault_request(vault_to_lock)
    if 'is_locked' in raw_response and raw_response['is_locked'] is True:
        title: str = f'{INTEGRATION_NAME} - Vault {vault_to_lock} has been locked'
        context_entry = {
            'ID': vault_to_lock,
            'IsLocked': True
        }
        context = {
            f'{INTEGRATION_NAME_CONTEXT}.Vault(val.ID && val.ID === obj.ID)': context_entry
        }
        human_readable = tableToMarkdown(title, context_entry)
        return_outputs(human_readable, context, raw_response)
    else:
        return_error(f'{INTEGRATION_NAME} - Could not lock vault ID: {vault_to_lock}')


def unlock_vault(client: Client):
    vault_to_lock: str = demisto.args().get('vault', '')
    raw_response = client.unlock_vault_request(vault_to_lock)
    if 'is_locked' in raw_response and raw_response['is_locked'] is True:
        title: str = f'{INTEGRATION_NAME} - Vault {vault_to_lock} has been unlocked'
        context_entry = {
            'ID': vault_to_lock,
            'IsLocked': True
        }
        context = {
            f'{INTEGRATION_NAME_CONTEXT}.Vault(val.ID && val.ID === obj.ID)': context_entry
        }
        human_readable = tableToMarkdown(title, context_entry)
        return_outputs(human_readable, context, raw_response)
    else:
        return_error(f'{INTEGRATION_NAME} - Could not lock vault ID: {vault_to_lock}')


def reset_account_command(client: Client):
    """
    Gets details about a raw_response using IDs or some other filters
    """
    # Initialize main vars
    context: Dict = dict()
    # Get arguments from user
    account_to_reset: str = demisto.args().get('account_id', '')
    # Make request and get raw response
    defaulted_account: str = client.reset_account_request(account_to_reset)
    # Parse response into context & content entries
    if defaulted_account == account_to_reset:
        title: str = f'{INTEGRATION_NAME} - Account `{defaulted_account}` has been returned to default.'
        context_entry = {
            'IsLocked': False,
            'ID': account_to_reset
        }

        context[f'{INTEGRATION_NAME_CONTEXT}.Account(val.ID && val.ID === obj.ID)'] = context_entry
        # Creating human readable for War room
        human_readable: str = tableToMarkdown(title, context_entry)
        # Return data to Demisto
        return_outputs(human_readable, context)
    else:
        return_error(f'{INTEGRATION_NAME} - Could not reset account `{account_to_reset}`')


def list_credentials(client: Client):
    raw_response: Dict = client.fetch_credentials()
    credentials: List[Dict] = raw_response.get('credentials', [])
    if credentials:
        title: str = f'{INTEGRATION_NAME} - Credentials list.'
        context_entry = [{
            'Name': credential.get('name')
        } for credential in credentials]
        context = {
            f'{INTEGRATION_NAME_CONTEXT}.Credential(val.Name && val.Name ==== obj.Name)': context_entry
        }
        human_readable = tableToMarkdown(title, context_entry)
        return_outputs(human_readable, context, context)
    else:
        return_warning(f'{INTEGRATION_NAME} - Could not find any credentials.')


''' COMMANDS MANAGER / SWITCH PANEL '''


def main():
    server: str = demisto.getParam('url')
    use_ssl: bool = not demisto.params().get('insecure', False)
    client: Client = Client(server, use_ssl)
    command: str = demisto.command()
    demisto.info(f'Command being called is {command}')
    commands: Dict = {
        'test-module': test_module,
        'fetch-credentials': fetch_credentials,
        f'{INTEGRATION_NAME_COMMAND}-list-credentials': list_credentials,
        f'{INTEGRATION_NAME_COMMAND}-lock-account': lock_account,
        f'{INTEGRATION_NAME_COMMAND}-unlock-account': unlock_account,
        f'{INTEGRATION_NAME_COMMAND}-reset-account': reset_account_command,
        f'{INTEGRATION_NAME_COMMAND}-lock-vault': lock_vault,
        f'{INTEGRATION_NAME_COMMAND}-unlock-vault': unlock_vault
    }
    try:
        if command in commands:
            commands[command](client)
    # Log exceptions
    except Exception as e:
        err_msg = f'Error in AuthenticationExample Integration [{e}]'
        return_error(err_msg, error=e)


if __name__ == '__builtin__':
    main()
