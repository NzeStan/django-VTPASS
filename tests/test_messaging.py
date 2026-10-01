from decimal import Decimal
from urllib.parse import parse_qs, urlparse

import pytest

from tests.conftest import SMS_BASE
from vtpass.exceptions import SMSError, VTpassAuthenticationError, VTpassValidationError
from vtpass.messaging import MessagingClient, SMSResult
from vtpass.models import SMSMessage

OK = {
    "responseCode": "TG00", "response": "MESSAGE PROCESSED", "batchId": 5463323,
    "messages": [{"statusCode": "0000", "recipient": "2348031234567", "status": "SENT", "network": "MTNNG"}],
}


def test_v2_send_posts_form_with_headers(api):
    api.post(SMS_BASE + "v2/api/sms/sendsms", json=OK)
    result = MessagingClient().send(["0803 123 4567", "+2348021234567"], "Hello", dlr=True, client_batch_id="b1")
    assert result.ok and result.batch_id == "5463323" and result.delivered_to == ["2348031234567"]
    request = api.calls[0].request
    assert request.headers["X-Token"] == "VT_PK_test" and request.headers["X-Secret"] == "VT_SK_test"
    body = parse_qs(request.body)
    assert body["recipient"] == ["08031234567,08021234567"]
    assert body["sender"] == ["TestCo"] and body["dlr"] == ["1"] and body["clientbatchid"] == ["b1"]


@pytest.mark.parametrize(
    "route,path",
    [("dnd", "v2/api/sms/dnd-route"), ("dnd-fallback", "v2/api/sms/dnd-fallback")],
)
def test_v2_routes(api, route, path):
    api.post(SMS_BASE + path, json=OK)
    assert MessagingClient().send("08031234567", "Hi", route=route).ok


@pytest.mark.parametrize(
    "route,path",
    [
        ("normal", "api/sms/sendsms"),
        ("dnd", "api/sms/dnd-route"),
        ("dnd-fallback", "api/sms/dnd-fallback"),
        ("simhost", "api/sms/simhost-route"),
        ("simhost-fallback", "api/sms/simhost-fallback"),
    ],
)
def test_v1_routes_use_get(api, route, path):
    api.get(SMS_BASE + path, json=OK)
    MessagingClient(api_version=1).send("08031234567", "Hi", route=route, project_id="p1")
    query = parse_qs(urlparse(api.calls[0].request.url).query)
    assert query["responsetype"] == ["json"]
    if route.startswith("simhost"):
        assert query["projectId"] == ["p1"]


def test_text_response_parsing():
    result = SMSResult.parse(
        "TG00-MESSAGE PROCESSED:0000|2347061933309|1623425963075808467849264|SENT|"
        "MESSAGE SENT TO PROVIDER|MTNNG|NIGERIA"
    )
    assert result.ok and result.messages[0]["network"] == "MTNNG"


def test_rejections(api):
    api.post(SMS_BASE + "v2/api/sms/sendsms", json={"responseCode": "TG17", "response": "INSUFFICIENT BALANCE"})
    with pytest.raises(SMSError) as exc:
        MessagingClient().send("08031234567", "Hi")
    assert exc.value.code == "TG17"
    api.replace("POST", SMS_BASE + "v2/api/sms/sendsms", json={"responseCode": "TG11"})
    with pytest.raises(VTpassAuthenticationError):
        MessagingClient().send("08031234567", "Hi")


def test_validation():
    client = MessagingClient()
    with pytest.raises(VTpassValidationError):
        client.send("123", "Hi")
    with pytest.raises(VTpassValidationError):
        client.send("08031234567", "")
    with pytest.raises(VTpassValidationError):
        client.send("08031234567", "x" * 1000)


def test_balance(api):
    api.get(SMS_BASE + "api/sms/balance", body="256.21")
    assert MessagingClient().balance() == Decimal("256.21")


@pytest.mark.django_db
def test_sms_service_logs_messages(api, vt, user):
    api.post(SMS_BASE + "v2/api/sms/sendsms", json=OK)
    vt.sms.send("08031234567,08031234567", "Hello", user=user, purpose="otp")
    record = SMSMessage.objects.get()
    assert record.recipient_count == 1 and record.batch_id == "5463323" and record.purpose == "otp"

    api.replace("POST", SMS_BASE + "v2/api/sms/sendsms", json={"responseCode": "TG17"})
    with pytest.raises(SMSError):
        vt.sms.send("08031234567", "Hello")
    assert SMSMessage.objects.filter(state=SMSMessage.FAILED).count() == 1
