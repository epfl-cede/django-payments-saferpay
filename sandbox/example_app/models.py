from urllib.parse import urljoin

from django.urls import reverse
from payments.core import get_base_url
from payments.models import BasePayment


class Payment(BasePayment):
    def get_failure_url(self):
        url = reverse("payment-failure", kwargs={"token": self.token})
        return urljoin(get_base_url(), url)

    def get_success_url(self):
        url = reverse("payment-success", kwargs={"token": self.token})
        return urljoin(get_base_url(), url)

    def get_purchased_items(self):
        raise NotImplementedError
