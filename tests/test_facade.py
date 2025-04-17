import base64
import json
from unittest.mock import Mock, patch

import pytest
import requests
from payments import PaymentError

from django_payments_saferpay import __version__ as version
from django_payments_saferpay.facade import (
    Facade,
    SaferpayErrorResponse,
    SaferpayPaymentAssertResponse,
    SaferpayPaymentInitializeResponse,
    SaferpayTransactionCaptureResponse,
)


def create_facade(**kwargs):
    # Create a mock provider object that has the necessary attributes
    mock_provider = Mock()
    mock_provider.customer_id = kwargs.get("customer_id", "test_customer_id")
    mock_provider.terminal_id = kwargs.get("terminal_id", "test_terminal_id")
    mock_provider.auth_username = kwargs.get("auth_username", "test_username")
    mock_provider.auth_password = kwargs.get("auth_password", "test_password")
    mock_provider.sandbox = kwargs.get("sandbox", True)

    return Facade(mock_provider)


class TestSaferpayPaymentInitializeResponse:
    def test_from_api_response_valid(self):
        """Test creating instance from a valid API response."""
        response_data = {
            "ResponseHeader": {"RequestId": "test-request-id"},
            "Token": "test-token",
            "RedirectUrl": "https://test-redirect.com",
        }

        result = SaferpayPaymentInitializeResponse.from_api_response(response_data)

        assert result.request_id == "test-request-id"
        assert result.token == "test-token"
        assert result.redirect_url == "https://test-redirect.com"

    def test_from_api_response_missing_request_id(self):
        """Test that an error is raised when RequestId is missing."""
        response_data = {
            "ResponseHeader": {},  # Missing RequestId
            "Token": "test-token",
            "RedirectUrl": "https://test-redirect.com",
        }

        with pytest.raises(PaymentError) as excinfo:
            SaferpayPaymentInitializeResponse.from_api_response(response_data)

        assert "Missing RequestId in SaferPay response" in str(excinfo.value)

    def test_from_api_response_missing_token(self):
        """Test that an error is raised when Token is missing."""
        response_data = {
            "ResponseHeader": {"RequestId": "test-request-id"},
            # Missing Token
            "RedirectUrl": "https://test-redirect.com",
        }

        with pytest.raises(PaymentError) as excinfo:
            SaferpayPaymentInitializeResponse.from_api_response(response_data)

        assert "Invalid response from SaferPay" in str(excinfo.value)

    def test_from_api_response_missing_redirect_url(self):
        """Test that an error is raised when RedirectUrl is missing."""
        response_data = {
            "ResponseHeader": {"RequestId": "test-request-id"},
            "Token": "test-token",
            # Missing RedirectUrl
        }

        with pytest.raises(PaymentError) as excinfo:
            SaferpayPaymentInitializeResponse.from_api_response(response_data)

        assert "Invalid response from SaferPay" in str(excinfo.value)

    def test_to_dict(self):
        """Test conversion to dictionary."""
        response = SaferpayPaymentInitializeResponse(
            request_id="test-request-id",
            token="test-token",
            redirect_url="https://test-redirect.com",
        )

        result = response.to_dict()

        assert isinstance(result, dict)
        assert result["request_id"] == "test-request-id"
        assert result["token"] == "test-token"
        assert result["redirect_url"] == "https://test-redirect.com"

    def test_direct_initialization(self):
        """Test creating instance directly."""
        response = SaferpayPaymentInitializeResponse(
            request_id="test-request-id",
            token="test-token",
            redirect_url="https://test-redirect.com",
        )

        assert response.request_id == "test-request-id"
        assert response.token == "test-token"
        assert response.redirect_url == "https://test-redirect.com"


