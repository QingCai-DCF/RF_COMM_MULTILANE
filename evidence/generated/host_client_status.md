# Host Client Offline Status

HOST_CLIENT_PROTOCOL_ENCODING=PASS
HOST_CLIENT_STATUS_RESPONSE=PASS
HOST_CLIENT_ERROR_EVENT=PASS
HOST_CLIENT_RECONNECT_STATE_MACHINE=PASS
HOST_CLIENT_TRANSPORT_DROP_RETRY=PASS
HOST_CLIENT_REAL_ETHERNET=PENDING_HW
NO_HARDWARE_ACTIONS_EXECUTED=1

`software/host_client/test_protocol_contract.py` covers packet
encode/decode, status and shutdown responses, error responses, initial connect
retry, transport-drop retry, and event recording through the offline mock
transport. No real Ethernet or hardware path is used.
