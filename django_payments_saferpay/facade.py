import base64
import json
import logging
import uuid
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

import requests
from django.utils.translation import gettext_lazy as _
from payments import PaymentError
from payments.models import BasePayment

from . import __version__ as version

SAFER_PAY_SPEC_VERSION = "1.45"
logger = logging.getLogger(__name__)


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


@dataclass
class SaferpayErrorResponse:
    """Data class representing a SaferPay API error response."""

    message: str = "Unknown error message"
    name: str = "Unknown error name"
    detail: str = "Unknown error detail"
    code: Optional[int] = None

    @classmethod
    def from_response(
        cls, response: Optional[requests.Response]
    ) -> "SaferpayErrorResponse":
        """
        Create a SaferpayErrorResponse from an HTTP response.

        Args:
            response: The HTTP response from SaferPay API

        Returns:
            A structured error response object
        """
        # Double check if response is None
        if response is None:
            return cls(message="No response received from SaferPay")

        try:
            json_response = response.json()
            logger.error(f"SaferPay error response: {json_response}")

            return cls(
                message=json_response.get("ErrorMessage", "Unknown error message"),
                name=json_response.get("ErrorName", "Unknown error name"),
                detail=json_response.get("ErrorDetail", "Unknown error detail"),
                code=response.status_code,
            )
        except json.JSONDecodeError:
            return cls(
                message="Failed to parse the response from SaferPay",
                code=response.status_code,
            )

    def to_dict(self) -> dict:
        """Convert the error response object to a dictionary."""
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

    def payment_initialize(
        self, payment: BasePayment, return_url: str
    ) -> SaferpayPaymentInitializeResponse:
        """Create a new payment at SaferPay."""

        # Validate required fields
        self._validate_payment_initialize_fields(payment)

        # Generate a unique UUID for the request
        request_id = self._generate_request_id()
        return self._make_api_request(
            endpoint="PaymentPage/Initialize",
            payload=self._generate_payment_initialize_payload(
                payment, return_url, request_id
            ),
            request_id=request_id,
            error_message="Failed to create payment at SaferPay",
            response_class=SaferpayPaymentInitializeResponse,
        )

    def payment_assert(self, payment: BasePayment) -> SaferpayPaymentAssertResponse:
        """Asserts the payment status with SaferPay."""

        # Validate required fields
        self._validate_payment_assert_fields(payment)

        # Generate a unique UUID for the request
        request_id = self._generate_request_id()
        return self._make_api_request(
            endpoint="PaymentPage/Assert",
            payload=self._generate_payment_assert_payload(payment, request_id),
            request_id=request_id,
            error_message="Failed to assert payment at SaferPay",
            response_class=SaferpayPaymentAssertResponse,
        )

    def transaction_capture(self, payment: BasePayment, transaction_id: str):
        """Capture a transaction."""

        # Validate required fields
        self._validate_transaction_capture_fields(payment)

        # Generate a unique UUID for the request
        request_id = self._generate_request_id()
        return self._make_api_request(
            endpoint="Transaction/Capture",
            payload=self._generate_transaction_capture_payload(
                payment, transaction_id, request_id
            ),
            request_id=request_id,
            error_message="Failed to capture transaction at SaferPay",
            response_class=SaferpayTransactionCaptureResponse,
        )

    def _get_auth_headers(self) -> Dict[str, str]:
        """Return the authorization headers for API requests."""
        return {
            "User-Agent": f"Django Payments SaferPay {version}",
            "Authorization": f"Basic {base64.b64encode(f'{self.auth_username}:{self.auth_password}'.encode()).decode()}",
        }

    def _get_api_url(self, endpoint: str) -> str:
        """Generate the full API URL for a given endpoint."""
        return f"{self.base_url}/{endpoint}"

    def _make_api_request(
        self,
        endpoint: str,
        payload: Dict[str, Any],
        request_id: str,
        error_message: str,
        response_class: Any,
    ) -> Any:
        """
        Make an API request to SaferPay and handle the response.

        Args:
            endpoint: The API endpoint to call
            payload: The request payload
            request_id: The unique request ID to verify in the response
            error_message: The error message to use if the request fails
            response_class: The class to use for parsing the response

        Returns:
            An instance of response_class with the API response data
        """
        url = self._get_api_url(endpoint)
        response = None

        try:
            response = self.client.post(
                url=url,
                json=payload,
                headers=self._get_auth_headers(),
            )
            response.raise_for_status()
            payment_data = response.json()
            self._verify_request_id(payment_data, request_id)

            return response_class.from_api_response(payment_data)

        except requests.HTTPError as e:
            if response is not None:
                error_data = SaferpayErrorResponse.from_response(response)
                error_message = error_data.message
                error_code = error_data.code
                error_name = error_data.name
            else:
                error_message = str(e)
                error_code = None
                error_name = None

            raise PaymentError(
                error_message,
                code=error_code,
                gateway_message=error_name,
            )
        except json.JSONDecodeError:
            raise PaymentError(
                _("Failed to parse the response from SaferPay"),
                code=response,
                gateway_message="Invalid JSON response",
            )
        except requests.RequestException as e:
            raise PaymentError(
                _("Failed to connect to SaferPay"), gateway_message=str(e)
            )
        except PaymentError:
            raise

    def _verify_request_id(self, payment_data, request_id):
        # Verify that the response contains our request ID
        response_header = payment_data.get("ResponseHeader", {})
        response_request_id = response_header.get("RequestId")

        if response_request_id != request_id:
            raise PaymentError(
                _("SaferPay response RequestId doesn't match our request"),
                gateway_message=f"Expected {request_id}, got {response_request_id}",
            )

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
        if payment.transaction_id:
            raise PaymentError(_("This payment has already been processed"))
        if not payment.currency:
            raise PaymentError(_("The payment has no currency, but it is required"))
        if not payment.total:
            raise PaymentError(_("The payment has no total amount, but it is required"))
        if not payment.description:
            raise PaymentError(_("The payment has no description, but it is required"))

    def _validate_payment_assert_fields(self, payment: BasePayment) -> None:
        """Validate that the payment has all required fields."""
        if not payment.transaction_id:
            raise PaymentError(
                _("The payment has no transaction ID, but it is required")
            )

    def _validate_transaction_capture_fields(self, payment: BasePayment) -> None:
        """Validate that the payment has all required fields."""
        pass
