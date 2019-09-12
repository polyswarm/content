import demistomock as demisto
from CommonServerPython import *
from CommonServerUserPython import *

''' IMPORTS '''
from typing import Dict, Tuple, List, Optional, Union, AnyStr
import urllib3

"""Example for Analytics and SIEM integration
    
Todo:
    * pass on it with alex
"""
# Disable insecure warnings
urllib3.disable_warnings()


class Client(BaseHTTPClient):
    """
    Wrapper class for BaseClient with additional functionality for the integration.
    """

    def __init__(self, *args, **kwargs):
        # Adds a max_results to client
        self._fetch_max_results = kwargs.get('max_results')
        # remove `max_results`
        kwargs.pop('max_results', None)
        super().__init__(*args, **kwargs)

    @property
    def max_results(self):
        return self._fetch_max_results

    def test_module_request(self) -> Dict:
        """Performs basic GET request to check if the API is reachable and authentication is successful.

        Returns:
            Response json
        """
        return self._http_request('GET', 'version')

    def list_events_request(self, max_results: Union[int, str] = None,
                            event_created_date_after: Optional[str] = None,
                            event_created_date_before: Optional[str] = None) -> Dict:
        """Returns all events by sending a GET request.

        Args:
            max_results: The maximum number of events to return.
            event_created_date_after: Returns events created after this date.
            event_created_date_before: Returns events created before this date.

        Returns:
            Response from API. from since_time if supplied else returns all events in given limit.
        """
        # The service endpoint to request from
        suffix = 'event'
        # Dictionary of params for the request
        params = assign_params(
            sinceTime=event_created_date_after,
            fromTime=event_created_date_before,
            limit=max_results)
        # Send a request using our http_request wrapper
        return self._http_request('GET', suffix, params=params)

    def event_request(self, event_id: AnyStr) -> Dict:
        """Return an event by the event ID.

        Args:
            event_id: event id to get

        Returns:
            event details
        """
        # The service endpoint to request from
        suffix = 'event'
        # Dictionary of params for the request
        params = assign_params(eventId=event_id)
        # Send a request using our http_request wrapper
        return self._http_request('GET', suffix, params=params)

    def close_event_request(self, event_id: AnyStr) -> Dict:
        """Closes the sepcified event.

        Args:
            event_id: The ID of the event to close.

        Returns:
            Response from API
        """
        # The service endpoint to request from
        suffix = 'event'
        # Dictionary of params for the request
        params = assign_params(eventId=event_id)
        # Send a request using our http_request wrapper
        return self._http_request('DELETE', suffix, params=params)

    def update_event_request(self, event_id: AnyStr, description: Optional[AnyStr] = None,
                             assignee: Optional[List[str]] = None) -> Dict:
        """Updates the specified event.

        Args:
            event_id: The ID of the event to update.
            assignee: A list of user IDs to assign to the event.
            description: The updated description of the event.


        Returns:
            Response from API
        """
        # The service endpoint to request from
        suffix = 'event'
        # Dictionary of params for the request
        params = assign_params(eventId=event_id, description=description, assignee=assignee)
        # Send a request using our http_request wrapper
        return self._http_request('POST', suffix, params=params)

    def create_event_request(self, description: str, assignee: List[str] = None) -> Dict:
        """Creates an event in the service.

        Args:
            description: A description of the event.
            assignee: A list of user IDs to assign to the event.

        Returns:
            Response from API
        """
        # The service endpoint to request from
        suffix = 'event'
        # Dictionary of params for the request
        params = assign_params(description=description, assignee=assignee)
        # Send a request using our http_request wrapper
        return self._http_request('POST', suffix, params=params)

    def query_request(self, **kwargs) -> Dict:
        """Query the specified kwargs.

        Args:
            **kwargs: The keyword argument for which to search.

        Returns:
            Response from API
        """
        # The service endpoint to request from
        suffix = 'query'
        # Send a request using our http_request wrapper
        return self._http_request('GET', suffix, params=kwargs)


''' HELPER FUNCTIONS '''


