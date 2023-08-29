*** Settings ***
Test Teardown       Actual Teardown


*** Test Cases ***
Foo
    Teardown


*** Keywords ***
Teardown
    Log    1

Actual Teardown
    Log    2
