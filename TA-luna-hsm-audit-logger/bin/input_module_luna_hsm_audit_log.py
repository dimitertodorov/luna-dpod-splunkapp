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

try:
    from StringIO import StringIO  # for Python 2
except ImportError:
    from io import StringIO  # for Python 3

timeout_seconds = 240

date_format = "%Y-%m-%dT%H:%M:%SZ"
thales_date_format = '%Y-%m-%d %H:%M:%S %Z'

# Custom function to set up HTTP Connections. Proxy compatible


def get_http_connection(helper, url, credentials):
    url = urllib.parse.urlparse(url)
    headers = {}
    if credentials['use_proxy']:
        proxy_host = credentials['proxy_url']
        proxy_port = credentials['proxy_port']
        if (credentials['proxy_username']):
            userAndPass = credentials['proxy_username'] + \
                ":" + credentials['proxy_password']
            userAndPass = b64encode(userAndPass.encode()).decode("ascii")
            headers['Proxy-Authorization'] = "Basic %s", userAndPass
        if (url.scheme == 'http'):
            port = url.port if url.port else 80
            conn = http.client.HTTPConnection(proxy_host, proxy_port)
        elif (url.scheme == 'https'):
            port = url.port if url.port else 443
            conn = http.client.HTTPSConnection(proxy_host, proxy_port)
        else:
            helper.log_error(
                "Invalid Scheme in URL %s", url.scheme)
            exit(2)
        conn.set_tunnel(url.netloc, port=port)
    else:
        if (url.scheme == 'http'):
            port = url.port if url.port else 80
            conn = http.client.HTTPConnection(url.hostname, port=port)
        elif (url.scheme == 'https'):
            port = url.port if url.port else 443
            conn = http.client.HTTPSConnection(url.hostname, port=port)
        else:
            helper.log_error(
                "Invalid Scheme in URL %s" % url.scheme)
            exit(2)
    return conn, headers

# Get a token from Thales Auth endpoint


def get_token(helper, ew, credentials):
    auth_request = {
        "client_id": credentials['client_id'],
        "client_secret": credentials['client_secret'],
        "grant_type": "client_credentials",
    }
    payload = urllib.parse.urlencode(auth_request)

    conn, headers = get_http_connection(
        helper, credentials['authentication_api_base'], credentials)
    headers['Accept'] = 'application/json'
    headers['Content-Type'] = 'application/x-www-form-urlencoded'
    try:
        conn.request("POST", "/oauth/token", payload, headers)
        res = conn.getresponse()
        if res.status != 200:
            error_message = "Failed getting HSM Bearer Token with response => %d : %s" % (
                res.status, res.reason)
            helper.log_error(error_message)
            send_status_event(helper, ew, error_message, "ERROR")
            exit(2)
        else:
            data = res.read()
            auth_data = json.loads(data.decode("utf-8"))
            credentials['Bearer'] = auth_data["access_token"]
            return auth_data["access_token"]
    except:
        error_message = "Error occurred on getting the Session token from Cloud AppSec portal. %s" % traceback.format_exc()
        helper.log_error(error_message)
        send_status_event(helper, ew, error_message, "ERROR")
        exit(2)

# This function uses the DPOD Audit Query API to collect logs from DPOD Cloud HSM
# Returns the location of the audit logs in the URL


def get_audit_logs(helper, ew, credentials, now, past):
    conn, headers = get_http_connection(helper,
                                        credentials['dpod_api_base'], credentials)
    headers['Accept'] = 'application/json'
    headers['Content-Type'] = 'application/json'
    headers['Authorization'] = "Bearer %s" % credentials['Bearer']
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
            helper.log_error(error_message)
            send_status_event(helper, ew, error_message, "ERROR")
            exit(2)
        else:
            data = res.read()
            response_data = json.loads(data.decode("utf-8"))
    except:
        error_message = "Error occurred on Starting and Audit Log Export from Thales %s" % traceback.format_exc()
        helper.log_error(error_message)
        send_status_event(helper, ew, error_message, "ERROR")
        exit(2)
    conn.close()

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
                helper.log_error(error_message)
                send_status_event(helper, ew, error_message, 'ERROR')
                exit(2)
            else:
                data = res.read()
                response_data = json.loads(data.decode("utf-8"))
        except:
            error_message = "Error occurred on retrieving Log Export from Thales %s" % traceback.format_exc()
            helper.log_error(error_message)
            send_status_event(helper, ew, error_message, 'ERROR')
            exit(2)
        conn.close()
        run_counter = run_counter+1
    return response_data

# Processes an audit log .gzip from DPOD Audit Query API
# Will aggregate settings depending on Configuration


