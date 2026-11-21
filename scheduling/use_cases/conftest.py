from collections.abc import Callable
from contextlib import AbstractContextManager

import pytest

from scheduling.domain.failure import Result
from scheduling.use_cases.test_sign_in_link_support import ADDRESS, PATIENT_EMAIL, Ask

OnCommit = Callable[..., AbstractContextManager[list[Callable[[], object]]]]


@pytest.fixture
def ask(django_capture_on_commit_callbacks: OnCommit) -> Ask:
    """Asks for a link the way a request does: the mail goes after commit, then the pool drains."""

    def run(email: str = PATIENT_EMAIL, address: str = ADDRESS) -> Result[None]:
        from scheduling.use_cases.background_mail import wait_until_idle
        from scheduling.use_cases.sign_in_link import ask_for_link

        with django_capture_on_commit_callbacks(execute=True):
            result = ask_for_link(email, address)
        wait_until_idle()
        return result

    return run
