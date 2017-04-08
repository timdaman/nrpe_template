[![Build Status](https://travis-ci.org/timdaman/nrpe_template.svg?branch=master)](https://travis-ci.org/timdaman/nrpe_template)
[![Code Climate](https://codeclimate.com/github/timdaman/nrpe_template/badges/gpa.svg)](https://codeclimate.com/github/timdaman/nrpe_template)
[![Test Coverage](https://codeclimate.com/github/timdaman/nrpe_template/badges/coverage.svg)](https://codeclimate.com/github/timdaman/nrpe_template/coverage)
Author: Tim Laurence

This is a sample NRPE compatible plugin. It contains many help functions which should make writing your own checks
fast and easy. It supports for both python 2.7 and 3.

Right now it tests the current time as returned from a remote service to see if it meets certain standards. You can use this an example fo rhow to impliment your own checks.

For example run this during second 31 for an OK

     python sample_plugin.py --prime --good 31 32 33 34 35 36 37 38 39 40 --below_range 40:50

Other times will generally be critical

# Hints for using this:

* Rather then returning statues information directly use the helper functions; 
`ok('message')`, `warning('message')`, `critical('message')`, `unknown('message'),`
* When sensible please don't forget to include performance data. There is a function called add_performance_data() to make this easy
* Try to avoid importing libraries outside of the standard library. Doing so can make it harder to run your plug-in on and the various servers that may end up running it. By sticking to the standard library this should run most places where python is installed
* Test your code with python 2.7 and to ensure it works on current and future python releases
* The Requests package is awesome but not included in the standard library. :( As an aid have wrapped urllib to make it easier
to make http requests added the following helper functions; `get_url()`, `get_url_json()`. You are welcome.
* I have included a logger to make it easy to debug while developing and then turn off that output. Use
`logger.debug('your message')` for development. Comment or uncomment the line about the declaration for 'logger; to
turning this output on and off.

# Credits:
* Borrowed parsing and evaluation code from here https://github.com/timdaman/check_docker
* Based on the standard found here https://nagios-plugins.org/doc/guidelines.html