import datetime
import gzip
import http.client
import json
import time
import traceback
import urllib.parse
import urllib.request
from base64 import b64encode
from bz2 import compress
from distutils.log import error
from io import BytesIO

timeout_seconds = 240

date_format = "%Y-%m-%dT%H:%M:%SZ"
thales_date_format = '%Y-%m-%d %H:%M:%S %Z'
thales_millisecond_date_format = '%Y-%m-%d %H:%M:%S.%f %Z'


class LunaCloudHsmProcessor:
    def __init__(self, helper, ew, definition=None, validate_only=False):
        self.helper = helper
        self.ew = ew
        self.definition = definition
        self.access_token = None

        if validate_only:
            self.auth_url = urllib.parse.urlparse(self.definition.parameters.get(
                'authentication_api_base', None))
            self.api_url = urllib.parse.urlparse(
                self.definition.parameters.get('dpod_api_base', None))
        else:
            self.auth_url = urllib.parse.urlparse(
                helper.get_arg('authentication_api_base'))
            self.api_url = urllib.parse.urlparse(
                helper.get_arg('dpod_api_base'))
            self.properties = {
                "authentication_api_base": helper.get_arg('authentication_api_base'),
                "dpod_api_base": helper.get_arg('dpod_api_base'),
                "Bearer": "",
                "client_id": helper.get_arg('client_id'),
                "client_secret": helper.get_arg('client_secret'),
                "proximity": "",
                "use_proxy": False,
                "aggregate_event_types": []
            }
            if (helper.get_arg('aggregate_event_types')):
                self.properties['aggregate_event_types'] = str(
                    helper.get_arg('aggregate_event_types')).split(',')

            proxy_settings = helper.get_proxy()
            if (proxy_settings):
                self.properties['use_proxy'] = True
                self.properties['proxy_url'] = proxy_settings['proxy_url']
                self.properties['proxy_port'] = proxy_settings['proxy_port']
                self.properties['proxy_type'] = proxy_settings['proxy_type']
                self.properties['proxy_username'] = proxy_settings['proxy_username']
                self.properties['proxy_password'] = proxy_settings['proxy_password']
                self.properties['proxy_rdns'] = proxy_settings['proxy_rdns']

    def validate_input(self):
        try:
            assert (self.auth_url.scheme.lower() == "https")
            assert (self.api_url.scheme.lower() == "https")
        except Exception as err:
            error_message = "Validation Exception Occured %s" % err.__class__.__qualname__
            self.helper.log_error(error_message)
            self.helper.log_error("Trace: %s" %
                                  traceback.format_exception(err))
            exit(2)

    # Send a status event to Splunk
    def send_status_event(self, message, status="INFO"):
        build_event = "_time=" + \
            str(round(datetime.datetime.now().timestamp())) + ","
        build_event = build_event + "clientid=" + \
            str(self.helper.get_arg('client_id'))+','
        build_event = build_event + "message=" + json.dumps(message)
        build_event = build_event + ",severity=" + status
        event = self.new_event(source=self.helper.get_input_type(), index=self.helper.get_output_index(
        ), sourcetype=self.helper.get_sourcetype(), data=build_event)
        self.ew.write_event(event)

    # Get a token from Thales Auth endpoint
    def get_token(self):
        auth_request = {
            "client_id": self.properties['client_id'],
            "client_secret": self.properties['client_secret'],
            "grant_type": "client_credentials",
        }
        payload = urllib.parse.urlencode(auth_request)

        conn, headers = self.get_http_connection(self.auth_url.geturl())
        headers['Accept'] = 'application/json'
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        try:
            conn.request("POST", "/oauth/token", payload, headers)
            res = conn.getresponse()
            if res.status != 200:
                error_message = "Failed getting HSM Bearer Token with response => %d : %s" % (
                    res.status, res.reason)
                self.helper.log_error(error_message)
                self.send_status_event(error_message, "ERROR")
                exit(2)
            else:
                data = res.read()
                auth_data = json.loads(data.decode("utf-8"))
                self.access_token = auth_data["access_token"]
                return auth_data["access_token"]
        except Exception as err:
            error_message = "Error occurred on getting the Session token from Cloud AppSec portal. %s" % err.__class__.__qualname__
            self.helper.log_error(error_message)
            self.helper.log_error("Trace: %s" %
                                  traceback.format_exception(err))
            self.send_status_event(error_message, "ERROR")
            exit(2)

    # Custom function to set up HTTP Connections. Proxy compatible
    def get_http_connection(self, url):
        url = urllib.parse.urlparse(url)
        headers = {}
        if self.properties['use_proxy']:
            proxy_host = self.properties['proxy_url']
            proxy_port = self.properties['proxy_port']
            if (self.properties['proxy_username']):
                userAndPass = self.properties['proxy_username'] + \
                    ":" + self.properties['proxy_password']
                userAndPass = b64encode(userAndPass.encode()).decode("ascii")
                headers['Proxy-Authorization'] = "Basic %s", userAndPass
            if (url.scheme == 'https'):
                port = url.port if url.port else 443
                conn = http.client.HTTPSConnection(proxy_host, proxy_port)
            else:
                self.helper.log_error(
                    "Invalid Scheme in URL - %s. Only HTTPS supported.", url.geturl())
                exit(2)
            conn.set_tunnel(url.netloc, port=port)
        else:
            if (url.scheme == 'https'):
                port = url.port if url.port else 443
                conn = http.client.HTTPSConnection(url.hostname, port=port)
            else:
                self.helper.log_error(
                    "Invalid Scheme in URL - %s. Only HTTPS supported.", url.geturl())
                exit(2)
        return conn, headers

    # This function uses the DPOD Audit Query API to collect logs from DPOD Cloud HSM
    # Returns the location of the audit logs in the URL
    def get_audit_logs(self, now, past):
        conn, headers = self.get_http_connection(self.api_url.geturl())
        headers['Accept'] = 'application/json'
        headers['Content-Type'] = 'application/json'
        headers['Authorization'] = "Bearer %s" % self.access_token
        audit_request = {
            "from": past,
            "to": now
        }
        payload = json.dumps(audit_request)
        response_data = {}
        try:
            conn.request("POST", "/v1/audit-log-exports", payload, headers)
            res = conn.getresponse()
            if res.status != 201:
                error_message = "Failed Audit Log Export with response => %d : %s" % (
                    res.status, res.reason)
                self.helper.log_error(error_message)
                self.send_status_event(error_message, "ERROR")
                exit(2)
            else:
                data = res.read()
                response_data = json.loads(data.decode("utf-8"))
        except Exception as err:
            error_message = "Error occurred on Starting and Audit Log Export from Thales %s" % err.__class__.__qualname__
            self.helper.log_error(error_message)
            self.helper.log_error("Trace: %s" %
                                  traceback.format_exception(err))
            self.send_status_event(error_message, "ERROR")
            exit(2)
        conn.close()

        # Start polling for audit-log-export in DPOD API
        job_path = "/v1/audit-log-exports/%s" % response_data["jobId"]
        headers.pop("Content-Type")

        max_wait_times = timeout_seconds / 2
        run_counter = 0
        while (response_data["state"] != "SUCCEEDED" and run_counter < max_wait_times):
            time.sleep(2)
            try:
                conn.request(method="GET", url=job_path, headers=headers)
                res = conn.getresponse()
                if res.status != 200:
                    error_message = "Error occurred on Starting and Audit Log Export from Thales => %d : %s" % res.status, res.reason
                    self.helper.log_error(error_message)
                    self.send_status_event(error_message, 'ERROR')
                    exit(2)
                else:
                    data = res.read()
                    response_data = json.loads(data.decode("utf-8"))
            except Exception as err:
                error_message = "Error occurred on retrieving Log Export from Thales %s" % err.__class__.__qualname__
                self.helper.log_error(error_message)
                self.helper.log_error("Trace: %s" %
                                      traceback.format_exception(err))
                self.send_status_event(error_message, 'ERROR')
                exit(2)
            conn.close()
            run_counter = run_counter+1
        return response_data

    # Processes an audit log .gzip from DPOD Audit Query API
    # Will aggregate events depending on input configuration
    def process_audit_log_events(self, url):
        conn, headers = self.get_http_connection(url)
        url = urllib.parse.urlsplit(url)
        conn.request(method="GET", url="%s?%s" %
                     (url.path, url.query), headers=headers)
        response = conn.getresponse()
        compressedFile = BytesIO(response.read())
        conn.close()
        decompressedFile = gzip.GzipFile(fileobj=compressedFile, mode='rb')
        decompressedFile.seek(0)
        aggregate_events = {}
        while True:
            line = decompressedFile.readline()
            if line == b'':
                break
            luna_evt = json.loads(line)
            luna_meta = json.loads(luna_evt['meta'])
            if (self.properties['aggregate_event_types'] and str(luna_evt['action']) in self.properties['aggregate_event_types']):
                aggregate_key = str(luna_evt['action'])+":"+str(luna_evt['status'])+":"+str(
                    luna_meta['clientip'])+":"+str(luna_meta['partid'])+":" + str(luna_evt['source']) + ":" + str(luna_evt['resourceID']) + ":" + str(luna_evt['actorID'])
                if aggregate_key in aggregate_events:
                    aggregate_events[aggregate_key]['count'] += 1
                    aggregate_events[aggregate_key]['end_time'] = str(LunaCloudHsmProcessor.parse_luna_event_time(
                        luna_evt['time']).timestamp())
                else:
                    aggregate_events[aggregate_key] = {
                        'count': 1,
                        'original_event': luna_evt,
                        'original_meta': luna_meta,
                        'begin_time': str(LunaCloudHsmProcessor.parse_luna_event_time(
                            luna_evt['time']).timestamp()),
                        'end_time': str(LunaCloudHsmProcessor.parse_luna_event_time(
                            luna_evt['time']).timestamp())
                    }
            else:
                build_event = "_time=" + \
                    str(LunaCloudHsmProcessor.parse_luna_event_time(
                        luna_evt['time']).timestamp())+","
                build_event = build_event + "resourceID=" + \
                    str(luna_evt['resourceID'])+','
                build_event = build_event + "clientid=" + \
                    str(self.properties['client_id'])+','
                build_event = build_event + "actorID=" + \
                    str(luna_evt['actorID'])+','
                build_event = build_event + "tenantID=" + \
                    str(luna_evt['tenantID'])+','
                build_event = build_event + "action=" + \
                    str(luna_evt['action'])+','
                build_event = build_event + "status=" + \
                    str(luna_evt['status'])+','
                build_event = build_event + "clientip=" + \
                    str(luna_meta['clientip'])+','
                build_event = build_event + "role=" + \
                    str(luna_meta['role'])+','
                build_event = build_event + "hsmid=" + \
                    str(luna_meta['hsmid'])+','
                build_event = build_event + "partid=" + \
                    str(luna_meta['partid'])
                event = self.new_event(source=self.helper.get_input_type(), index=self.helper.get_output_index(
                ), sourcetype=self.helper.get_sourcetype(), data=build_event)
                self.ew.write_event(event)

        # Iterate through aggregated events and write to stream
        for agg_key in aggregate_events:
            luna_evt = aggregate_events[agg_key]['original_event']
            luna_meta = aggregate_events[agg_key]['original_meta']
            build_event = "_time=" + \
                str(LunaCloudHsmProcessor.parse_luna_event_time(
                    luna_evt['time']).timestamp())+","
            build_event = build_event + "clientid=" + \
                str(self.properties['client_id'])+','
            build_event = build_event + "resourceID=" + \
                str(luna_evt['resourceID'])+','
            build_event = build_event + "actorID="+str(luna_evt['actorID'])+','
            build_event = build_event + "tenantID=" + \
                str(luna_evt['tenantID'])+','
            build_event = build_event + "action="+str(luna_evt['action'])+','
            build_event = build_event + "status="+str(luna_evt['status'])+','
            build_event = build_event + "clientip=" + \
                str(luna_meta['clientip'])+','
            build_event = build_event + "role=" + \
                str(luna_meta['role'])+','
            build_event = build_event + "hsmid="+str(luna_meta['hsmid'])+','
            build_event = build_event + "partid="+str(luna_meta['partid'])+','
            build_event = build_event + "count=" + \
                str(aggregate_events[agg_key]['count'])
            event = self.new_event(source=self.helper.get_input_type(), index=self.helper.get_output_index(
            ), sourcetype=self.helper.get_sourcetype(), data=build_event)
            self.ew.write_event(event)

    # Wrapper function to help create events.
    def new_event(self, data, time=None, host=None, index=None, source=None, sourcetype=None, done=True, unbroken=True):
        """Create a Splunk event object. - Wrapper around the TA Helper to insert the DPOD Host if not provided in the event

        :param data: ``string``, the event's text.
        :param time: ``float``, time in seconds, including up to 3 decimal places to represent milliseconds.
        :param host: ``string``, the event's host, ex: localhost.
        :param index: ``string``, the index this event is specified to write to, or None if default index.
        :param source: ``string``, the source of this event, or None to have Splunk guess.
        :param sourcetype: ``string``, source type currently set on this event, or None to have Splunk guess.
        :param done: ``boolean``, is this a complete ``Event``? False if an ``Event`` fragment.
        :param unbroken: ``boolean``, Is this event completely encapsulated in this ``Event`` object?
        :return: ``Event`` object
        """
        data += f",input_config={self.helper.get_input_stanza_names()}"
        if host:
            return self.helper.new_event(data, time=time, host=host, index=index, source=index, sourcetype=sourcetype, done=True, unbroken=True)
        else:
            return self.helper.new_event(data, time=time, host=self.api_url.hostname, index=index, source=index, sourcetype=sourcetype, done=True, unbroken=True)

    def parse_luna_event_time(event_time):
        try:
            return datetime.datetime.strptime(event_time, thales_date_format)
        except ValueError:
            return datetime.datetime.strptime(event_time, thales_millisecond_date_format)