class TestSaferpayPaymentAssertResponse:
    def test_from_api_response_valid_with_capture_id(self):
        """Test creating instance from a valid API response with capture_id."""
        response_data = {
            "ResponseHeader": {"RequestId": "test-request-id"},
            "Transaction": {
                "Id": "test-transaction-id",
                "Status": "CAPTURED",
                "CaptureId": "test-capture-id",
            },
        }

        result = SaferpayPaymentAssertResponse.from_api_response(response_data)

        assert result.request_id == "test-request-id"
        assert result.transaction_id == "test-transaction-id"
        assert result.transaction_status == "CAPTURED"
        assert result.capture_id == "test-capture-id"

    def test_from_api_response_valid_without_capture_id(self):
        """Test creating instance from a valid API response without capture_id."""
        response_data = {
            "ResponseHeader": {"RequestId": "test-request-id"},
            "Transaction": {
                "Id": "test-transaction-id",
                "Status": "AUTHORIZED",
                # No CaptureId present
            },
        }

        result = SaferpayPaymentAssertResponse.from_api_response(response_data)

        assert result.request_id == "test-request-id"
        assert result.transaction_id == "test-transaction-id"
        assert result.transaction_status == "AUTHORIZED"
        assert result.capture_id == ""  # Should be empty string when not provided

    def test_from_api_response_missing_request_id(self):
        """Test that an error is raised when RequestId is missing."""
        response_data = {
            "ResponseHeader": {},  # Missing RequestId
            "Transaction": {"Id": "test-transaction-id", "Status": "AUTHORIZED"},
        }

        with pytest.raises(PaymentError) as excinfo:
            SaferpayPaymentAssertResponse.from_api_response(response_data)

        assert "Missing RequestId in SaferPay response" in str(excinfo.value)

    def test_from_api_response_missing_transaction_id(self):
        """Test that an error is raised when Transaction.Id is missing."""
        response_data = {
            "ResponseHeader": {"RequestId": "test-request-id"},
            "Transaction": {
                # Missing Id
                "Status": "AUTHORIZED"
            },
        }

        with pytest.raises(PaymentError) as excinfo:
            SaferpayPaymentAssertResponse.from_api_response(response_data)

        assert "Missing Transaction.Id in SaferPay response" in str(excinfo.value)

    def test_from_api_response_missing_transaction_status(self):
        """Test that an error is raised when Transaction.Status is missing."""
        response_data = {
            "ResponseHeader": {"RequestId": "test-request-id"},
            "Transaction": {
                "Id": "test-transaction-id",
                # Missing Status
            },
        }

        with pytest.raises(PaymentError) as excinfo:
            SaferpayPaymentAssertResponse.from_api_response(response_data)

        assert "Missing Transaction.Status in SaferPay response" in str(excinfo.value)

    def test_from_api_response_missing_transaction_object(self):
        """Test that an error is raised when Transaction object is missing."""
        response_data = {
            "ResponseHeader": {"RequestId": "test-request-id"},
            # Missing Transaction object
        }

        with pytest.raises(PaymentError) as excinfo:
            SaferpayPaymentAssertResponse.from_api_response(response_data)

        assert "Missing Transaction.Id in SaferPay response" in str(excinfo.value)

    def test_to_dict(self):
        """Test conversion to dictionary."""
        response = SaferpayPaymentAssertResponse(
            request_id="test-request-id",
            transaction_id="test-transaction-id",
            transaction_status="AUTHORIZED",
            capture_id="test-capture-id",
        )

        result = response.to_dict()

        assert isinstance(result, dict)
        assert result["request_id"] == "test-request-id"
        assert result["transaction_id"] == "test-transaction-id"
        assert result["transaction_status"] == "AUTHORIZED"
        assert result["capture_id"] == "test-capture-id"

    def test_direct_initialization(self):
        """Test creating instance directly."""
        response = SaferpayPaymentAssertResponse(
            request_id="test-request-id",
            transaction_id="test-transaction-id",
            transaction_status="AUTHORIZED",
            capture_id="test-capture-id",
        )

        assert response.request_id == "test-request-id"
        assert response.transaction_id == "test-transaction-id"
        assert response.transaction_status == "AUTHORIZED"
        assert response.capture_id == "test-capture-id"

    def test_all_transaction_status_values(self):
        """Test with different valid transaction status values."""
        status_values = ["AUTHORIZED", "CANCELED", "CAPTURED", "PENDING"]

        for status in status_values:
            response_data = {
                "ResponseHeader": {"RequestId": "test-request-id"},
                "Transaction": {"Id": "test-transaction-id", "Status": status},
            }

            result = SaferpayPaymentAssertResponse.from_api_response(response_data)
            assert result.transaction_status == status


