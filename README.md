# django-payments-saferpay

[![PyPI - Version](https://img.shields.io/pypi/v/django-payments-saferpay.svg)](https://pypi.org/project/django-payments-saferpay)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/django-payments-saferpay.svg)](https://pypi.org/project/django-payments-saferpay)

A Django Payments plugin that integrates [Saferpay payment provider](https://docs.saferpay.com/home) with [Django Payments](https://django-payments.readthedocs.io/).

## Features

- Easy integration with Django Payments framework
- Support for Saferpay payment processing
- Sandbox mode for testing
- Simple configuration

## Installation

```console
pip install django-payments-saferpay
```

## Configuration

### Basic Setup

Add the Saferpay payment variant to your Django settings:

```python
PAYMENT_VARIANTS = {
    "saferpay": (
        "django_payments_saferpay.provider.SaferpayProvider",
        {
            "customer_id": "your-customer-id",
            "terminal_id": "your-terminal-id",
            "username": "your-username",
            "password": "your-password",
            "sandbox": True,  # Set to True for testing, False for production
        }
    )
}
```

### Configuration Options

| Option | Description | Required |
|--------|-------------|----------|
| `customer_id` | Your Saferpay customer ID | Yes |
| `terminal_id` | Your terminal ID from Saferpay | Yes |
| `username` | The username for Saferpay API authentication | Yes |
| `password` | The password for Saferpay API authentication | Yes |
| `sandbox` | Boolean flag to enable or disable sandbox mode (default: `True`) | No |

### Environment Variables

For security, it's recommended to store sensitive data in environment variables:

```python
import os

PAYMENT_VARIANTS = {
    "saferpay": (
        "django_payments_saferpay.provider.SaferpayProvider",
        {
            "customer_id": os.environ.get("SAFERPAY_CUSTOMER_ID"),
            "terminal_id": os.environ.get("SAFERPAY_TERMINAL_ID"),
            "username": os.environ.get("SAFERPAY_API_USERNAME"),
            "password": os.environ.get("SAFERPAY_API_PASSWORD"),
            "sandbox": True,
        }
    )
}
```

## Sandbox Testing Environment

The project includes a sandbox application that demonstrates a simple implementation of Django Payments with the SaferPay payment variant. You can use it to:

- See a complete working implementation example
- Test your SaferPay credentials
- Experiment with different payment flows

### Setting Up the Sandbox

1. Navigate to the sandbox directory:
   ```console
   cd sandbox
   ```

2. Create an environment file (`.envrc`) with your Saferpay credentials:
   ```shell
   export PAYMENT_HOST=localhost:8000
   export SAFERPAY_CUSTOMER_ID=your-customer-id
   export SAFERPAY_TERMINAL_ID=your-terminal-id
   export SAFERPAY_API_PASSWORD=your-password
   export SAFERPAY_API_USERNAME=API_username_here
   ```

3. Load the environment variables:
   ```console
   source .envrc
   ```
   (Or if you have [direnv](https://direnv.net/) installed, it will load automatically)

4. Set up and run the sandbox server:
   ```console
   uv venv                          # Create virtual environment
   source .venv/bin/activate        # Activate virtual environment
   uv pip install ..                # Install the package
   python manage.py migrate         # Set up the database
   python manage.py runserver       # Start the server
   ```

5. Open your browser and navigate to:
   ```
   http://localhost:8000/create-payment/
   ```

## Documentation

For more detailed information, refer to:
- [Django Payments Documentation](https://django-payments.readthedocs.io/)
- [Saferpay API Documentation](https://docs.saferpay.com/home)
- [Saferpay API Reference](https://saferpay.github.io/jsonapi/index.html)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

`django-payments-saferpay` is distributed under the terms of the [BSD 3-Clause](https://spdx.org/licenses/BSD-3-Clause.html) license.
