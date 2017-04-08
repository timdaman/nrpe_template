#!/usr/bin/env python
########################################################################################################################
# Author: Tim Laurence
#
# This is a sample NRPE compatible plugin. It contains many help functions which should make writing your own checks
# fast and easy.
#
# Right now it tests the current time as returned from a remote service to see if it meets certain
# standards
#
# For example run this during second 31 for an OK
#   python sample_plugin.py --prime --good 31 32 33 34 35 36 37 38 39 40 --below_range 40:50
# Other times will generally be critical
#
# Hints for using this:
# * Rather then returning statues information directly use the helper functions;
#   ok('message'), warning('message'), critical('message'), unknown('message'),
#
# * When sensible please don't forget to include performance data. There is a function called add_performance_data() to
#   make this easy
#
# * Try to avoid importing libraries outside of the standard library. Doing so can make it harder to run your plug-in on
#   and the various servers that may end up running it. By sticking to the standard library this should run most places
#   where python is installed
#
#  * Test your code with python 2.7 and to ensure it works on current and future python releases
#
#  * Requests is awesome but not included in the standard library. :( As an aid have included urllib to make it easier
#   to make http requests and the following helper functions; get_url(), get_url_json(). You are welcome. If those
#   don't do what you want you can also use urlopen() directly.
#
#  * I have included a logger to make it easy to debug while developing and then turn off that output. Use
#   logger.debug('your message') for development. Comment or uncomment the line about the declaration for 'logger; to
#   turning this output on and off.
#
#  Credits:
#  * Borrowed parsing and evaluation code from here https://github.com/timdaman/check_docker
#  * Based on the standard found here https://nagios-plugins.org/doc/guidelines.html
########################################################################################################################
import argparse
import json
import logging
import ssl
import traceback
from collections import OrderedDict
from collections import deque
from sys import argv

# This gets a usable urlopen for both python 2 and 3.
import sys

try:
    from urllib.request import Request, urlopen  # Python 3
except:
    from urllib2 import Request, urlopen  # Python 2

# Uncomment to send debug logging to console.
# logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger()

# Timeout on networking requests.
TIMEOUT = 10

# NRPE standard return-codes
OK_RC = 0
WARNING_RC = 1
CRITICAL_RC = 2
UNKNOWN_RC = 3
UNDEFINED_RC = -1

# The final return code. Don't set this directly, use on of the helper methods.
#
return_code = UNDEFINED_RC

message_groups = OrderedDict((
    ('UNKNOWN', []),
    ('CRITICAL', []),
    ('WARNING', []),
    ('OK', [])))

quiet = False

performance_data = []
url_base = None
token = None
headers = {'Content-Type': 'application/json'}
tls_context = None
supports_tls_context = sys.version_info >= (2,7,9)

#########################################################################################################################
#
# Helper functions below. You should probably not touch anything here but read the doc so you know how to use it.
#
#########################################################################################################################
def update_return_code(new_code):
    """
    Update return code never letting it be downgraded
    """
    global return_code
    return_code = new_code if new_code > return_code else return_code

def get_final_return_code():
    if return_code == UNDEFINED_RC:
        return UNKNOWN_RC
    else:
        return return_code

def ok(message):
    """
    Called to record a 'OK' result to a check
    :param message: The message string to record in the results
    :return:
    """
    global message_groups
    update_return_code(OK_RC)
    message_groups['OK'].append(message)


def warning(message):
    """
    Called to record a 'WARNING' result to a check
    :param message: The message string to record in the results
    :return:
    """
    global message_groups
    return_code = update_return_code(WARNING_RC)
    message_groups['WARNING'].append(message)


def critical(message):
    """
    Called to record a 'CRITICAL' result to a check
    :param message: The message string to record in the results
    :return:
    """
    global message_groups
    return_code = update_return_code(CRITICAL_RC)
    message_groups['CRITICAL'].append(message)


def unknown(message):
    """
    Called to record a 'UNKNOWN' result to a check
    :param message: The message string to record in the results
    :return:
    """
    global message_groups
    return_code = update_return_code(UNKNOWN_RC)
    message_groups['UNKNOWN'].append(message)


def get_url(url):
    """ Get a url and get back data raw data """
    global tls_context
    req = Request(url=url, headers=headers)
    logger.debug("Requesting: {} with headers {}".format(url, headers))
    if supports_tls_context:
        response = urlopen(req, context=tls_context, timeout=TIMEOUT)
    else:
        response = urlopen(req, timeout=TIMEOUT)

    bytes = response.read()
    logger.debug("Received: {}".format(repr(bytes)))
    return bytes


