"""
robot is very bad at detecting invalid robot files. although this is obviously a python file, robot
won't complain unless there's a multiline string with an asterisk at the start of a line. so we do
that to force a robot error and make sure it doesn't happen when running python files

*
"""
