from payments.models import BasePayment


class BaseTestPayment(BasePayment):
    """Payment model subclassing Django Payments' BaseModel"""

    def get_failure_url(self):
        return "https://example.com/failure"

    def get_success_url(self):
        return "https://example.com/success"
