from hie_middleware.contracts import EditRequest, OperationResult


def test_contracts_are_serializable():
    request = EditRequest("preview", "document-1", {"strength": 0.5})
    result = OperationResult("request-1", "completed", request.document_id)

    assert request.parameters["strength"] == 0.5
    assert result.to_dict()["status"] == "completed"
