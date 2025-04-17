import pytest
import requests

from django_payments_saferpay.facade import (
    Facade,
)

from .test_facade import create_facade


class TestFacadeInit:
    def test_init_with_sandbox_true(self):
        """Test initialization with sandbox=True."""
        facade = create_facade()

        # Verify properties are set correctly
        assert facade.provider.customer_id == "test_customer_id"
        assert facade.provider.terminal_id == "test_terminal_id"
        assert facade.provider.auth_username == "test_username"
        assert facade.provider.auth_password == "test_password"
        assert facade.base_url == "https://test.saferpay.com/api/Payment/v1"

        # Verify client is a requests.Session
        assert isinstance(facade.client, requests.Session)

    def test_init_with_sandbox_false(self):
        """Test initialization with sandbox=False."""
        facade = create_facade(sandbox=False)

        # Verify base_url is production URL
        assert facade.base_url == "https://www.saferpay.com/api/Payment/v1"

        # Verify other properties are set correctly
        assert facade.provider.customer_id == "test_customer_id"
        assert facade.provider.terminal_id == "test_terminal_id"
        assert facade.provider.auth_username == "test_username"
        assert facade.provider.auth_password == "test_password"

        # Verify client is a requests.Session
        assert isinstance(facade.client, requests.Session)

    def test_init_with_empty_strings(self):
        """Test initialization with empty strings."""
        facade = create_facade(
            customer_id="",
            terminal_id="",
            auth_username="",
            auth_password="",
            sandbox=True,
        )

        # Verify empty strings are accepted
        assert facade.provider.customer_id == ""
        assert facade.provider.terminal_id == ""
        assert facade.provider.auth_username == ""
        assert facade.provider.auth_password == ""

        # URL still set correctly
        assert facade.base_url == "https://test.saferpay.com/api/Payment/v1"

    def test_init_with_none_values(self):
        """Test initialization with None values raises TypeError."""
        # When customer_id is None
        with pytest.raises(TypeError):
            Facade(
                customer_id=None,
                terminal_id="test_terminal_id",
                auth_username="test_username",
                auth_password="test_password",
                sandbox=True,
            )

        # When terminal_id is None
        with pytest.raises(TypeError):
            Facade(
                customer_id="test_customer_id",
                terminal_id=None,
                auth_username="test_username",
                auth_password="test_password",
                sandbox=True,
            )

        # When auth_username is None
        with pytest.raises(TypeError):
            Facade(
                customer_id="test_customer_id",
                terminal_id="test_terminal_id",
                auth_username=None,
                auth_password="test_password",
                sandbox=True,
            )

        # When auth_password is None
        with pytest.raises(TypeError):
            Facade(
                customer_id="test_customer_id",
                terminal_id="test_terminal_id",
                auth_username="test_username",
                auth_password=None,
                sandbox=True,
            )
