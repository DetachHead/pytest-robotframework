*** Settings ***
Test Setup      Bar


*** Test Cases ***
Foo
    Log    1


*** Keywords ***
Bar
    Fail    asdf
