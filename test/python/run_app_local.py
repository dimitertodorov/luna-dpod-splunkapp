import os
import sys
from urllib.parse import urlsplit
from stub_helper import StubHelper, StubEw
current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
pathname = os.path.abspath(parent + "../../TA-luna-hsm-audit-logger/bin")
print(os.path.abspath(parent + "../../TA-luna-hsm-audit-logger/bin"))
sys.path.append(pathname)
import input_module_luna_hsm_audit_log
helper = StubHelper()
ew = StubEw()

input_module_luna_hsm_audit_log.collect_events(helper,ew)