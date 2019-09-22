from typing import Dict

from CommonServerPython import *
from DataEnrichmentThreatIntelligence import Client
from pytest import raises

BASE_URL = 'https://example.com/api/v1/'
FILE_RESULTS = {
    'result': [
        {
            'id': 1,
            'severity': 75,
            'md5': 'd1e09edea866f35738ab48893603a025',
            'sha1': 'f06f909f532683fe62feed4481b4b36067e807be',
            'sha256': '42a5e275559a1651b3df8e15d3f5912499f0f2d3d1523959c56fc5aea6371e59',
            'ssdeep': '6:lR393QRG7+IKG7gofyG7FVZOxIT5elQKG70WBAXXU:9DSIdUo9JVZOIWQdAWwE',
            'description': 'yml file'
        }
    ]
}

IP_RESULTS = {
    'result': [
        {
            'id': 101,
            'severity': 0,
            'IP': '8.8.8.8',
            'description': 'Google\'s DNS'
        }
    ]
}

URL_RESULTS = {
    'result': [
        {
            'id': 101,
            'severity': 31,
            'URL': 'suspicious.example.com',
            'description': 'Scary URL'
        }
    ]
}

DOMAIN_RESULTS = {
    'result': [
        {
            'id': 101,
            'severity': 50,
            'Domain': 'example.com',
            'description': 'Scary domain'
        }
    ]
}

CLIENT = Client(BASE_URL, threshold=50)

EMPTY_RESPONSE: Dict = {'result': []}


class TestDeTi:
    def test_test_module(self, requests_mock):
        from DataEnrichmentThreatIntelligence import test_module
        requests_mock.get(BASE_URL + 'version', json={'version': '1.5.0'})
        human_readable, _, _ = test_module(CLIENT)
        assert human_readable == 'ok'

    def test_test_module_negative(self, requests_mock):
        from DataEnrichmentThreatIntelligence import test_module
        requests_mock.get(BASE_URL + 'version', json={})
        with raises(DemistoException, match='Test module failed'):
            test_module(CLIENT)

    def test_ip_positive(self, requests_mock):
        from DataEnrichmentThreatIntelligence import search_ip
        requests_mock.get(BASE_URL + 'ip?ip=8.8.8.8', json=IP_RESULTS)
        human_readable, context, _ = search_ip(CLIENT, {'ip': '8.8.8.8'})
        assert 'Analysis results for IP: 8.8.8.8' in human_readable
        assert 'DBotScore' in context
        assert len(context) == 2

    def test_ip_negative(self, requests_mock):
        from DataEnrichmentThreatIntelligence import search_ip
        requests_mock.get(BASE_URL + 'ip?ip=8.8.8.8', json=EMPTY_RESPONSE)
        human_readable, context, raw_response = search_ip(CLIENT, {'ip': '8.8.8.8'})
        assert not context
        assert 'No results found' in human_readable
        assert raw_response == raw

    def test_url_positive(self, requests_mock):
        from DataEnrichmentThreatIntelligence import search_url
        requests_mock.get(BASE_URL + 'analysis?url=malicious.example.com', json=URL_RESULTS)
        human_readable, context, raw_response = search_url(CLIENT, {'url': 'malicious.example.com'})
        assert 'Analysis results for URL: malicious.example.com' in human_readable
        assert context[outputPaths['dbotscore']]['Score'] == 2
        assert raw_response == URL_RESULTS

    def test_url_negative(self, requests_mock):
        from DataEnrichmentThreatIntelligence import search_url
        requests_mock.get(BASE_URL + 'analysis?url=malicious.example.com', json=EMPTY_RESPONSE)
        human_readable, context, raw_response = search_url(CLIENT, {'url': 'malicious.example.com'})
        assert 'No results found' in human_readable
        assert not context
        assert raw_response == EMPTY_RESPONSE

    def test_file_positive(self, requests_mock):
        from DataEnrichmentThreatIntelligence import search_file
        file_hash = 'd1e09edea866f35738ab48893603a025'
        requests_mock.get(BASE_URL + f'analysis?hash={file_hash}', json=FILE_RESULTS)
        human_readable, context, raw_response = search_file(CLIENT, {'file': 'd1e09edea866f35738ab48893603a025'})
        assert 'Analysis results for file hash' in human_readable
        assert len(context['DBotScore']) == 4
        assert raw_response == FILE_RESULTS

    def test_file_negative(self, requests_mock):
        from DataEnrichmentThreatIntelligence import search_file
        file_hash = 'd1e09edea866f35738ab48893603a025'
        requests_mock.get(BASE_URL + f'analysis?hash={file_hash}', json=EMPTY_RESPONSE)
        human_readable, context, raw_response = search_file(CLIENT, {'file': file_hash})
        assert 'No results found' in human_readable
        assert not context
        assert raw_response == EMPTY_RESPONSE

    def test_domain_positive(self, requests_mock):
        from DataEnrichmentThreatIntelligence import search_domain
        domain = 'example.com'
        requests_mock.get(BASE_URL + f'analysis?domain={domain}', json=DOMAIN_RESULTS)
        human_readable, context, raw_response = search_domain(CLIENT, {'domain': domain})
        assert 'Analysis results for domain' in human_readable
        assert len(context['DBotScore']) == 4
        assert raw_response == DOMAIN_RESULTS

    def test_domain_negative(self, requests_mock):
        from DataEnrichmentThreatIntelligence import search_domain
        domain = 'example.com'
        requests_mock.get(BASE_URL + f'analysis?domain={domain}', json=EMPTY_RESPONSE)
        human_readable, context, raw_response = search_domain(CLIENT, {'domain': domain})
        assert 'No results found' in human_readable
        assert not context
        assert raw_response == EMPTY_RESPONSE


class TestHelperFunctions:
    def test_calculate_dbot(self):
        assert CLIENT.calculate_dbot_score(100) == 3
        assert CLIENT.calculate_dbot_score(40) == 2
        assert CLIENT.calculate_dbot_score(10) == 1
        assert CLIENT.calculate_dbot_score(-1) == 0
        assert CLIENT.calculate_dbot_score(10, 5) == 3