class TestSaferpayTransactionCaptureResponse:
    def test_from_api_response_valid(self):
        """Test creating instance from a valid API response."""
        response_data = {
            "ResponseHeader": {"RequestId": "test-request-id"},
            "Status": "CAPTURED",
        }

        result = SaferpayTransactionCaptureResponse.from_api_response(response_data)

        assert result.request_id == "test-request-id"
        assert result.status == "CAPTURED"

    def test_from_api_response_missing_request_id(self):
        """Test that an error is raised when RequestId is missing."""
        response_data = {
            "ResponseHeader": {},  # Missing RequestId
            "Status": "CAPTURED",
        }

        with pytest.raises(PaymentError) as excinfo:
            SaferpayTransactionCaptureResponse.from_api_response(response_data)

        assert "Missing RequestId in SaferPay response" in str(excinfo.value)

    def test_from_api_response_missing_status(self):
        """Test handling when Status field is missing."""
        response_data = {
            "ResponseHeader": {"RequestId": "test-request-id"}
            # Status is missing
        }

        result = SaferpayTransactionCaptureResponse.from_api_response(response_data)

        assert result.request_id == "test-request-id"
        assert result.status == ""  # Should be empty string when not provided

    def test_from_api_response_empty_status(self):
        """Test handling when Status field is empty."""
        response_data = {
            "ResponseHeader": {"RequestId": "test-request-id"},
            "Status": "",
        }

        result = SaferpayTransactionCaptureResponse.from_api_response(response_data)

        assert result.request_id == "test-request-id"
        assert result.status == ""

    def test_from_api_response_missing_response_header(self):
        """Test that an error is raised when ResponseHeader is missing."""
        response_data = {
            # Missing ResponseHeader
            "Status": "CAPTURED"
        }

        with pytest.raises(PaymentError) as excinfo:
            SaferpayTransactionCaptureResponse.from_api_response(response_data)

        assert "Missing RequestId in SaferPay response" in str(excinfo.value)

    def test_to_dict(self):
        """Test conversion to dictionary."""
        response = SaferpayTransactionCaptureResponse(
            request_id="test-request-id", status="CAPTURED"
        )

        result = response.to_dict()

        assert isinstance(result, dict)
        assert result["request_id"] == "test-request-id"
        assert result["status"] == "CAPTURED"

    def test_direct_initialization(self):
        """Test creating instance directly."""
        response = SaferpayTransactionCaptureResponse(
            request_id="test-request-id", status="CAPTURED"
        )

        assert response.request_id == "test-request-id"
        assert response.status == "CAPTURED"

    def test_with_different_status_values(self):
        """Test with different possible status values."""
        status_values = ["CAPTURED", "PENDING"]

        for status in status_values:
            response_data = {
                "ResponseHeader": {"RequestId": "test-request-id"},
                "Status": status,
            }

            result = SaferpayTransactionCaptureResponse.from_api_response(response_data)
            assert result.request_id == "test-request-id"
            assert result.status == status

    def test_from_api_response_with_extra_fields(self):
        """Test creating instance from API response with extra fields."""
        response_data = {
            "ResponseHeader": {
                "RequestId": "test-request-id",
                "ExtraField": "should be ignored",
            },
            "Status": "CAPTURED",
            "AnotherExtraField": "should also be ignored",
        }

        result = SaferpayTransactionCaptureResponse.from_api_response(response_data)

        assert result.request_id == "test-request-id"
        assert result.status == "CAPTURED"
        # Make sure extra fields are not added to the object
        assert not hasattr(result, "ExtraField")
        assert not hasattr(result, "AnotherExtraField")


