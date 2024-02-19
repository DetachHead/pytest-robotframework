from __future__ import annotations

from ast import Assert, Call, Constant, Expr, If, Raise, copy_location, stmt

from _pytest.assertion import rewrite
from _pytest.assertion.rewrite import (
    AssertionRewriter,
    _get_assertion_exprs,  # pyright:ignore[reportPrivateUsage]
    traverse_node,
)
from pytest import StashKey
from typing_extensions import Callable, cast

from pytest_robotframework._internal.cringe_globals import current_item
from pytest_robotframework._internal.errors import InternalError
from pytest_robotframework._internal.utils import patch_method

explanation_key = StashKey[str]()


def _call_assertion_hook(
    expression: str,
    fail_message: object,
    line_number: int,
    assertion_error: AssertionError | None,
    explanation: str | None = None,
):
    item = current_item()
    if not item:
        return
    if assertion_error and explanation and explanation.startswith("\n"):
        # pretty gross but we have to remove this trailing \n which means the fail message was None
        # but the assertion rewriter already wrote the error message thinking it wasn't None because
        # it was an AssertOptions object
        explanation = explanation[1:]
        assertion_error.args = (explanation, *assertion_error.args[1:])
    item.ihook.pytest_robot_assertion(
        item=item,
        expression=expression,
        fail_message=fail_message,
        line_number=line_number,
        assertion_error=assertion_error,
        explanation=item.stash[explanation_key] if explanation is None else explanation,
    )


# we aren't patching an existing function here but instead adding a new one to the rewrite module,
# since the rewritten assert statement needs to call it, and this is the easist way to do that
rewrite._call_assertion_hook = _call_assertion_hook  # pyright:ignore[reportAttributeAccessIssue]


@patch_method(AssertionRewriter)
def visit_Assert(  # noqa: N802
    og: Callable[[AssertionRewriter, Assert], list[stmt]], self: AssertionRewriter, assert_: Assert
) -> list[stmt]:
    """we patch the assertion rewriter because the hook functions do not give us what we need. see
    these issues:

    - https://github.com/pytest-dev/pytest/issues/11984
    - https://github.com/pytest-dev/pytest/issues/11975
    """
    result = og(self, assert_)
    if not self.enable_assertion_pass_hook:
        return result
    assert_msg = assert_.msg or Constant(None)
    if not self.config:
        raise InternalError("failed to rewrite assertion because config was somehow `None`")
    try:
        main_test = next(statement for statement in reversed(result) if isinstance(statement, If))
    except StopIteration:
        raise InternalError("failed to find if statement for assertion rewriting") from None
    expression = _get_assertion_exprs(self.source)[assert_.lineno]
    # rice the fail statements:
    raise_statement = cast(Raise, main_test.body.pop())
    if not raise_statement.exc:
        raise InternalError("raise statement without exception")
    main_test.body.append(
        Expr(
            self.helper(
                "_call_assertion_hook",
                Constant(expression),  # expression
                assert_msg,  # fail_message
                Constant(assert_.lineno),  # line_number
                raise_statement.exc,  # assertion_error
                cast(Call, raise_statement.exc).args[0],  # explanation
            )
        )
    )

    # rice the pass statements:
    main_test.orelse.append(
        Expr(
            self.helper(
                "_call_assertion_hook",
                Constant(expression),  # expression
                assert_msg,  # fail_message
                Constant(assert_.lineno),  # line_number
                Constant(None),  # assertion_error
                # explanation is handled by the pytest_assertion_pass hook above, since its too
                # hard to get it from here
            )
        )
    )
    # copied from the end of og, need to rerun this since a new statement was added:
    for statement in result:
        for node in traverse_node(statement):
            _ = copy_location(node, assert_)
    return result
