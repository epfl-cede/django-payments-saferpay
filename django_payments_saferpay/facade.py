import json
import base64
from tracemalloc import Trace
import warnings
import requests
import uuid
from typing import Optional
from decimal import Decimal
from typing import Any, Dict, Tuple
from dataclasses import asdict, dataclass

from django.db import transaction
from django.db.models.functions import Reverse
from django.db.models.options import Options
from django.utils.http import re
from django.utils.translation import gettext_lazy as _
from django.urls import reverse

from payments import FraudStatus, PaymentError, PaymentStatus
from payments.models import BasePayment
from requests.sessions import Request

from . import __version__ as version

SAFER_PAY_SPEC_VERSION = "1.45"


class SaferpayTransactionStatus:
    AUTHORIZED = "AUTHORIZED"
    CANCELED = "CANCELED"
    CAPTURED = "CAPTURED"
    PENDING = "PENDING"


@dataclass
class SaferpayPaymentInitializeResponse:
    """Data class representing a validated SaferPay payment initialize response."""

    request_id: str
    token: str
    redirect_url: str

    @classmethod
    def from_api_response(
        cls, response_data: dict
    ) -> "SaferpayPaymentInitializeResponse":
        """
        Create a SaferpayPaymentInitializeResponse from the API response dictionary.
        Validates that all required fields are present.

        Raises:
            PaymentError: If the response is invalid or missing required fields.
        """

        # Get the request ID from the response header
        request_id = response_data.get("ResponseHeader", {}).get("RequestId", "")
        if not request_id:
            raise PaymentError(_("Missing RequestId in SaferPay response"))

        # Verify the response contains the expected fields
        if not all(key in response_data for key in ["Token", "RedirectUrl"]):
            raise PaymentError(_("Invalid response from SaferPay"))

        return cls(
            request_id=request_id,
            token=response_data["Token"],
            redirect_url=response_data["RedirectUrl"],
        )

    def to_dict(self) -> dict:
        """Convert the response object to a dictionary."""
        return asdict(self)


@dataclass
class SaferpayPaymentAssertResponse:
    """Data class representing a validated SaferPay payment assert response."""

    request_id: str
    transaction_id: str
    transaction_status: str
    capture_id: str

    @classmethod
    def from_api_response(cls, response_data: dict) -> "SaferpayPaymentAssertResponse":
        """
        Create a SaferpayPaymentAssertResponse from the API response dictionary.
        Validates that all required fields are present.

        Raises:
            PaymentError: If the response is invalid or missing required fields.
        """
        # Get the request ID from the response header
        request_id = response_data.get("ResponseHeader", {}).get("RequestId", "")
        if not request_id:
            raise PaymentError(_("Missing RequestId in SaferPay response"))

        # Unique Saferpay transaction id. Used to reference the transaction in any further step.
        transaction_id = response_data.get("Transaction", {}).get("Id", "")
        if not transaction_id:
            raise PaymentError(_("Missing Transaction.Id in SaferPay response"))

        # Current status of the transaction. One of 'AUTHORIZED', 'CANCELED', 'CAPTURED' or 'PENDING'
        transaction_status = response_data.get("Transaction", {}).get("Status", "")
        if not transaction_status:
            raise PaymentError(_("Missing Transaction.Status in SaferPay response"))

        # Unique Saferpay capture id.
        # Available if the transaction was already captured (Status: CAPTURED).
        # Must be stored for later reference (eg refund).
        capture_id = response_data.get("Transaction", {}).get("CaptureId", "")

        return cls(
            request_id=request_id,
            transaction_id=transaction_id,
            transaction_status=transaction_status,
            capture_id=capture_id,
        )

    def to_dict(self) -> dict:
        """Convert the response object to a dictionary."""
        return asdict(self)


@dataclass
class SaferpayTransactionCaptureResponse:
    """Data class representing a validated SaferPay transaction capture response."""

    request_id: str
    status: str

    @classmethod
    def from_api_response(
        cls, response_data: dict
    ) -> "SaferpayTransactionCaptureResponse":
        """
        Create a SaferpayTransactionCaptureResponse from the API response dictionary.
        Validates that all required fields are present.

        Raises:
            PaymentError: If the response is invalid or missing required fields.
        """
        # Get the request ID from the response header
        request_id = response_data.get("ResponseHeader", {}).get("RequestId", "")
        if not request_id:
            raise PaymentError(_("Missing RequestId in SaferPay response"))

        # Current status of the capture. (PENDING is only used for paydirekt at the moment)
        status = response_data.get("Status", "")

        return cls(
            request_id=request_id,
            status=status,
        )

    def to_dict(self) -> dict:
        """Convert the response object to a dictionary."""
        return asdict(self)