class TestSaferpayErrorResponse:
    def test_default_values(self):
        """Test that the class has the expected default values."""
        error = SaferpayErrorResponse()

        assert error.message == "Unknown error message"
        assert error.name == "Unknown error name"
        assert error.detail == "Unknown error detail"
        assert error.code is None

    def test_custom_values(self):
        """Test creating instance with custom values."""
        error = SaferpayErrorResponse(
            message="Custom error message",
            name="CustomError",
            detail="Detailed error info",
            code=400,
        )

        assert error.message == "Custom error message"
        assert error.name == "CustomError"
        assert error.detail == "Detailed error info"
        assert error.code == 400

    def test_from_response_none(self):
        """Test handling when response is None."""
        error = SaferpayErrorResponse.from_response(None)

        assert error.message == "No response received from SaferPay"
        assert error.name == "Unknown error name"
        assert error.detail == "Unknown error detail"
        assert error.code is None

    def test_from_response_json_success(self):
        """Test creating from a response with valid JSON error data."""
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "ErrorMessage": "Payment failed",
            "ErrorName": "PaymentError",
            "ErrorDetail": "Card declined",
        }

        error = SaferpayErrorResponse.from_response(mock_response)

        assert error.message == "Payment failed"
        assert error.name == "PaymentError"
        assert error.detail == "Card declined"
        assert error.code == 400

    def test_from_response_partial_json(self):
        """Test creating from a response with partial JSON error data."""
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 500
        mock_response.json.return_value = {
            "ErrorMessage": "Server error",
            # Missing ErrorName and ErrorDetail
        }

        error = SaferpayErrorResponse.from_response(mock_response)

        assert error.message == "Server error"
        assert error.name == "Unknown error name"  # Default value
        assert error.detail == "Unknown error detail"  # Default value
        assert error.code == 500

    def test_from_response_json_decode_error(self):
        """Test handling when response contains invalid JSON."""
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 502
        # Use JSONDecodeError instead of ValueError
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)

        error = SaferpayErrorResponse.from_response(mock_response)

        assert error.message == "Failed to parse the response from SaferPay"
        assert error.name == "Unknown error name"
        assert error.detail == "Unknown error detail"
        assert error.code == 502

    def test_to_dict(self):
        """Test conversion to dictionary."""
        error = SaferpayErrorResponse(
            message="Test error message",
            name="TestError",
            detail="Test error details",
            code=404,
        )

        result = error.to_dict()

        assert isinstance(result, dict)
        assert result["message"] == "Test error message"
        assert result["name"] == "TestError"
        assert result["detail"] == "Test error details"
        assert result["code"] == 404

    def test_logging_on_error(self):
        """Test that error responses are logged."""
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 400
        error_data = {
            "ErrorMessage": "Payment failed",
            "ErrorName": "PaymentError",
            "ErrorDetail": "Card declined",
        }
        mock_response.json.return_value = error_data

        # mock the logger instance of the module
        with patch("django_payments_saferpay.facade.logger") as mock_logger:
            SaferpayErrorResponse.from_response(mock_response)

            # Verify that error is logged
            mock_logger.error.assert_called_once()
            # Check that the log message contains our error data
            log_message = mock_logger.error.call_args[0][0]
            assert "SaferPay error response:" in log_message
            assert str(error_data) in log_message


class TestFacadeGetAuthHeaders:
    def test_get_auth_headers_structure(self):
        """Test that _get_auth_headers returns the correct structure."""
        facade = create_facade()

        headers = facade._get_auth_headers()

        # Verify we get back a dictionary
        assert isinstance(headers, dict)

        # Verify it contains the expected keys
        assert "User-Agent" in headers
        assert "Authorization" in headers

    def test_user_agent_header(self):
        """Test that User-Agent header has the correct format."""
        facade = create_facade()

        headers = facade._get_auth_headers()

        # Verify User-Agent format
        expected_user_agent = f"Django Payments SaferPay {version}"
        assert headers["User-Agent"] == expected_user_agent

    def test_authorization_header(self):
        """Test that Authorization header has the correct Basic auth format."""
        auth_username = "test_username"
        auth_password = "test_password"
        facade = create_facade()
        headers = facade._get_auth_headers()

        # Verify Basic auth format
        expected_auth_string = f"Basic {base64.b64encode(f'{auth_username}:{auth_password}'.encode()).decode()}"
        assert headers["Authorization"] == expected_auth_string


class TestFacadeGetApiUrl:
    def test_get_api_url_sandbox(self):
        """Test URL construction with sandbox mode."""
        facade = create_facade()

        # Test with a simple endpoint
        url = facade._get_api_url("Test/Endpoint")
        expected_url = "https://test.saferpay.com/api/Payment/v1/Test/Endpoint"
        assert url == expected_url

    def test_get_api_url_production(self):
        """Test URL construction with production mode."""
        facade = create_facade(sandbox=False)

        # Test with a simple endpoint
        url = facade._get_api_url("Test/Endpoint")
        expected_url = "https://www.saferpay.com/api/Payment/v1/Test/Endpoint"
        assert url == expected_url
