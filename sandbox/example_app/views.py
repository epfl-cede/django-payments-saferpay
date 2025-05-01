import random
from decimal import Decimal

from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from payments import RedirectNeeded, get_payment_model

Payment = get_payment_model()


def payment_failure(request, token):
    """The payment failure view, referenced from the Payment model."""
    payment = get_object_or_404(Payment, token=token)

    return HttpResponse(
        content=f"Payment failure, {payment.status=}, {payment.message=}".encode(),
    )


def payment_success(request, token):
    """The payment success view, referenced from the Payment model."""
    payment = get_object_or_404(Payment, token=token)

    return HttpResponse(
        content=f"Payment success, {payment.total=}, {payment.captured_amount=}, {payment.status=}, {payment.message=}".encode(),  # noqa: E501
    )


def payment_details(request, token):
    """
    The payment details view, as described in django-payments documentation.

    See https://django-payments.readthedocs.io/en/latest/payment-model.html#create-a-payment-view  # noqa: E501
    """
    payment = get_object_or_404(Payment, token=token)

    try:
        form = payment.get_form(data=request.POST or None)
    except RedirectNeeded as redirect_to:
        return redirect(str(redirect_to))

    return TemplateResponse(request, "payment.html", {"form": form, "payment": payment})


def create_payment(request):
    """Simple view to create a payment and redirect, to start the manual flow."""
    if "amount" in request.GET:
        amount = Decimal(request.GET["amount"])

        payment = Payment.objects.create(
            variant="saferpay",
            total=amount,
            currency="EUR",
            description=f"My payment #{random.randint(1, 99999)}",
        )
        return redirect(reverse("payment-details", kwargs={"token": payment.token}))

    else:
        return HttpResponse(
            content="""<form>
                <input type="number" min="1" step=".01" name="amount" value="10.00" />
                <input type="submit" value="Create payment" />
            </form>""".encode()
        )