def build_context(events: Union[Dict, List]) -> Union[Dict, List]:
    """Formats the API response to Demisto context.

    Args:
        events: The raw response from the API call. Can be a List or Dict.

    Returns:
        The formatted Dict or List.

    Examples:
        >>> build_context({'eventId': '1', 'description': 'event description', 'createdAt':\
        '2019-09-09T08:30:07.959533', 'isActive': True, 'assignee': [{'name': 'user1', 'id': '142'}]})
        {'ID': '1', 'Description': 'event description', 'Created': '2019-09-09T08:30:07.959533', 'IsActive': True,\
 'Assignee': [{'Name': 'user1', 'ID': '142'}]}
    """

    def build_dict(event: Dict) -> Dict:
        """Builds a Dict formatted for Demisto.

        Args:
            event: A single event from the API call.

        Returns:
            A Dict formatted for Demisto context.
        """
        return {
            'ID': event.get('eventId'),
            'Description': event.get('description'),
            'Created': event.get('createdAt'),
            'IsActive': event.get('isActive'),
            'Assignee': [
                {
                    'Name': user.get('name'),
                    'ID': user.get('id')
                } for user in event.get('assignee', [])
            ]
        }

    if isinstance(events, list):
        return [build_dict(event) for event in events]
    return build_dict(events)


''' COMMANDS '''


def test_module(client: Client, *_) -> Tuple[str, Dict, Dict]:
    """Performs a basic GET request to check if the API is reachable and authentication is successful.
    """
    results = client.test_module_request()
    if 'version' in results:
        return 'ok', {}, {}
    raise DemistoException('Test module failed, {}'.format(results))


def fetch_incidents(client: Client, last_run):
    """Uses to fetch credentials into Demisto
    Documentation: https://github.com/demisto/content/tree/master/docs/fetching_credentials
    """
    timestamp_format = '%Y-%m-%dT%H:%M:%S.%fZ"'
    # Get incidents from API
    if not last_run:  # if first time running
        last_run, _ = parse_date_range(demisto.params().get('fetch_time'))
        last_run_string = last_run.strftime(timestamp_format)
    else:
        last_run_string = datetime.strptime(last_run, timestamp_format)
    incidents = list()
    raw_response = client.list_events_request(event_created_date_after=last_run_string,
                                              max_results=client.max_results)
    events: List[Dict] = raw_response.get('event', [])
    if events:
        # Creates incident entry
        incidents = [{
            'name': event.get('title'),
            'occurred': event.get('created'),
            'rawJSON': json.dumps(event)
        } for event in events]

        last_incident_timestamp = incidents[-1].get('occurred')
        demisto.setLastRun(last_incident_timestamp)
    demisto.incidents(incidents)
    # Return empty results
    return '', {}, {}


def list_events(client: Client, args: Dict) -> Tuple[str, Dict, Dict]:
    max_results: Optional[str] = args.get('max_results')
    event_created_date_before: Optional[str] = args.get('event_created_date_before')
    event_created_date_after: Optional[str] = args.get('event_created_date_after')
    raw_response = client.list_events_request(
        event_created_date_before=event_created_date_before,
        event_created_date_after=event_created_date_after,
        max_results=max_results)
    events = raw_response.get('event', [])
    if events:
        title: str = f'{client.integration_name} - List events:'
        context_entry = build_context(events)
        context = {f'{client.integration_context_name}.Event(val.ID && val.ID === obj.ID)': context_entry}
        # Creating human readable for War room
        human_readable = tableToMarkdown(title, context_entry)
        # Return data to Demisto
        return human_readable, context, raw_response
    else:
        raise DemistoException(f'{client.integration_name} - Could not find any events.')


def get_event(client: Client, args: Dict) -> Tuple[str, Dict, Dict]:
    """
    Gets details about a raw_response using the event ID or other valid filters.
    """
    # Get arguments from user
    event_id: str = args.get('event_id', '')
    # Make request and get raw response
    raw_response: Dict = client.event_request(event_id)
    # Parse response into context & content entries
    event: Dict = raw_response.get('event', {})
    if event:
        title: str = f'{client.integration_name} - Event `{event_id}`:'
        context_entry = build_context(event)
        context = {f'{client.integration_context_name}.Event(val.ID && val.ID === obj.ID)': context_entry}
        # Creating human readable for War room
        human_readable = tableToMarkdown(title, context_entry)
        # Return data to Demisto
        return human_readable, context, raw_response
    else:
        raise DemistoException(f'{client.integration_name} - Could not find event `{event_id}`')


def close_event(client: Client, args: Dict) -> Tuple[str, Dict, None]:
    """
    Gets details about a raw_response using the event ID or other valid filters.
    """
    # Get arguments from user
    event_id: str = args.get('event_id', '')
    # Make request and get raw response
    event = client.close_event_request(event_id)
    # Parse response into context & content entries
    if event:
        title = f'{client.integration_name} - Event `{event_id}` has been deleted.'
        context_entry = build_context(event)
        context = {f'{client.integration_context_name}.Event(val.ID && val.ID === obj.ID)': context_entry}
        # Creating human readable for War room
        human_readable: str = tableToMarkdown(title, context_entry)
        # Return data to Demisto
        return human_readable, context, None
    else:
        raise DemistoException(f'{client.integration_name} - Could not delete event `{event_id}`')


