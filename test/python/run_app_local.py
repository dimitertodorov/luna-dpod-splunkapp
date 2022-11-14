import os
import sys
from urllib.parse import urlsplit
from stub_helper import StubHelper, StubEw, StubDefinition
current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
pathname = os.path.abspath(parent + "../../TA-luna-hsm-audit-logger/bin")
print(os.path.abspath(parent + "../../TA-luna-hsm-audit-logger/bin"))
sys.path.append(pathname)
import input_module_luna_hsm_audit_log
helper = StubHelper()
definition = StubDefinition()
ew = StubEw()
input_module_luna_hsm_audit_log.validate_input(helper, definition)
input_module_luna_hsm_audit_log.collect_events(helper,ew)