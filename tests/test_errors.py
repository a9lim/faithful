"""Tests for the FaithfulError hierarchy."""
from faithful.errors import (
    FaithfulError,
    FaithfulConfigError,
    FaithfulSetupError,
    FaithfulRuntimeError,
)


def test_all_subclasses_inherit_from_faithful_error():
    assert issubclass(FaithfulConfigError, FaithfulError)
    assert issubclass(FaithfulSetupError, FaithfulError)
    assert issubclass(FaithfulRuntimeError, FaithfulError)


def test_faithful_error_is_an_exception():
    assert issubclass(FaithfulError, Exception)


def test_message_round_trips():
    err = FaithfulConfigError("missing token")
    assert str(err) == "missing token"