def validate_input(helper, definition):
    validator = LunaCloudHsmProcessor(helper, None, definition, True)
    validator.validate_input()


def collect_events(helper, ew):
    processor = LunaCloudHsmProcessor(helper, ew, None, False)

    processor.send_status_event("Starting Log Collection from %s,client_id=%s" % (
        helper.get_arg('dpod_api_base'), helper.get_arg('client_id')))

    # Get the auth token for the app using client_id and client_secret
    processor.get_token()

    # Get time window to filter for logs
    now_checkpoint = str(round(time.time()))
    last_checkpoint = helper.get_check_point("last_run_%s" %
                                             helper.get_arg('client_id'))
    interval = int(helper.get_arg('interval'))

    now = int(round(time.time()))
    past = now - interval

    # Check the last run checkpoint if set and use that as the 'from' parameter to Thales.
    # Make sure the interval is not more than 30 days
    if last_checkpoint and ((past > int(last_checkpoint)) and ((now - int(last_checkpoint)) < 2591998)):
        past = datetime.datetime.fromtimestamp(
            int(last_checkpoint)).strftime(date_format)
    else:
        past = datetime.datetime.fromtimestamp(past).strftime(date_format)
    now = datetime.datetime.fromtimestamp(now).strftime(date_format)

    # Request an audit log export from DPOD API
    audit_logs = processor.get_audit_logs(now, past)

    # Process resultant .gzip file into events
    processor.process_audit_log_events(audit_logs['location'])

    processor.send_status_event("Luna HSM log processing completed.")

    # Save Checkpoint - only save once all steps have finished.
    helper.save_check_point("last_run_%s" %
                            helper.get_arg('client_id'), now_checkpoint)