def update_event(client: Client, args: Dict) -> Tuple[str, Dict, Dict]:
    # Get arguments from user
    event_id: str = args.get('event_id', '')
    description: str = args.get('description', '')
    assignee: List[str] = argToList(args.get('assignee', ''))
    # Make request and get raw response
    raw_response = client.update_event_request(event_id, description=description, assignee=assignee)
    event = raw_response.get('event')
    # Parse response into context & content entries
    if event:
        title: str = f'{client.integration_name} - Event `{event_id}` has been updated.'
        context_entry = build_context(event)
        context = {f'{client.integration_context_name}.Event(val.ID && val.ID === obj.ID)': context_entry}
        human_readable = tableToMarkdown(title, context_entry)
        return human_readable, context, raw_response
    else:
        raise DemistoException(f'{client.integration_name} - Could not update event `{event_id}`')


def create_event(client: Client, args: Dict) -> Tuple[str, Dict, Dict]:
    # Get arguments from user
    description: str = args.get('description', '')
    assignee: List[str] = argToList(demisto.args().get('assignee', ''))
    # Make request and get raw response
    raw_response: Dict = client.create_event_request(description, assignee)
    event: Dict = raw_response.get('event', {})
    # Parse response into context & content entries
    if event:
        event_id: str = event.get('eventId', '')
        title = f'{client.integration_name} - Event `{event_id}` has been created.'
        context_entry = build_context(event)
        context = {f'{client.integration_context_name}.Event(val.ID && val.ID === obj.ID)': context_entry}
        human_readable = tableToMarkdown(title, context_entry)
        return human_readable, context, raw_response
    else:
        raise DemistoException(f'{client.integration_name} - Could not create new event.')


def query(client: Client, args: Dict):
    # Get arguments from user
    query_dict = assign_params(
        eventId=args.get('event_id'),
        sinceTime=args.get('since_time'),
        assignee=argToList(args.get('assignee')),
        isActive=args.get('is_active') == 'true'
    )
    # Make request and get raw response
    raw_response: Dict = client.query_request(**query_dict)
    events: List = raw_response.get('event', [])
    # Parse response into context & content entries
    if events:
        title = f'{client.integration_name} - Results for given query'
        context_entry = build_context(events)
        context = {f'{client.integration_context_name}.Event(val.ID && val.ID === obj.ID)': context_entry}
        human_readable: str = tableToMarkdown(title, context_entry)
        return human_readable, context, raw_response
    else:
        return_warning(f'{client.integration_name} - Could not find any results for given query')


''' COMMANDS MANAGER / SWITCH PANEL '''


def main():
    """ GLOBALS/PARAMS """
    integration_name = 'Analytics & SIEM Integration'
    # lowercase with `-` dividers
    integration_command_name = 'analytics-and-siem'
    # No dividers
    integration_context_name = 'AnalyticsAndSIEM'
    params = demisto.params()
    server = params.get('url', '')
    verify_ssl = not params.get('insecure', False)
    proxy = params.get('proxy')
    base_suffix = '/api/v2/'
    client: Client = Client(server=server,
                            integration_name=integration_name,
                            integration_command_name=integration_command_name,
                            integration_context_name=integration_context_name,
                            base_suffix=base_suffix,
                            verify=verify_ssl,
                            proxy=proxy)
    command = demisto.command()
    demisto.info(f'Command being called is {command}')

    # Switch case
    commands = {
        'test-module': test_module,
        'fetch-incidents': fetch_incidents,
        f'{client.integration_command_name}-list-events': list_events,
        f'{client.integration_command_name}-get-event': get_event,
        f'{client.integration_command_name}-delete-event': close_event,
        f'{client.integration_command_name}-update-event': update_event,
        f'{client.integration_command_name}-create-event': create_event,
        f'{client.integration_command_name}-query': query
    }
    try:
        if command == 'fetch-incidents':
            commands[command](client, last_run=demisto.getLastRun())
        elif command in commands:
            human_readable, context, raw_response = commands[command](client, demisto.args())
            return_outputs(human_readable, context, raw_response)
    # Log exceptions
    except Exception as e:
        err_msg = f'Error in {client.integration_name} Integration [{e}]'
        return_error(err_msg, error=e)


if __name__ == 'builtins':
    main()

# TODO: add pip file
