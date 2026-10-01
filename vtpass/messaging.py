"""
Client for the VTpass Messaging API (bulk SMS) at ``messaging.vtpass.com``.

Messaging uses its own key pair (``X-Token`` / ``X-Secret``) from the
Messaging dashboard, configured under ``VTPASS["MESSAGING"]``.

    from vtpass.messaging import MessagingClient

    sms = MessagingClient()
    result = sms.send("08012345678,08098765432", "Your OTP is 123456", sender="MyBrand")
    result.ok, result.batch_id, result.messages
    sms.balance()

Routes: ``normal``, ``dnd``, ``dnd-fallback``, ``simhost``, ``simhost-fallback``.
API version 2 (POST, form encoded) is used where VTpass offers it; SIMHOST
routes only exist as version 1 (GET).
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Union

from vtpass.client import BaseHTTPClient
from vtpass.constants import SMSMessageStatus, SMSResponseCode, SMSRoute
from vtpass.exceptions import SMSError, VTpassAuthenticationError, VTpassConfigError, VTpassValidationError
from vtpass.logger import log_response
from vtpass.settings import vtpass_settings
from vtpass.utils import normalize_phone, to_decimal

ROUTE_PATHS = {
    SMSRoute.NORMAL: "sendsms",
    SMSRoute.DND: "dnd-route",
    SMSRoute.DND_FALLBACK: "dnd-fallback",
    SMSRoute.SIMHOST: "simhost-route",
    SMSRoute.SIMHOST_FALLBACK: "simhost-fallback",
}
V2_ROUTES = {SMSRoute.NORMAL, SMSRoute.DND, SMSRoute.DND_FALLBACK}
MAX_MESSAGE_LENGTH = 918  # 6 concatenated pages


@dataclass
class SMSResult:
    raw: Any
    response_code: str = ""
    response: str = ""
    batch_id: Optional[str] = None
    messages: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.response_code == SMSResponseCode.PROCESSED

    @property
    def delivered_to(self) -> List[str]:
        good = {SMSMessageStatus.SENT, SMSMessageStatus.DELIVERED, SMSMessageStatus.DND_SENT}
        return [m.get("recipient") for m in self.messages if str(m.get("statusCode")) in good]

    @property
    def rejected(self) -> List[Dict[str, Any]]:
        bad = {SMSMessageStatus.REJECTED, SMSMessageStatus.DND_REJECTED}
        return [m for m in self.messages if str(m.get("statusCode")) in bad]

    @classmethod
    def parse(cls, body):
        if isinstance(body, dict):
            return cls(
                raw=body,
                response_code=str(body.get("responseCode", "")),
                response=str(body.get("response", "")),
                batch_id=str(body["batchId"]) if body.get("batchId") is not None else None,
                messages=list(body.get("messages") or []),
            )
        # Text format: "TG00-MESSAGE PROCESSED:0000|234...|msgid|SENT|...|MTNNG|NIGERIA,..."
        text = str(body or "").strip()
        head, _, rest = text.partition(":")
        code, _, description = head.partition("-")
        messages = []
        for chunk in filter(None, rest.split(",")):
            parts = chunk.split("|")
            if len(parts) >= 4:
                messages.append({
                    "statusCode": parts[0], "recipient": parts[1], "messageId": parts[2],
                    "status": parts[3], "description": parts[4] if len(parts) > 4 else "",
                    "network": parts[5] if len(parts) > 5 else "",
                })
        return cls(raw=text, response_code=code.strip(), response=description.strip(), messages=messages)


class MessagingClient(BaseHTTPClient):
    def __init__(self, public_key=None, secret_key=None, base_url=None, api_version=None, **kwargs):
        config = vtpass_settings.MESSAGING
        self.public_key = public_key if public_key is not None else config["PUBLIC_KEY"]
        self.secret_key = secret_key if secret_key is not None else config["SECRET_KEY"]
        self.api_version = int(api_version or config.get("API_VERSION") or 2)
        super().__init__(base_url or vtpass_settings.messaging_base_url, **kwargs)

    def _headers(self):
        if not (self.public_key and self.secret_key):
            raise VTpassConfigError(
                "VTPASS['MESSAGING']['PUBLIC_KEY'] and ['SECRET_KEY'] are required for SMS."
            )
        return {"X-Token": self.public_key, "X-Secret": self.secret_key, "Accept": "application/json"}

    @staticmethod
    def format_recipients(recipients: Union[str, Iterable[str]]) -> str:
        if isinstance(recipients, str):
            recipients = recipients.split(",")
        cleaned = []
        for number in recipients:
            digits = normalize_phone(number)
            if len(digits) < 11:
                raise VTpassValidationError(f"Invalid recipient number: {number!r}")
            if digits not in cleaned:
                cleaned.append(digits)
        if not cleaned:
            raise VTpassValidationError("At least one recipient is required.")
        return ",".join(cleaned)

    def send(
        self,
        recipients,
        message,
        sender=None,
        route=None,
        api_version=None,
        dlr=None,
        client_batch_id=None,
        project_id=None,
        raise_on_error=True,
    ) -> SMSResult:
        """
        Send an SMS to one or many recipients (list or comma separated string).

        ``route`` picks the delivery route; DND routes reach numbers on the
        Do-Not-Disturb list at a higher price. ``dlr``/``client_batch_id`` are
        v2 features, ``project_id`` is for SIMHOST routes.
        """
        config = vtpass_settings.MESSAGING
        route = SMSRoute(route or config["DEFAULT_ROUTE"])
        sender = sender or config["DEFAULT_SENDER"]
        if not sender:
            raise VTpassValidationError("An SMS sender ID is required.")
        if not message or not str(message).strip():
            raise VTpassValidationError("The SMS message cannot be empty.")
        if len(message) > MAX_MESSAGE_LENGTH:
            raise VTpassValidationError(f"The SMS message is longer than {MAX_MESSAGE_LENGTH} characters.")

        version = int(api_version or self.api_version)
        if route not in V2_ROUTES:
            version = 1
        params = {
            "sender": sender,
            "recipient": self.format_recipients(recipients),
            "message": message,
            "responsetype": "json",
        }
        if project_id and route in (SMSRoute.SIMHOST, SMSRoute.SIMHOST_FALLBACK):
            params["projectId"] = project_id
        if version == 2:
            if dlr is not None:
                params["dlr"] = "1" if dlr else "0"
            if client_batch_id:
                params["clientbatchid"] = client_batch_id
            path = f"v2/api/sms/{ROUTE_PATHS[route]}"
            response, elapsed = self._send("POST", path, self._headers(), data=params)
        else:
            path = f"api/sms/{ROUTE_PATHS[route]}"
            response, elapsed = self._send("GET", path, self._headers(), params=params)

        result = SMSResult.parse(_body(response))
        log_response(response.request.method, path, response.status_code, result.raw, elapsed)
        if response.status_code in (401, 403) or result.response_code == "TG11":
            raise VTpassAuthenticationError("VTpass Messaging rejected the credentials.", response=result.raw)
        if raise_on_error and not result.ok:
            raise SMSError(
                SMSResponseCode.DESCRIPTIONS.get(result.response_code, result.response or "SMS rejected"),
                code=result.response_code, response=result.raw,
            )
        return result

    def balance(self) -> Decimal:
        """Remaining SMS units."""
        response, _ = self._send("GET", "api/sms/balance", self._headers())
        body = _body(response)
        if isinstance(body, dict):
            body = body.get("balance", body.get("data"))
        value = to_decimal(body)
        if value is None:
            raise SMSError("Could not read the SMS unit balance.", response=body)
        return value


def _body(response):
    try:
        return response.json()
    except ValueError:
        return response.text