def process_audit_log_events(helper, ew, credentials, url):
    conn, headers = get_http_connection(helper, url, credentials)
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
        if (credentials['aggregate_event_types'] and str(luna_evt['action']) in credentials['aggregate_event_types']):
            aggregate_key = str(luna_evt['action'])+":"+str(luna_evt['status'])+":"+str(
                luna_meta['clientip'])+":"+str(luna_meta['partid'])
            if aggregate_key in aggregate_events:
                aggregate_events[aggregate_key]['count'] += 1
                aggregate_events[aggregate_key]['end_time'] = str(round(datetime.datetime.strptime(
                    luna_evt['time'], thales_date_format).timestamp()))
            else:
                aggregate_events[aggregate_key] = {
                    'count': 1,
                    'original_event': luna_evt,
                    'original_meta': luna_meta,
                    'begin_time': str(round(datetime.datetime.strptime(
                        luna_evt['time'], thales_date_format).timestamp())),
                    'end_time': str(round(datetime.datetime.strptime(
                        luna_evt['time'], thales_date_format).timestamp()))
                }
        else:
            build_event = "_time=" + \
                str(round(datetime.datetime.strptime(
                    luna_evt['time'], thales_date_format).timestamp()))+","
            build_event = build_event + "resourceID=" + \
                str(luna_evt['resourceID'])+','
            build_event = build_event + "clientid=" + \
                str(credentials['client_id'])+','
            build_event = build_event + "actorID="+str(luna_evt['actorID'])+','
            build_event = build_event + "tenantID=" + \
                str(luna_evt['tenantID'])+','
            build_event = build_event + "action="+str(luna_evt['action'])+','
            build_event = build_event + "status="+str(luna_evt['status'])+','
            build_event = build_event + "clientip=" + \
                str(luna_meta['clientip'])+','
            build_event = build_event + "hsmid="+str(luna_meta['hsmid'])+','
            build_event = build_event + "partid="+str(luna_meta['partid'])+','
            event = helper.new_event(source=helper.get_input_type(), index=helper.get_output_index(
            ), sourcetype=helper.get_sourcetype(), data=build_event)
            ew.write_event(event)

    # Iterate through aggregated events and write to stream
    for agg_key in aggregate_events:
        luna_evt = aggregate_events[agg_key]['original_event']
        luna_meta = aggregate_events[agg_key]['original_meta']
        build_event = "_time=" + \
            str(round(datetime.datetime.strptime(
                luna_evt['time'], thales_date_format).timestamp()))+","
        build_event = build_event + "clientid=" + \
            str(credentials['client_id'])+','
        build_event = build_event + "resourceID=" + \
            str(luna_evt['resourceID'])+','
        build_event = build_event + "actorID="+str(luna_evt['actorID'])+','
        build_event = build_event + "tenantID=" + \
            str(luna_evt['tenantID'])+','
        build_event = build_event + "action="+str(luna_evt['action'])+','
        build_event = build_event + "status="+str(luna_evt['status'])+','
        build_event = build_event + "clientip=" + \
            str(luna_meta['clientip'])+','
        build_event = build_event + "hsmid="+str(luna_meta['hsmid'])+','
        build_event = build_event + "partid="+str(luna_meta['partid'])+','
        build_event = build_event + "count=" + \
            str(aggregate_events[agg_key]['count'])
        event = helper.new_event(source=helper.get_input_type(), index=helper.get_output_index(
        ), sourcetype=helper.get_sourcetype(), data=build_event)
        ew.write_event(event)


def send_status_event(helper, ew, message, status="INFO"):
    build_event = "_time=" + \
        str(round(datetime.datetime.now().timestamp())) + ","
    build_event = build_event + "clientid=" + \
        str(helper.get_arg('client_id'))+','
    build_event = build_event + "message=" + json.dumps(message)
    build_event = build_event + ",severity=" + status
    event = helper.new_event(source=helper.get_input_type(), index=helper.get_output_index(
    ), sourcetype=helper.get_sourcetype(), data=build_event)
    ew.write_event(event)


def validate_input(helper, definition):
    credentials = {
        "authentication_api_base": helper.get_arg('authentication_api_base'),
        "dpod_api_base": helper.get_arg('dpod_api_base'),
        "Bearer": "",
        "client_id": helper.get_arg('client_id'),
        "client_secret": helper.get_arg('client_secret'),
        "proximity": "",
        "use_proxy": False,
        "aggregate_event_types": []
    }
    pass


def collect_events(helper, ew):
    send_status_event(helper, ew, "Starting Log Collection from %s,client_id=%s" % (
        helper.get_arg('dpod_api_base'), helper.get_arg('client_id')))

    credentials = {
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
        credentials['aggregate_event_types'] = str(
            helper.get_arg('aggregate_event_types')).split(',')

    proxy_settings = helper.get_proxy()
    if (proxy_settings):
        credentials['use_proxy'] = True
        credentials['proxy_url'] = proxy_settings['proxy_url']
        credentials['proxy_port'] = proxy_settings['proxy_port']
        credentials['proxy_type'] = proxy_settings['proxy_type']
        credentials['proxy_username'] = proxy_settings['proxy_username']
        credentials['proxy_password'] = proxy_settings['proxy_password']
        credentials['proxy_rdns'] = proxy_settings['proxy_rdns']

    # Get the autherization token for the app using client_id and client_secret
    get_token(helper, ew, credentials)

    # Get time window to filter for logs
    now_checkpoint = str(round(time.time()))
    last_checkpoint = helper.get_check_point("last_run_%s" %
                                             helper.get_arg('client_id'))
    interval = int(helper.get_arg('interval'))

    now = int(round(time.time()))
    past = now - interval

    # Check the last run checkpoint if set and use that as the 'from' parameter to Thales.
    if last_checkpoint and ((past > int(last_checkpoint)) and ((now - int(last_checkpoint)) < 2591998)):
        past = datetime.datetime.fromtimestamp(
            int(last_checkpoint)).strftime(date_format)
    else:
        past = datetime.datetime.fromtimestamp(past).strftime(date_format)
    now = datetime.datetime.fromtimestamp(now).strftime(date_format)
    # Create an Audit Log export file
    audit_logs = get_audit_logs(helper, ew, credentials, now, past)

    # Process .gzip file into events
    process_audit_log_events(helper, ew, credentials, audit_logs['location'])

    send_status_event(helper, ew, "Luna HSM log processing completed.")
    # Save Checkpoint
    helper.save_check_point("last_run_%s" %
                            helper.get_arg('client_id'), now_checkpoint)
