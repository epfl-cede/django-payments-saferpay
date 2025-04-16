# django-payments-saferpay

[![PyPI - Version](https://img.shields.io/pypi/v/django-payments-saferpay.svg)](https://pypi.org/project/django-payments-saferpay)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/django-payments-saferpay.svg)](https://pypi.org/project/django-payments-saferpay)

-----

Django Payments Saferpay is a python package that adds support for the [Saferpay payment provider](https://docs.saferpay.com/home) to [Django Payments](https://django-payments.readthedocs.io/).

**Table of Contents**

- [Installation](#installation)
- [Configuration](#configuration)
- [Sandbox](#sandbox)
- [License](#license)

## Installation

```console
pip install django-payments-saferpay
```

## Configuration

You should follow the configuration guide in the Django Payments documentation. To set up this package as a payment variant, use the following PAYMENT_VARIANTS in the Django settings file:

```python
PAYMENT_VARIANTS = {
    "saferpay": (
        "django_payments_saferpay.provider.SaferpayProvider",
        {
            "customer_id": "your-customer-id",
            "terminal_id": "your-terminal-id",
            "username": "your-username",
            "password": "your-password",
            "sandbox": True,  # Set to True for testing
        }
    )
}
```

### Available configuration options
- `customer_id`: Your Saferpay customer ID.
- `terminal_id`: Your terminal ID from Saferpay.
- `username`: The username for Saferpay API authentication.
- `password`: The password for Saferpay API authentication.
- `sandbox`: Boolean flag to enable or disable sandbox mode for testing.

## Sandbox

The project contains a sandbox that shows a very simple implementation of Django Payments with the SaferPay payment variant. You can use it to see how implementation could be done, or to actually run an application against your own Mollie account.

## License

`django-payments-saferpay` is distributed under the terms of the [BSD](https://spdx.org/licenses/BSD-3-Clause.html) license.
