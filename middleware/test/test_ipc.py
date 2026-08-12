import pytest

from hie_middleware.ipc import IpcContractError, IpcRequest, IpcResponse


def test_ipc_request_round_trips_as_a_versioned_json_safe_envelope():
    request = IpcRequest("req-1", "notify", {"message": "ready"})
    assert IpcRequest.from_dict(request.to_dict()) == request
    assert request.to_dict()["version"] == 1


def test_ipc_response_requires_explicit_error_details():
    response = IpcResponse("req-1", "ok", {"accepted": True})
    assert IpcResponse.from_dict(response.to_dict()) == response
    with pytest.raises(IpcContractError, match="error responses"):
        IpcResponse("req-1", "error")


@pytest.mark.parametrize(
    "value",
    [
        {"request_id": "req", "method": "unknown"},
        {"request_id": "req", "method": "notify", "version": 99},
        {"request_id": "", "method": "notify"},
    ],
)
def test_ipc_request_rejects_unsupported_or_malformed_envelopes(value):
    with pytest.raises(IpcContractError):
        IpcRequest.from_dict(value)
