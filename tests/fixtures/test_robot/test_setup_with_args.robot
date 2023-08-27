*** Settings ***
Test Setup      Run Keywords    Bar    AND    Baz


*** Test Cases ***
Foo
    No Operation


*** Keywords ***
Bar
    Log    1

Baz
    Log    2
