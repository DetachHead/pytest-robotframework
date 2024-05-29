*** Settings ***
Test Setup          Log    setup ran
Test Teardown       Log    teardown ran


*** Test Cases ***
Runs globally defined setup and teardown
    No Operation

Disable teardown
    No Operation
    [Teardown]    None

Disable setup
    [Setup]    None
    No Operation
