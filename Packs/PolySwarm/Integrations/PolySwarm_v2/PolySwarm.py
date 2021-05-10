''' IMPORTS '''
import demistomock as demisto
from CommonServerPython import *

from polyswarm_api.api import PolyswarmAPI

import socket
import io

''' CONSTANTS '''
POLYSWARM_DEMISTO_VERSION = '0.2.0'
ERROR_ENDPOINT = 'Error with endpoint: '


# Allows nested keys to be accesible
def makehash():
    import collections
    return collections.defaultdict(makehash)


# Polyswarm-Demisto Interface
class PolyswarmConnector():
    def __init__(self):
        self.config = {}  # type: Dict[str,str]
        self.config['polyswarm_api_key'] = demisto.params().get('api_key')
        self.config['base_url'] = demisto.params().get('base_url')
        self.config['polyswarm_community'] = demisto.params().get('polyswarm_community')

        self.polyswarm_api = PolyswarmAPI(key=self.config['polyswarm_api_key'],
                                          uri=self.config['base_url'])

    def _get_results(self,
                     object_name: str,
                     total_scans: int,
                     positives: int,
                     permalink: str,
                     artifact: str,
                     indicator: object = None) -> object:

        results = {'Scan_UUID': artifact,
                   'Total': str(total_scans),
                   'Positives': str(positives),
                   'Permalink': permalink,
                   'Artifact': artifact}

        return CommandResults(
            outputs_prefix=f'PolySwarm.{object_name}',
            outputs_key_field='Scan_UUID',
            outputs=results,
            indicator=indicator,
            ignore_auto_extract=True
        )

    def test_connectivity(self) -> bool:
        EICAR_HASH = '131f95c51cc819465fa1797f6ccacf9d494aaaff46fa3eac73ae63ffbdfd8267'  # guardrails-disable-line

        try:
            results = self.polyswarm_api.search(EICAR_HASH)
            for result in results:
                if result.failed:
                    return False
        except Exception:
            return False

        return True

    def file_reputation(self,
                        param: dict) -> object:
        file_hash = param.get('file', param.get('hash'))
        if not file_hash:
            return_error("Please specify a file hash to enrich.")

        title = 'PolySwarm File Reputation for Hash: %s' % file_hash

        demisto.debug(f'[file_reputation] {title}')

        # default values
        total_scans = 0
        positives = 0
        permalink = ''

        try:
            results = self.polyswarm_api.search(file_hash)

            for result in results:
                if result.failed:
                    return_error('Error fetching results. Please try again.')

                if not result.assertions:
                    return_error('Run Rescan for this hash')

                for assertion in result.assertions:
                    if assertion.verdict:
                        positives += 1
                    total_scans += 1

                permalink = result.permalink

            demisto.debug('Positives: {positives} - Total Scans: {total_scans}'.
                          format(positives=positives, total_scans=total_scans))

        except Exception as err:
            return_error('{ERROR_ENDPOINT}{err}'.
                         format(ERROR_ENDPOINT=ERROR_ENDPOINT,
                                err=err))

        return self._get_results('File', total_scans,
                                 positives, permalink,
                                 file_hash)

    def get_file(self, param: dict) -> object:
        demisto.debug(f'[get_file] Hash: {param["hash"]}')

        handle_file = io.BytesIO()

        try:
            self.polyswarm_api.download_to_handle(param['hash'],
                                                  handle_file)
            return fileResult(param['hash'], handle_file.getvalue())
        except Exception as err:
            return_error('{ERROR_ENDPOINT}{err}'.
                         format(ERROR_ENDPOINT=ERROR_ENDPOINT,
                                err=err))

    def detonate_file(self, param: dict) -> object:
        title = 'PolySwarm File Detonation for Entry ID: %s' % param['entryID']

        demisto.debug(f'[detonate_file] {title}')

        # default values
        total_scans = 0
        positives = 0

        try:
            file_info = demisto.getFilePath(param['entryID'])
        except Exception:
            return_error('File not found - EntryID: {entryID}'.
                         format(entryID=param['entryID']))

        try:
            demisto.debug(f'Submit file: {file_info}')
            instance = self.polyswarm_api.submit(file_info['path'],
                                                 artifact_name=file_info['name'])
            result = self.polyswarm_api.wait_for(instance)

            if result.failed:
                return demisto.results('Error submitting File.')

            # iterate for getting positives and total_scan number
            for assertion in result.assertions:
                if assertion.verdict:
                    positives += 1
                total_scans += 1

        except Exception as err:
            return_error('{ERROR_ENDPOINT}{err}'.
                         format(ERROR_ENDPOINT=ERROR_ENDPOINT,
                                err=err))

        return self._get_results('File', total_scans,
                                 positives, result.permalink,
                                 file_info['name'])

    def rescan_file(self, param: dict) -> object:
        title = 'PolySwarm Rescan for Hash: %s' % param['hash']

        demisto.debug(f'[rescan_file] {title}')

        # default values
        total_scans = 0
        positives = 0

        try:
            instance = self.polyswarm_api.rescan(param['hash'])
            result = self.polyswarm_api.wait_for(instance)

            if result.failed:
                return demisto.results('Error rescaning File.')

            # iterate for getting positives and total_scan number
            for assertion in result.assertions:
                if assertion.verdict:
                    positives += 1
                total_scans += 1

        except Exception as err:
            return_error('{ERROR_ENDPOINT}{err}'.
                         format(ERROR_ENDPOINT=ERROR_ENDPOINT,
                                err=err))

        return self._get_results('File', total_scans,
                                 positives, result.permalink,
                                 param['hash'])

    def url_reputation(self,
                       param: dict,
                       artifact_type: str) -> list:

        command_results = []

        artifacts = argToList(param[artifact_type])

        for artifact in artifacts:
            title = 'PolySwarm %s Reputation for: %s' % (artifact_type.upper(),
                                                         artifact)

            demisto.debug(f'[url_reputation] {title}')

            # default values
            total_scans = 0
            positives = 0

            # IP validation
            if artifact_type == 'ip':
                try:
                    socket.inet_aton(artifact)
                except socket.error:
                    return_error('Invalid IP Address: {ip}'.
                                 format(ip=artifact))

            try:
                # PolySwarm API: URL, IP and Domain are artifact_type='url'
                instance = self.polyswarm_api.submit(artifact,
                                                     artifact_type='url')
                result = self.polyswarm_api.wait_for(instance)

                if result.failed:
                    return demisto.results('Error submitting URL.')

                # iterate for getting positives and total_scan number
                for assertion in result.assertions:
                    if assertion.verdict:
                        positives += 1
                    total_scans += 1

            except Exception as err:
                return_error('{ERROR_ENDPOINT}{err}'.
                             format(ERROR_ENDPOINT=ERROR_ENDPOINT,
                                    err=err))

            score = Common.DBotScore.SUSPICIOUS if positives > 0 else Common.DBotScore.GOOD

            if artifact_type == 'ip':
                object_name = 'IP'
                dbot_score_type = DBotScoreType.IP
            elif artifact_type == 'url':
                object_name = 'URL'
                dbot_score_type = DBotScoreType.URL
            elif artifact_type == 'domain':
                object_name = 'Domain'
                dbot_score_type = DBotScoreType.DOMAIN

            dbot_score = Common.DBotScore(indicator=artifact,
                                          indicator_type=dbot_score_type,
                                          integration_name='PolySwarm',
                                          score=score)

            indicator = None
            if artifact_type == 'ip':
                indicator = Common.IP(ip=artifact,
                                      dbot_score=dbot_score)
            elif artifact_type == 'url':
                indicator = Common.URL(url=artifact,
                                       dbot_score=dbot_score)
            elif artifact_type == 'domain':
                indicator = Common.Domain(domain=artifact,
                                          dbot_score=dbot_score)

            results = self._get_results(object_name, total_scans,
                                        positives, result.permalink,
                                        artifact, indicator)
            command_results.append(results)

        return command_results

    def get_report(self, param: dict) -> object:
        """
            UUID is equal to Hash.
        """
        title = 'PolySwarm Report for UUID: %s' % param['scan_uuid']

        demisto.debug(f'[get_report] {title}')

        # default values
        total_scans = 0
        positives = 0

        try:
            results = self.polyswarm_api.search(param['scan_uuid'])
            for result in results:
                if result.failed:
                    return_error('Error fetching results. Please try again.')

                if not result.assertions:
                    return_error('Run Rescan for this hash')

                for assertion in result.assertions:
                    if assertion.verdict:
                        positives += 1
                    total_scans += 1

                permalink = result.permalink

            demisto.debug('Positives: {positives} - Total Scans: {total_scans}'.
                          format(positives=positives, total_scans=total_scans))

        except Exception as err:
            return_error('{ERROR_ENDPOINT}{err}'.
                         format(ERROR_ENDPOINT=ERROR_ENDPOINT,
                                err=err))

        return self._get_results('File', total_scans,
                                 positives, permalink,
                                 param['scan_uuid'])


def main():
    ''' EXECUTION '''
    LOG('command is %s' % (demisto.command(),))
    try:
        polyswarm = PolyswarmConnector()

        command = demisto.command()
        param = demisto.args()

        if command == 'test-module':
            if polyswarm.test_connectivity():
                return_results('ok')
            else:
                return_error('Connection Failed')
        elif command == 'file':
            return_results(polyswarm.file_reputation(param))
        elif command == 'get-file':
            return_results(polyswarm.get_file(param))
        elif command == 'file-scan':
            return_results(polyswarm.detonate_file(param))
        elif command == 'file-rescan':
            return_results(polyswarm.rescan_file(param))
        elif command == 'url':
            return_results(polyswarm.url_reputation(param, 'url'))
        elif command == 'url-scan':
            return_results(polyswarm.url_reputation(param, 'url'))
        elif command == 'ip':
            return_results(polyswarm.url_reputation(param, 'ip'))
        elif command == 'domain':
            return_results(polyswarm.url_reputation(param, 'domain'))
        elif command == 'polyswarm-get-report':
            return_results(polyswarm.get_report(param))

    except Exception as e:
        return_error(str(e),
                     error=traceback.format_exc())


if __name__ in ('__main__', '__builtin__', 'builtins'):
    main()
