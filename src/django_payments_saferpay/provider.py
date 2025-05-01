import logging
from typing import Any, Dict, Optional

from django.shortcuts import redirect
from payments import PaymentError, PaymentStatus, RedirectNeeded, get_payment_model
from payments.core import BasicProvider
from payments.models import BasePayment

from .facade import Facade, SaferpayTransactionStatus

Payment = get_payment_model()
logger = logging.getLogger(__name__)


class SaferpayProvider(BasicProvider):
    """
    Payment provider for Saferpay payment gateway.

    Handles payment initialization, authorization, capture, and refunds.
    """

    def __init__(self, *args, **kwargs):
        self.customer_id: str = kwargs.pop("customer_id")
        self.terminal_id: str = kwargs.pop("terminal_id")
        self.auth_username: str = kwargs.pop("auth_username")
        self.auth_password: str = kwargs.pop("auth_password")
        self.sandbox: bool = kwargs.pop("sandbox", True)

        self.facade = Facade(self)

        super().__init__(**kwargs)

    @staticmethod
    def update_payment(payment_id: int, **kwargs: Dict[str, Any]) -> None:
        """
        Helper method to update the payment model safely.

        See https://django-payments.readthedocs.io/en/latest/payment-model.html#mutating-a-payment-instance  # noqa: E501

        Args:
            payment_id: The ID of the payment to update
            kwargs: Fields to update on the payment
        """
        Payment.objects.filter(id=payment_id).update(**kwargs)

    def process_data(self, payment: BasePayment, request):
        """
        Process the payment data when the user returns from Saferpay.

        This method checks the payment status with Saferpay and updates the local payment record.
        If applicable, it also captures authorized payments.

        Args:
            payment: The payment instance to process
            request: The HTTP request

        Returns:
            HttpResponse: Redirect to success or failure URL
        """
        if payment.transaction_id:
            if payment.status in [PaymentStatus.REJECTED, PaymentStatus.ERROR]:
                return redirect(payment.get_failure_url())
            elif payment.status == PaymentStatus.CONFIRMED:
                return redirect(payment.get_success_url())

            try:
                saferpay_payment_assert_response = self.facade.payment_assert(payment)
                logger.debug(f"{saferpay_payment_assert_response=}")
            except PaymentError as pe:
                payment.change_status(PaymentStatus.ERROR, str(pe))
                return redirect(payment.get_failure_url())
            else:
                payment.attrs.saferpay_payment_assert_response = (
                    saferpay_payment_assert_response.to_dict()
                )
                payment.save()

                if (
                    saferpay_payment_assert_response.transaction_status
                    == SaferpayTransactionStatus.CANCELED
                ):
                    payment.change_status(PaymentStatus.REJECTED)
                    return redirect(payment.get_failure_url())
                elif (
                    saferpay_payment_assert_response.transaction_status
                    == SaferpayTransactionStatus.CAPTURED
                ):
                    payment.captured_amount = payment.total
                    type(payment).objects.filter(pk=payment.pk).update(
                        captured_amount=payment.captured_amount
                    )
                    payment.change_status(PaymentStatus.CONFIRMED)
                    return redirect(payment.get_success_url())
                elif (
                    saferpay_payment_assert_response.transaction_status
                    == SaferpayTransactionStatus.AUTHORIZED
                ):
                    # make transaction capture call
                    try:
                        saferpay_transaction_capture_response = (
                            self.facade.transaction_capture(
                                payment, saferpay_payment_assert_response.transaction_id
                            )
                        )
                        logger.debug(f"{saferpay_transaction_capture_response=}")
                    except PaymentError as pe:
                        payment.change_status(PaymentStatus.ERROR, str(pe))
                        raise pe
                    else:
                        payment.attrs.saferpay_transaction_capture_response = (
                            saferpay_transaction_capture_response.to_dict()
                        )
                        payment.save()

                        if saferpay_transaction_capture_response.status == "CAPTURED":
                            payment.captured_amount = payment.total
                            type(payment).objects.filter(pk=payment.pk).update(
                                captured_amount=payment.captured_amount
                            )
                            payment.change_status(PaymentStatus.CONFIRMED)
                        return redirect(payment.get_success_url())

        # If we get here, something unexpected happened
        logger.error(f"Unexpected state in process_data for payment {payment.pk}")
        return redirect(payment.get_failure_url())

    def get_form(self, payment: BasePayment, data=None):
        """
        Prepare the payment form and initialize the Saferpay payment.

        Instead of returning an actual form, this redirects the customer to the
        Saferpay payment page.

        Args:
            payment: The payment instance to initialize
            data: Optional form data

        Raises:
            RedirectNeeded: To redirect the customer to Saferpay
            PaymentError: If initialization fails
        """
        if not payment.transaction_id:
            return_url = self.get_return_url(payment)

            try:
                saferpay_payment_initialize_response = self.facade.payment_initialize(
                    payment, return_url
                )
            except PaymentError as pe:
                # Handle payment error
                payment.change_status(PaymentStatus.ERROR, str(pe))
                raise pe
            else:
                # Update the Payment
                payment.attrs.saferpay_payment_initialize_response = (
                    saferpay_payment_initialize_response.to_dict()
                )
                payment.transaction_id = saferpay_payment_initialize_response.token
                payment.save()

        # Send the user to Saferpay for further payment
        raise RedirectNeeded(
            payment.attrs.saferpay_payment_initialize_response["redirect_url"]
        )

    def capture(self, payment: BasePayment, amount: Optional[int] = None):
        """
        Capture an authorized payment.

        This would typically be used for delayed captures (authorize now, capture later).

        Args:
            payment: The payment to capture
            amount: The amount to capture (defaults to full amount)

        Raises:
            PaymentError: If capture fails
        """
        if not payment.transaction_id:
            raise PaymentError("Cannot capture a payment without a transaction ID")

        # Implementation depends on Saferpay's API for capturing authorized transactions
        raise NotImplementedError("Explicit capture not implemented")

    def refund(self, payment: BasePayment, amount: Optional[int] = None):
        """
        Refund a captured payment.

        Args:
            payment: The payment to refund
            amount: The amount to refund (defaults to full amount)

        Raises:
            PaymentError: If refund fails
        """
        if not payment.transaction_id:
            raise PaymentError("Cannot refund a payment without a transaction ID")

        # Implementation depends on Saferpay's API for refunding transactions
        raise NotImplementedError("Refunds not implemented")
