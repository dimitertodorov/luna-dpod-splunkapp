import datetime
import gzip
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import pathlib
from socketserver import ThreadingMixIn
import ssl
import threading
import argparse
import re
import urllib
import uuid

client_id = b""
client_secret = b""


class LocalData(object):
    records = {}
    jobs = {}


class HsmEventMeta:
    sample_meta = {"clientip": "10.0.0.1", "hsmid": "61112",
                   "partid": "4444049524932", "role": "CO"}

    def __init__(self, clientip: str = "10.0.0.1", hsmid: str = "61112", partid: str = "4444049524932", role: str = "CO"):
        self.clientip = clientip
        self.hsmid = hsmid
        self.partid = partid
        self.role = role


class HsmEvent:
    thales_date_format = "%Y-%m-%d %H:%M:%S %Z"
    sample_event = {
        "time": "2022-10-30 14:52:47 UTC",
        "source": "thales/cloudhsm/1334049524932",
        "resourceID": "f59a597b-19b9-41df-b479-1530ed60fca3",
        "actorID": "d5fa3ace-a79f-40ba-8e21-3ebf0bf0250a",
        "tenantID": "b863768a-9b90-4a6a-b8ec-01a7b46a6ca3",
        "action": "LUNA_LOGIN",
        "status": "LUNA_RET_OK",
        "traceID": "_PQejsfbmmiohSUzOMs5hvJehlrkVxdSopjdrZSx30A",
        "meta": {"clientip": "10.0.0.1", "hsmid": "567782", "partid": "1334049524932", "role": "CO"}
    }

    def __init__(self, action: str, status: str, eventTime: datetime = datetime.datetime.now(datetime.timezone.utc), meta: HsmEventMeta = HsmEventMeta()):
        self.time = eventTime.strftime(HsmEvent.thales_date_format)
        self.source = HsmEvent.sample_event['source']
        self.resourceID = HsmEvent.sample_event['resourceID']
        self.actorID = HsmEvent.sample_event['actorID']
        self.tenantID = HsmEvent.sample_event['tenantID']
        self.action = action
        self.status = status
        self.traceID = HsmEvent.sample_event['traceID']
        self.meta = meta

    def toJSON(self):
        attrs = self.__dict__
        attrs['meta'] = json.dumps(self.meta.__dict__)
        return json.dumps(attrs)


def generate_sample_events(begin: datetime.datetime, end: datetime.datetime = datetime.datetime.now()) -> list[HsmEvent]:
    total_seconds = int(end.timestamp() - begin.timestamp())
    events = []
    required_events = int(total_seconds/5)
    if required_events > 600:
        required_events = 400
    event_interval = int(total_seconds / required_events)
    event_date = datetime.datetime.fromtimestamp(
        (begin.timestamp()), datetime.timezone.utc)
    for i in range(required_events):
        events.append(HsmEvent("LUNA_LOGIN", "LUNA_RET_OK", event_date))
        event_date = datetime.datetime.fromtimestamp(
            (event_date.timestamp() + event_interval), datetime.timezone.utc)

    return events


class HTTPRequestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if None != re.search('/oauth/token*', self.path):
            ctype = self.headers.get_all('content-type')
            if ctype:
                ctype = self.headers.get_all('content-type')[0]
                if ctype == 'application/x-www-form-urlencoded':
                    length = int(self.headers.get_all('content-length')[0])
                    data = dict(urllib.parse.parse_qs(
                        self.rfile.read(length), encoding='utf-8'))

                    if ((data[b"client_id"][0] != client_id) | (data[b'client_secret'][0] != client_secret)):
                        self.send_response(401)
                        self.end_headers()
                    else:
                        jdata = json.dumps({
                            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.mNQasHSre8hFeCMWElRUUdLE-EtXThIxH9H88cYczKE",
                            "token_type": "bearer",
                            "expires_in": 3599,
                            "scope": "dpod.tuid.7a057e19-9a92-4f94-8caa-157ab9d8ccb7 dpod.tenant.api_appowner dpod.tuid.7a057e19-9a92-4f94-8caa-157ab9d8ccb7.sguid.32b32507-d04b-4c41-af3f-ce4a9d87bbb8",
                            "jti": "ea42115b8b6e4309bfc9b4104cd85885"
                        })
                        jdata = jdata.encode(encoding='utf8')
                        self.send_response(200)
                        self.send_header('content-length', len(jdata))
                        self.send_header('content-type', 'application/json')
                        self.end_headers()
                        self.wfile.write(jdata)
                else:
                    self.send_response(400)
                    self.end_headers()
            else:
                self.send_response(400)
                self.end_headers()
                data = {}
        elif None != re.search('/v1/audit-log-exports*', self.path):
            ctype = self.headers.get_all('content-type')
            if ctype:
                ctype = self.headers.get_all('content-type')[0]
                if ctype == 'application/json':
                    length = int(self.headers.get_all('content-length')[0])
                    data = self.rfile.read(length)
                    data = json.loads(data)
                    fromDate = datetime.datetime.strptime(
                        data['from'], "%Y-%m-%dT%H:%M:%SZ")
                    toDate = datetime.datetime.strptime(
                        data['to'], "%Y-%m-%dT%H:%M:%SZ")
                    evts = generate_sample_events(fromDate, toDate)
                    eventOutput = ""
                    for evt in evts:
                        eventOutput += "%s\n" % evt.toJSON()
                    content = gzip.compress(eventOutput.encode('utf8'))
                    jobId = str(uuid.uuid4())
                    LocalData.jobs[jobId] = content
                    startedAt = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
                    jdata = json.dumps({"jobId": jobId,
                                       "startedAt": startedAt, "endedAt": None, "state": "ACTIVE", "location": None})
                    jdata = jdata.encode(encoding='utf8')
                    self.send_response(201)
                    self.send_header('content-length', len(jdata))
                    self.send_header('content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(jdata)
                else:
                    self.send_response(400)
                    self.end_headers()
            else:
                self.send_response(400)
                self.end_headers()
                data = {}
        else:
            self.send_response(403)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
        return

    def do_GET(self):
        if None != re.search('/v1/audit-log-exports/*', self.path):
            jobId = self.path.split('/')[-1]
            jobData = LocalData.jobs[jobId]
            hostHeader = self.headers.get_all('Host')[0]
            if jobData:
                startedAt = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
                location = "https://%s/export_files/%s" % (hostHeader, jobId)
                jdata = json.dumps({"jobId": jobId,
                                    "startedAt": startedAt, "endedAt": None, "state": "SUCCEEDED", "location": location})
                jdata = jdata.encode(encoding='utf8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('content-length', len(jdata))
                self.end_headers()
                self.wfile.write(jdata)
            else:
                self.send_response(400)
                self.end_headers()
        elif None != re.search('/export_files/*', self.path):
            jobId = self.path.split('/')[-1]
            jobId = jobId.replace('?', '')
            jobData = LocalData.jobs[jobId]
            if jobData:
                self.send_response(200)
                self.send_header('Content-Type', 'application/octet-stream')
                self.send_header('content-length', len(jobData))
                self.end_headers()
                self.wfile.write(jobData)
            else:
                self.send_response(400)
                self.end_headers()
        elif None != re.search('/ping', self.path):
            pingReply = "OK"
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.send_header('content-length', len(pingReply))
            self.end_headers()
            self.wfile.write(pingReply.encode("utf8"))
        else:
            self.send_response(403)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
        return


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    allow_reuse_address = True

    def shutdown(self):
        self.socket.close()
        HTTPServer.shutdown(self)


class SimpleHttpServer():
    def __init__(self, ip, port):
        # Resolve SSL Certificates
        current = os.path.dirname(os.path.realpath(__file__))
        parent = pathlib.Path(current).absolute()
        ssl_path = pathlib.Path(parent) / 'ssl'
        cert_path = ssl_path / 'lunatest.mock.pem'
        key_path = ssl_path / 'lunatest.mock.key'
        self.server = ThreadedHTTPServer((ip, port), HTTPRequestHandler)
        self.ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.ssl_context.load_cert_chain(cert_path, key_path)

    def start(self):
        self.server.socket = self.ssl_context.wrap_socket(
            self.server.socket, server_side=True)
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()

    def waitForThread(self):
        self.server_thread.join()

    def addRecord(self, recordID, jsonEncodedRecord):
        LocalData.records[recordID] = jsonEncodedRecord

    def stop(self):
        self.server.shutdown()
        self.waitForThread()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='HTTP Server')
    parser.add_argument(
        '--port', type=int, help='Listening port for HTTP Server', default="8084", required=False)
    parser.add_argument('--ip', help='HTTP Server IP',
                        default="0.0.0.0", required=False)
    parser.add_argument(
        '--client_id', help='client_id for token endpoint', default="thisisnotreal", required=False)
    parser.add_argument(
        '--client_secret', help='client_secret for token endpoint', default="somesecret", required=False)

    args = parser.parse_args()
    client_id = str(args.client_id).encode("utf8")
    client_secret = str(args.client_secret).encode("utf8")
    server = SimpleHttpServer(args.ip, args.port)
    print('HTTP Server Running...........')
    server.start()
    server.waitForThread()