def get_url_ascii(url):
    """ Get a url and get back data data that has been decoded as ascii """
    response = get_url(url)
    return response.decode('ascii')


def get_url_utf8(url):
    """ Get a url and get back data data that has been decoded as utf-8 """
    response = get_url(url)
    return response.decode('utf-8')


def get_url_json(url):
    """ Get a url and get back data data that has been decoded as utf-8  and formatted as json"""
    response = get_url_utf8(url)
    return json.loads(response)


def parse_thresholds(spec):
    """
    Given a threshold specification string break it up into ':' separated chunks. Convert chunks to integers

    :param spec: The string specifing ':' separated alert thresholds in the format of warn:crit[:units]

    :return: A list containing the thresholds in order of warn, crit, and units(if included and present)
    """
    returned = []
    parts = deque(spec.split(':'))
    if not all(parts):
        raise ValueError("Blanks are not allowed in a threshold specification: {}".format(spec))
    try:
        # Warning threshold
        returned.append(int(parts.popleft()))
        # Critical threshold
        returned.append(int(parts.popleft()))
    except IndexError:
        raise IndexError("Too few thresholds specified, there must be at least two")
    # If there is a units specified
    if len(parts):
        returned.append(parts.popleft())
    else:
        returned.append(None)

    if len(parts) != 0:
        raise ValueError("Too many threshold specifiers in {}".format(spec))

    return returned


def evaluate_numeric_thresholds(name, value, warning_threshold, critical_threshold, units='', greater_than=True):
    """
    Given a set of thresholds and value automatically set the return code and messages appropriately.
    :param name: The name if the measured variable which will be used in message templates
    :param value: The value being evaluated against the thresholds
    :param warning_threshold: When to start warning
    :param critical_threshold: When to start going critical
    :param units: Used for display. The units the threshold and values are in.
    :param greater_than: If true values are evaluated againt their exceeding a threshold.
                         If false values trigger pass threshold by falling below them
    :return:
    """
    error_template = "{name} {value}{units}{relationship}{threshold}{units}"
    ok_message = "{name} {value}{units}".format(name=name, value=value, units=units)
    message_values = {
        'name': name,
        'value': value,
        'units': units,
        'relationship': '?',
        'threshold': '?'
    }
    if greater_than:
        message_values['relationship'] = '>'
        if value >= critical_threshold:
            message_values['threshold'] = critical_threshold
            critical(error_template.format(**message_values))
        elif value >= warning_threshold:
            message_values['threshold'] = warning_threshold
            warning(error_template.format(**message_values))
        else:
            message_values['threshold'] = warning_threshold
            ok(ok_message)
    else:
        message_values['relationship'] = '<'
        if value <= critical_threshold:
            message_values['threshold'] = critical_threshold
            critical(error_template.format(**message_values))
        elif value <= warning_threshold:
            message_values['threshold'] = warning_threshold
            warning(error_template.format(**message_values))
        else:
            ok(ok_message)


def add_performance_data(name, value, units='', warning_threshold='', critical_threshold='', lower_limit='',
                         upper_limit=''):
    """
    Add performace data record to output. This can be used to graph changes over time
    :param name: The tag used to identify what is this data is. Should be unique. It iwll be used to title graphs.
    :param value: The current value of a metric being checked
    :param units: The unit of measure for the value. Can be blank, 's' for seconds, '%' for percent,
                  'B' 'KB' 'MB' 'TB' for data sizes, and c for continuous counters
    :param warning_threshold: Where to draw the warning threshold on any graphs
    :param critical_threshold: Where to draw the critical threshold on any graphs
    :param lower_limit: The lowest value on the y axis of graphs
    :param upper_limit: The highest value on the y axis of graphs
    :return:
    """
    data_string = "'{name}'={value}{units};{warning_threshold};{critical_threshold};{lower_limit};{upper_limit};". \
        format(name=name,
               value=value,
               units=units,
               warning_threshold=warning_threshold,
               critical_threshold=critical_threshold,
               lower_limit=lower_limit,
               upper_limit=upper_limit)

    performance_data.append(data_string)


def print_results():
    """
    Called after all checks. Prints final results
    :return:
    """
    messages_blocks = []
    for level, messages in message_groups.items():
        if quiet and level == 'OK':
            continue
        if len(messages) > 0:
            block = level + ": "
            block += ', '.join(messages)
            messages_blocks.append(block)

    all_messages = '; '.join(messages_blocks)
    perfdata_concat = ' '.join(performance_data)
    if len(performance_data) > 0:
        print(all_messages + '|' + perfdata_concat)
    else:
        print(all_messages)