class Facade:
    """
    Interface between Django payments and SaferPay.

    In this class, all functionality that actually touches SaferPay is implemented.
    """

    client: requests.Session

    def __init__(
        self,
        customer_id: str,
        terminal_id: str,
        auth_username: str,
        auth_password: str,
        sandbox: bool,
    ) -> None:
        self.customer_id: str = customer_id
        self.terminal_id: str = terminal_id
        self.auth_username: str = auth_username
        self.auth_password: str = auth_password
        if sandbox:
            self.base_url = "https://test.saferpay.com/api/Payment/v1"
        else:
            self.base_url = "https://www.saferpay.com/api/Payment/v1"

        self.client = requests.Session()
        self.client.headers["User-Agent"] = f"Django Payments SaferPay {version}"
        self.client.headers["Authorization"] = (
            f"Basic {base64.b64encode(f'{self.auth_username}:{self.auth_password}'.encode()).decode()}"
        )

    def payment_initialize(
        self, payment: BasePayment, return_url: str
    ) -> SaferpayPaymentInitializeResponse:
        """Create a new payment at SaferPay."""
        if payment.transaction_id:
            raise PaymentError(_("This payment has already been processed"))

        # Validate required fields
        self._validate_payment_initialize_fields(payment)

        # Generate a unique UUID for the request
        request_id = self._generate_request_id()

        # Prepare request
        payload = self._generate_payment_initialize_payload(
            payment, return_url, request_id
        )
        initialize_url = f"{self.base_url}/PaymentPage/Initialize"
        # Initialize response outside try block, otherwise pyright get warning
        response = None

        try:
            response = self.client.post(url=initialize_url, json=payload)
            response.raise_for_status()  # Raise exception for bad HTTP status
            payment_data = response.json()

            # Verify that the response contains our request ID
            response_header = payment_data.get("ResponseHeader", {})
            response_request_id = response_header.get("RequestId")

            if response_request_id != request_id:
                raise PaymentError(
                    _("SaferPay response RequestId doesn't match our request"),
                    gateway_message=f"Expected {request_id}, got {response_request_id}",
                )

            return SaferpayPaymentInitializeResponse.from_api_response(payment_data)

        except requests.HTTPError as e:
            # Handle HTTP error
            if response is not None:
                error_data = self._parse_error_response(response)
                error_message = error_data["message"]
            else:
                error_message = str(e)

            raise PaymentError(
                _("Failed to create payment at SaferPay"),
                gateway_message=error_message,
            )
        except json.JSONDecodeError:
            # Handle invalid JSON response
            raise PaymentError(
                _("Failed to parse the response from SaferPay"),
                gateway_message="Invalid JSON response",
            )
        except requests.RequestException as e:
            # Handle case where the request fails to send (no response)
            raise PaymentError(
                _("Failed to connect to SaferPay"), gateway_message=str(e)
            )
        except PaymentError:
            # Pass through PaymentError from response validation
            raise

    def payment_assert(self, payment: BasePayment) -> SaferpayPaymentAssertResponse:
        """
        Depending on the payment provider, the resulting transaction may either be an authorization or may already
        be captured (meaning the financial flow was already triggered). This will be visible in the status of the
        transaction container returned in the response.
        This function can be called up to 24 hours after the transaction was initialized. For pending transaction
        the token expiration is increased to 120 hours.
        If the transaction failed (the payer was redirected to the Fail url or he manipulated the return url), an
        error response with an http status code 400 or higher containing an error message will be returned providing
        some information on the transaction failure.
        """
        if not payment.transaction_id:
            raise PaymentError(_("This payment has already been processed"))

        # Validate required fields
        self._validate_payment_assert_fields(payment)

        # Generate a unique UUID for the request
        request_id = self._generate_request_id()

        # Prepare request
        payload = self._generate_payment_assert_payload(payment, request_id)
        assert_url = f"{self.base_url}/PaymentPage/Assert"
        # Initialize response outside try block, otherwise pyright get warning
        response = None

        try:
            response = self.client.post(url=assert_url, json=payload)
            response.raise_for_status()  # Raise exception for bad HTTP status
            payment_data = response.json()

            # Verify that the response contains our request ID
            response_header = payment_data.get("ResponseHeader", {})
            response_request_id = response_header.get("RequestId")

            if response_request_id != request_id:
                raise PaymentError(
                    _("SaferPay response RequestId doesn't match our request"),
                    gateway_message=f"Expected {request_id}, got {response_request_id}",
                )

            return SaferpayPaymentAssertResponse.from_api_response(payment_data)

        except requests.HTTPError as e:
            # Handle HTTP error
            if response is not None:
                error_data = self._parse_error_response(response)
                error_message = error_data["message"]
            else:
                error_message = str(e)

            raise PaymentError(
                _("Failed to assert payment at SaferPay"),
                gateway_message=error_message,
            )
        except json.JSONDecodeError:
            # Handle invalid JSON response
            raise PaymentError(
                _("Failed to parse the response from SaferPay"),
                gateway_message="Invalid JSON response",
            )
        except requests.RequestException as e:
            # Handle case where the request fails to send (no response)
            raise PaymentError(
                _("Failed to connect to SaferPay"), gateway_message=str(e)
            )
        except PaymentError:
            # Pass through PaymentError from response validation
            raise

    def transaction_capture(self, payment: BasePayment, transaction_id: str):
        """Capture a transaction."""
        request_id = self._generate_request_id()
        payload = self._generate_transaction_capture_payload(
            payment, transaction_id, request_id
        )
        call_url = f"{self.base_url}/Transaction/Capture"
        # Initialize response outside try block, otherwise pyright get warning
        response = None

        try:
            response = self.client.post(url=call_url, json=payload)
            response.raise_for_status()  # Raise exception for bad HTTP status
            payment_data = response.json()

            # Verify that the response contains our request ID
            response_header = payment_data.get("ResponseHeader", {})
            response_request_id = response_header.get("RequestId")

            if response_request_id != request_id:
                raise PaymentError(
                    _("SaferPay response RequestId doesn't match our request"),
                    gateway_message=f"Expected {request_id}, got {response_request_id}",
                )

            return SaferpayTransactionCaptureResponse.from_api_response(payment_data)

        except requests.HTTPError as e:
            # Handle HTTP error
            if response is not None:
                error_data = self._parse_error_response(response)
                error_message = error_data["message"]
            else:
                error_message = str(e)

            raise PaymentError(
                _("Failed to assert payment at SaferPay"),
                gateway_message=error_message,
            )
        except json.JSONDecodeError:
            # Handle invalid JSON response
            raise PaymentError(
                _("Failed to parse the response from SaferPay"),
                gateway_message="Invalid JSON response",
            )
        except requests.RequestException as e:
            # Handle case where the request fails to send (no response)
            raise PaymentError(
                _("Failed to connect to SaferPay"), gateway_message=str(e)
            )
        except PaymentError:
            # Pass through PaymentError from response validation
            raise

    def _generate_request_id(self):
        return str(uuid.uuid4())

    def _generate_payment_request_header(self, request_id: str):
        return {
            "CustomerId": self.customer_id,
            "RequestId": request_id,
            "RetryIndicator": 0,
            "SpecVersion": SAFER_PAY_SPEC_VERSION,
        }

    def _generate_payment_initialize_payload(
        self,
        payment: BasePayment,
        return_url: str,
        request_id: str,
    ) -> Dict[str, Any]:
        """Generate the payload for a new SaferPay payment initialize request."""
        payload = {
            "RequestHeader": self._generate_payment_request_header(request_id),
            "Payment": {
                "Amount": {
                    # ISO 4217 3-letter currency code (CHF, USD, EUR, ...)
                    "CurrencyCode": payment.currency,
                    # Amount in minor unit (CHF 1.00 ⇒ Value=100). Only Integer values will be accepted!
                    "Value": int(float(str(payment.total)) * 100),
                },
                # A human readable description provided by the merchant that will be displayed in Payment Page.
                "Description": payment.description,
                # Unambiguous order identifier defined by the merchant / shop. This identifier might be used as reference later on.
                # For PosftFinance it is restricted to a maximum of 18 characters and to an alphanumeric format
                "OrderId": payment.pk,
            },
            "ReturnUrl": {
                "Url": return_url,
            },
            # GET-method to handle async notifications from SaferPay
            # not mandatory
            "Notification": {
                "FailNotifyUrl": payment.get_failure_url(),
                "SuccessNotifyUrl": payment.get_success_url(),
            },
            "TerminalId": self.terminal_id,
        }

        return payload

    def _generate_payment_assert_payload(
        self,
        payment: BasePayment,
        request_id: str,
    ) -> Dict[str, Any]:
        """Generate the payload for a new SaferPay payment assert request."""
        payload = {
            "RequestHeader": self._generate_payment_request_header(request_id),
            "Token": payment.transaction_id,
        }

        return payload

    def _generate_transaction_capture_payload(
        self,
        payment: BasePayment,
        transaction_id: str,
        request_id: str,
    ) -> Dict[str, Any]:
        """Generate the payload for a new SaferPay transaction capture request."""
        payload = {
            "RequestHeader": self._generate_payment_request_header(request_id),
            "TransactionReference": {
                "TransactionId": transaction_id,
            },
        }

        return payload

    def _validate_payment_initialize_fields(self, payment: BasePayment) -> None:
        """Validate that the payment has all required fields."""
        if not payment.currency:
            raise ValueError("The payment has no currency, but it is required")
        if not payment.total:
            raise ValueError("The payment has no total amount, but it is required")
        if not payment.description:
            raise ValueError("The payment has no description, but it is required")

    def _validate_payment_assert_fields(self, payment: BasePayment) -> None:
        """Validate that the payment has all required fields."""
        if not payment.transaction_id:
            raise ValueError("The payment has no transaction ID, but it is required")

    def _parse_error_response(self, response: Optional[requests.Response]) -> dict:
        """Extract error details from a SaferPay error response."""
        if response is None:
            return {
                "message": "No response received from SaferPay",
            }

        try:
            json_response = response.json()
            error_message = json_response.get("ErrorMessage", "Unknown Error")
            error_detail = json_response.get("ErrorDetail", "Unknown Detail")
            return {
                "message": f"{error_message=} {error_detail=}",
            }
        except json.JSONDecodeError:
            return {
                "message": _("Failed to parse the response from SaferPay"),
            }
