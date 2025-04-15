import logging

from django.http import JsonResponse
from django.utils.http import re
from django.shortcuts import redirect
from payments import PaymentStatus, PaymentError, RedirectNeeded, get_payment_model
from payments.core import BasicProvider
from payments.models import BasePayment

from .facade import SAFER_PAY_SPEC_VERSION, Facade
from .facade import SaferpayTransactionStatus

Payment = get_payment_model()
logger = logging.getLogger(__name__)


class SaferpayProvider(BasicProvider):
    def __init__(self, *args, **kwargs):
        customer_id: str = kwargs.pop("customer_id")
        terminal_id: str = kwargs.pop("terminal_id")
        auth_username: str = kwargs.pop("auth_username")
        auth_password: str = kwargs.pop("auth_password")
        sandbox: bool = kwargs.pop("sandbox", True)
        self.facade = Facade(
            customer_id, terminal_id, auth_username, auth_password, sandbox
        )
        super().__init__(**kwargs)

    @staticmethod
    def update_payment(payment_id: int, **kwargs: dict) -> None:
        """
        Helper method to update the payment model safely.

        See https://django-payments.readthedocs.io/en/latest/payment-model.html#mutating-a-payment-instance  # noqa: E501
        """
        Payment.objects.filter(id=payment_id).update(**kwargs)

    def process_data(self, payment: BasePayment, request):
        """
        This method is responsible for processing webhook calls from the payment gateway. It receives a payment object
        representing the payment being processed and the request object. Implement the logic to handle the webhook
        data received from the payment gateway and update the payment status or perform any necessary actions.

        This method called when user returned back by ReturnUrl, here we check the payment and perform necessary actions.
        """
        if payment.transaction_id:
            if payment.status in [PaymentStatus.REJECTED, PaymentStatus.ERROR]:
                redirect(payment.get_failure_url())
            elif payment.status == PaymentStatus.CONFIRMED:
                redirect(payment.get_success_url())

            try:
                saferpay_assert_response = self.facade.payment_assert(payment)
                logger.warning(f"{saferpay_assert_response=}")
            except PaymentError as pe:
                payment.change_status(PaymentStatus.ERROR, str(pe))
                raise pe
            else:
                payment.attrs.saferpay_assert_response = (
                    saferpay_assert_response.to_dict()
                )
                payment.save()

                if (
                    saferpay_assert_response.transaction_status
                    == SaferpayTransactionStatus.CANCELED
                ):
                    payment.change_status(PaymentStatus.REJECTED)
                    return redirect(payment.get_failure_url())
                elif (
                    saferpay_assert_response.transaction_status
                    == SaferpayTransactionStatus.CAPTURED
                ):
                    payment.captured_amount = payment.total
                    payment.change_status(PaymentStatus.CONFIRMED)
                    return redirect(payment.get_success_url())
                elif (
                    saferpay_assert_response.transaction_status
                    == SaferpayTransactionStatus.AUTHORIZED
                ):
                    # make transaction capture call
                    try:
                        saferpay_transaction_capture_response = (
                            self.facade.transaction_capture(
                                payment, saferpay_assert_response.transaction_id
                            )
                        )
                        logger.warning(f"{saferpay_transaction_capture_response=}")
                    except PaymentError as pe:
                        payment.change_status(PaymentStatus.ERROR, str(pe))
                        raise pe
                    else:
                        payment.attrs.saferpay_capture_response = (
                            saferpay_transaction_capture_response.to_dict()
                        )
                        payment.save()
                        if saferpay_transaction_capture_response.status == "CAPTURED":
                            payment.captured_amount = payment.total
                            payment.change_status(PaymentStatus.CONFIRMED)
                        return redirect(payment.get_success_url())

    def get_form(self, payment, data=None):
        """
        This method is responsible for rendering the payment form to be displayed within your Django application. It
        receives a payment object representing the payment being made and an optional data parameter if form submission
        data is provided. Implement the logic to render the payment form, customize it based on your payment gateway
        requirements, and handle form submission.
        """
        if not payment.transaction_id:
            return_url = self.get_return_url(payment)

            try:
                saferpay_initialize_response = self.facade.payment_initialize(
                    payment, return_url
                )
            except PaymentError as pe:
                # Handle payment error
                payment.change_status(PaymentStatus.ERROR, str(pe))
                raise pe
            else:
                # Update the Payment
                payment.attrs.saferpay_initialize_response = (
                    saferpay_initialize_response.to_dict()
                )
                payment.transaction_id = saferpay_initialize_response.token
                payment.save()

        # Send the user to Saferpay for further payment
        raise RedirectNeeded(payment.attrs.saferpay_initialize_response["redirect_url"])

    def capture(self, payment, amount=None):
        """
        This method is responsible for capturing the payment amount. It receives a payment object representing the
        payment to be captured and an optional amount parameter. Implement the logic to interact with your payment
        gateway’s API and perform the necessary actions to capture the payment amount. If capturing is not supported
        by your payment gateway, set capture: False. to skip capture.
        """
        pass

    def refund(self, payment, amount=None):
        """
        This method is responsible for refunding a payment. It receives a payment object representing the payment
        to be refunded and an optional amount parameter. Implement the logic to interact with your payment
        gateway’s API and initiate the refund process. If refunding is not supported by your payment gateway,
        raise a NotImplementedError.
        """
        pass