########################################################################################################################
#
# Begin of user customizable section
#
########################################################################################################################

def process_args(args):
    parser = argparse.ArgumentParser(description='This is a sample check')

    validate_group = parser.add_mutually_exclusive_group(required=False)
    validate_group.add_argument('--validate',
                                dest='validate',
                                action='store_true',
                                help='Validate certificate'
                                )
    validate_group.add_argument('--no-validate',
                                dest='validate',
                                action='store_false',
                                help='Do not validate certificate'
                                )
    parser.set_defaults(validate=True)

    parser.add_argument('--quiet',
                        dest='quiet',
                        action='store_true',
                        help='Do not display message information for checks that are "OK".')

    parser.add_argument('--good',
                        dest='good',
                        action='store',
                        nargs='+',
                        type=int,
                        default=['all'],
                        help='List of acceptable seconds.  (default: all)')

    parser.add_argument('--prime',
                        dest='prime',
                        action='store_true',
                        default=False,
                        help='Is seconds a prime number')

    parser.add_argument('--above_range',
                        dest='range_above',
                        action='store',
                        type=str,
                        metavar='WARN:CRIT',
                        help='Ranges of acceptable seconds should be above')

    parser.add_argument('--below_range',
                        dest='range_below',
                        action='store',
                        type=str,
                        metavar='WARN:CRIT',
                        help='Ranges of acceptable seconds should be below')

    return parser.parse_args(args=args)


########################################################################################################################
#
# Sample checks
#
########################################################################################################################

def get_second():
    from datetime import datetime
    time_url = 'http://date.jsontest.com/'
    time = get_url_json(time_url)
    second = datetime.strptime(time['time'], '%I:%M:%S %p').second
    return second


def check_good(current_second, good_seconds):
    logger.debug("Good=" + repr(good_seconds))
    if 'all' in good_seconds:
        ok("It is all good")
    else:
        if current_second in good_seconds:
            ok("{} is good".format(current_second))
        else:
            critical("{} is a bad second!".format(current_second))


def check_prime(current_second):
    PRIME_SECONDS = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59]
    if current_second in PRIME_SECONDS:
        ok("{} is prime".format(current_second))
    else:
        critical("{} is not prime".format(current_second))


def check_range_above(current_second, range_spec):
    warning_threshold, critical_threshold, units = parse_thresholds(range_spec)
    evaluate_numeric_thresholds(name='seconds above',
                                value=current_second,
                                units='s',
                                warning_threshold=warning_threshold,
                                critical_threshold=critical_threshold,
                                greater_than=False)


def check_range_below(current_second, range_spec):
    warning_threshold, critical_threshold, units = parse_thresholds(range_spec)
    evaluate_numeric_thresholds(name='seconds below',
                                value=current_second,
                                units='s',
                                warning_threshold=warning_threshold,
                                critical_threshold=critical_threshold)


def perform_checks(args):

    parsed_args = process_args(args)
    try:
        current_second = get_second()
        logger.debug("Second=" + repr(current_second))
        add_performance_data(name='current second',
                             value=current_second,
                             units='s',
                             lower_limit=0,
                             upper_limit=59)

        # Do we validate SSL certs?
        if not parsed_args.validate:
            if supports_tls_context:
                global tls_context
                tls_context = ssl.create_default_context()
                tls_context.check_hostname = False
                tls_context.verify_mode = ssl.CERT_NONE
            else:
                raise NotImplementedError("Disabling TLS validation is not supported in python versions below 2.7.9")
        global quiet
        quiet = parsed_args.quiet

        if parsed_args.good:
            check_good(current_second=current_second, good_seconds=parsed_args.good)
        if parsed_args.prime:
            check_prime(current_second=current_second)
        if parsed_args.range_above:
            check_range_above(current_second=current_second, range_spec=parsed_args.range_above)
        if parsed_args.range_below:
            check_range_below(current_second=current_second, range_spec=parsed_args.range_below)

    except Exception as e:
        traceback.print_exc()
        unknown("We got the following error {}".format(repr(e)))

    ####################################################################################################################
    #
    #  End of customizable section. The rest simply returns results.
    #
    ####################################################################################################################
if __name__ == '__main__':
    args = perform_checks(argv[1:])
    print_results()
    exit(get_final_return_code())