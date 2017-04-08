import json
import unittest
from collections import OrderedDict

try:
    from unittest.mock import patch, Mock  # Post 3.4.3
except:
    from mock import patch, Mock  # Pre

import sys

import nrpe_template as tested
tested_name = 'nrpe_template'

class TestArgumentParsing(unittest.TestCase):
    def test_quiet(self):
        args = ['--quiet']
        parsed_args = tested.process_args(args=args)
        self.assertEqual(parsed_args.quiet, True)

    def test_loud(self):
        args = []
        parsed_args = tested.process_args(args=args)
        self.assertEqual(parsed_args.quiet, False)

    def test_novalidate(self):
        args = ['--no-validate']
        parsed_args = tested.process_args(args=args)
        self.assertEqual(parsed_args.validate, False)

    def test_validate(self):
        args = ['--validate']
        parsed_args = tested.process_args(args=args)
        self.assertEqual(parsed_args.validate, True)


class TestReturnCode(unittest.TestCase):
    def setUp(self):
        tested.return_code = tested.UNDEFINED_RC
        tested.message_groups = OrderedDict((
            ('UNKNOWN', []),
            ('CRITICAL', []),
            ('WARNING', []),
            ('OK', [])))
        tested.performance_data = []

    def test_default_status(self):
        self.assertEqual(tested.return_code, tested.UNDEFINED_RC)
        self.assertListEqual(tested.message_groups['OK'], [])
        self.assertListEqual(tested.message_groups['WARNING'], [])
        self.assertListEqual(tested.message_groups['CRITICAL'], [])
        self.assertListEqual(tested.message_groups['UNKNOWN'], [])
        # Return code should be overridden to a valid value
        self.assertEqual(tested.get_final_return_code(), tested.UNKNOWN_RC)

    def test_default_status_ok_1(self):
        tested.ok('test')
        self.assertEqual(tested.return_code, tested.OK_RC)
        self.assertListEqual(tested.message_groups['OK'], ['test'])
        self.assertListEqual(tested.message_groups['WARNING'], [])
        self.assertListEqual(tested.message_groups['CRITICAL'], [])
        self.assertListEqual(tested.message_groups['UNKNOWN'], [])
        self.assertEqual(tested.get_final_return_code(), tested.OK_RC)

    def test_status_warn_1(self):
        tested.warning('test')
        self.assertEqual(tested.return_code, tested.WARNING_RC)
        self.assertListEqual(tested.message_groups['OK'], [])
        self.assertListEqual(tested.message_groups['WARNING'], ['test'])
        self.assertListEqual(tested.message_groups['CRITICAL'], [])
        self.assertListEqual(tested.message_groups['UNKNOWN'], [])
        self.assertEqual(tested.get_final_return_code(), tested.WARNING_RC)

    def test_status_warn_2(self):
        tested.ok('test_ok')
        tested.warning('test')
        self.assertEqual(tested.return_code, tested.WARNING_RC)
        self.assertListEqual(tested.message_groups['OK'], ['test_ok'])
        self.assertListEqual(tested.message_groups['WARNING'], ['test'])
        self.assertListEqual(tested.message_groups['CRITICAL'], [])
        self.assertListEqual(tested.message_groups['UNKNOWN'], [])
        self.assertEqual(tested.get_final_return_code(), tested.WARNING_RC)

    def test_status_critical_1(self):
        tested.critical('test')
        self.assertEqual(tested.return_code, tested.CRITICAL_RC)
        self.assertListEqual(tested.message_groups['OK'], [])
        self.assertListEqual(tested.message_groups['WARNING'], [])
        self.assertListEqual(tested.message_groups['CRITICAL'], ['test'])
        self.assertListEqual(tested.message_groups['UNKNOWN'], [])
        self.assertEqual(tested.get_final_return_code(), tested.CRITICAL_RC)

    def test_status_critical_2(self):
        tested.ok('test_ok')
        tested.critical('test')
        self.assertEqual(tested.return_code, tested.CRITICAL_RC)
        self.assertListEqual(tested.message_groups['OK'], ['test_ok'])
        self.assertListEqual(tested.message_groups['WARNING'], [])
        self.assertListEqual(tested.message_groups['CRITICAL'], ['test'])
        self.assertListEqual(tested.message_groups['UNKNOWN'], [])
        self.assertEqual(tested.get_final_return_code(), tested.CRITICAL_RC)

    def test_status_unknown_1(self):
        tested.unknown('test')
        self.assertEqual(tested.return_code, tested.UNKNOWN_RC)
        self.assertListEqual(tested.message_groups['OK'], [])
        self.assertListEqual(tested.message_groups['WARNING'], [])
        self.assertListEqual(tested.message_groups['CRITICAL'], [])
        self.assertListEqual(tested.message_groups['UNKNOWN'], ['test'])
        self.assertEqual(tested.get_final_return_code(), tested.UNKNOWN_RC)

    def test_status_unknown_2(self):
        tested.ok('test_ok')
        tested.unknown('test')
        self.assertEqual(tested.return_code, tested.UNKNOWN_RC)
        self.assertListEqual(tested.message_groups['OK'], ['test_ok'])
        self.assertListEqual(tested.message_groups['WARNING'], [])
        self.assertListEqual(tested.message_groups['CRITICAL'], [])
        self.assertListEqual(tested.message_groups['UNKNOWN'], ['test'])
        self.assertEqual(tested.get_final_return_code(), tested.UNKNOWN_RC)


class TestParseThresholds(unittest.TestCase):
    def test_blanks1(self):
        self.assertRaises(ValueError, tested.parse_thresholds, '0::0')

    def test_blanks2(self):
        self.assertRaises(ValueError, tested.parse_thresholds, '::')

    def test_blanks3(self):
        self.assertRaises(ValueError, tested.parse_thresholds, ':0:0')

    def test_blanks4(self):
        self.assertRaises(ValueError, tested.parse_thresholds, '0:0:')

    def test_blanks5(self):
        self.assertRaises(ValueError, tested.parse_thresholds, '0:0:')

    def test_too_many_1(self):
        self.assertRaises(ValueError, tested.parse_thresholds, '0:0:0:')

    def test_too_many_2(self):
        self.assertRaises(ValueError, tested.parse_thresholds, '0:0:0:0')

    def test_too_few(self):
        self.assertRaises(IndexError, tested.parse_thresholds, '0')

    def test_two(self):
        results = tested.parse_thresholds("1:2")
        self.assertListEqual(results, [1, 2, None])

    def test_three_1(self):
        results = tested.parse_thresholds("1:2:x")
        self.assertListEqual(results, [1, 2, 'x'])

    def test_three_2(self):
        results = tested.parse_thresholds("1:2:3")
        self.assertListEqual(results, [1, 2, '3'])


class TestEvalateThresholds(unittest.TestCase):
    def setUp(self):
        tested.return_code = tested.UNDEFINED_RC
        tested.message_groups = OrderedDict((
            ('UNKNOWN', []),
            ('CRITICAL', []),
            ('WARNING', []),
            ('OK', [])))
        tested.performance_data = []

    def test_ok_1(self):
        tested.evaluate_numeric_thresholds('test', 1, 2, 3)
        self.assertEqual(tested.return_code, tested.OK_RC)
        self.assertListEqual(tested.message_groups['OK'], ['test 1'])
        self.assertListEqual(tested.message_groups['WARNING'], [])
        self.assertListEqual(tested.message_groups['CRITICAL'], [])
        self.assertListEqual(tested.message_groups['UNKNOWN'], [])
        # Return code should be overridden to a valid value
        self.assertEqual(tested.get_final_return_code(), tested.OK_RC)

    def test_ok_2(self):
        tested.evaluate_numeric_thresholds('test', 3, 2, 1, greater_than=False)
        self.assertEqual(tested.return_code, tested.OK_RC)
        self.assertListEqual(tested.message_groups['OK'], ['test 3'])
        self.assertListEqual(tested.message_groups['WARNING'], [])
        self.assertListEqual(tested.message_groups['CRITICAL'], [])
        self.assertListEqual(tested.message_groups['UNKNOWN'], [])
        # Return code should be overridden to a valid value
        self.assertEqual(tested.get_final_return_code(), tested.OK_RC)

    def test_warning_1(self):
        tested.evaluate_numeric_thresholds('test', 2, 1, 3)
        self.assertEqual(tested.return_code, tested.WARNING_RC)
        self.assertListEqual(tested.message_groups['OK'], [])
        self.assertListEqual(tested.message_groups['WARNING'], ['test 2>1'])
        self.assertListEqual(tested.message_groups['CRITICAL'], [])
        self.assertListEqual(tested.message_groups['UNKNOWN'], [])
        # Return code should be overridden to a valid value
        self.assertEqual(tested.get_final_return_code(), tested.WARNING_RC)

    def test_warning_2(self):
        tested.evaluate_numeric_thresholds('test', 2, 3, 1, greater_than=False)
        self.assertEqual(tested.return_code, tested.WARNING_RC)
        self.assertListEqual(tested.message_groups['OK'], [])
        self.assertListEqual(tested.message_groups['WARNING'], ['test 2<3'])
        self.assertListEqual(tested.message_groups['CRITICAL'], [])
        self.assertListEqual(tested.message_groups['UNKNOWN'], [])
        # Return code should be overridden to a valid value
        self.assertEqual(tested.get_final_return_code(), tested.WARNING_RC)

    def test_critical_1(self):
        tested.evaluate_numeric_thresholds('test', 3, 1, 2, units='x')
        self.assertEqual(tested.return_code, tested.CRITICAL_RC)
        self.assertListEqual(tested.message_groups['OK'], [])
        self.assertListEqual(tested.message_groups['WARNING'], [])
        self.assertListEqual(tested.message_groups['CRITICAL'], ['test 3x>2x'])
        self.assertListEqual(tested.message_groups['UNKNOWN'], [])
        # Return code should be overridden to a valid value
        self.assertEqual(tested.get_final_return_code(), tested.CRITICAL_RC)

    def test_critical_2(self):
        tested.evaluate_numeric_thresholds('test', 1, 3, 2, greater_than=False)
        self.assertEqual(tested.return_code, tested.CRITICAL_RC)
        self.assertListEqual(tested.message_groups['OK'], [])
        self.assertListEqual(tested.message_groups['WARNING'], [])
        self.assertListEqual(tested.message_groups['CRITICAL'], ['test 1<2'])
        self.assertListEqual(tested.message_groups['UNKNOWN'], [])
        # Return code should be overridden to a valid value
        self.assertEqual(tested.get_final_return_code(), tested.CRITICAL_RC)


class TestAddPerformanceData(unittest.TestCase):
    def setUp(self):
        tested.performance_data = []

    def test_add_performance_data_1(self):
        tested.add_performance_data(name='name', value=1, units='x', warning_threshold=2, critical_threshold=3,
                                    lower_limit=0, upper_limit=5)
        self.assertListEqual(tested.performance_data, ["'name'=1x;2;3;0;5;"])


class TestGetUrl(unittest.TestCase):
    TEST_DICT = {
                "time": "02:32:05 AM",
                "milliseconds_since_epoch": 1491532325034,
                "date": "04-07-2017"
                }
    TEST_BYTES = b'''{
                "time": "02:32:05 AM",
                "milliseconds_since_epoch": 1491532325034,
                "date": "04-07-2017"
                }
                '''

    def test_get_url(self):
        response = Mock(**{'read.return_value': self.TEST_BYTES})
        with patch(tested_name + '.urlopen', return_value=response):
            returned = tested.get_url('http://example.com')
            self.assertEqual(returned, self.TEST_BYTES)

    def test_get_asscii(self):
        expected = self.TEST_BYTES.decode('ascii')
        with patch(tested_name + '.get_url', return_value=self.TEST_BYTES):
            returned = tested.get_url_ascii('example.com')
            self.assertEqual(returned, expected)

    def test_get_json(self):
        with patch(tested_name + '.get_url', return_value=self.TEST_BYTES):
            returned = tested.get_url_json('example.com')
            self.assertEqual(returned, self.TEST_DICT)

class TestOutput(unittest.TestCase):

    def setUp(self):
        tested.return_code = tested.UNDEFINED_RC
        tested.message_groups = OrderedDict((
            ('UNKNOWN', ['unknown_test']),
            ('CRITICAL', ['critical_test']),
            ('WARNING', ['warning_test']),
            ('OK', ['ok_test'])))

    def test_loud_1(self):
        tested.performance_data = ['perfdata1', 'perfdata2']
        tested.print_results()
        output = sys.stdout.getvalue().strip()
        self.assertEquals(output, 'UNKNOWN: unknown_test; CRITICAL: critical_test; WARNING: warning_test; OK: ok_test|perfdata1 perfdata2')

    def test_loud_2(self):
        tested.performance_data = []
        tested.print_results()
        output = sys.stdout.getvalue().strip()
        self.assertEquals(output, 'UNKNOWN: unknown_test; CRITICAL: critical_test; WARNING: warning_test; OK: ok_test')


    def test_quiet(self):
        tested.performance_data = []
        tested.quiet = True
        tested.print_results()
        output = sys.stdout.getvalue().strip()
        self.assertEquals(output,
                          'UNKNOWN: unknown_test; CRITICAL: critical_test; WARNING: warning_test')


class TestSeconds(unittest.TestCase):

    TEST_BYTES = b'''{
                "time": "02:32:05 AM",
                "milliseconds_since_epoch": 1491532325034,
                "date": "04-07-2017"
                }
                '''

    def setUp(self):
        tested.return_code = tested.UNDEFINED_RC

    def test_get_seconds(self):
        response = Mock(**{'read.return_value': self.TEST_BYTES})
        with patch(tested_name + '.urlopen', return_value=response):
            returned = tested.get_second()
            self.assertEqual(returned, 5)

    def test_good_seconds_1(self):
            tested.check_good(5, [5,6])
            self.assertEqual(tested.return_code, tested.OK_RC)


    def test_good_seconds_2(self):
        tested.check_good(5, [1,2])
        self.assertEqual(tested.return_code, tested.CRITICAL_RC)

    def test_good_seconds_3(self):
        tested.check_good(5, 'all')
        self.assertEqual(tested.return_code, tested.OK_RC)

    def test_prime_seconds_1(self):
            tested.check_prime(3)
            self.assertEqual(tested.return_code, tested.OK_RC)


    def test_prime_seconds_2(self):
        tested.check_prime(4)
        self.assertEqual(tested.return_code, tested.CRITICAL_RC)

    def test_check_range_above_1(self):
        tested.check_range_above(5, '1:2')
        self.assertEqual(tested.return_code, tested.OK_RC)

    def test_check_range_above_2(self):
        tested.check_range_above(5, '6:7')
        self.assertEqual(tested.return_code, tested.CRITICAL_RC)


    def test_check_range_below_1(self):
        tested.check_range_below(5, '1:2')
        self.assertEqual(tested.return_code, tested.CRITICAL_RC)
    
    
    def test_check_range_below_2(self):
        tested.check_range_below(5, '6:7')
        self.assertEqual(tested.return_code, tested.OK_RC)


class TestPerform(unittest.TestCase):
    TEST_BYTES = b'''{
                        "time": "02:32:05 AM",
                        "milliseconds_since_epoch": 1491532325034,
                        "date": "04-07-2017"
                        }
                        '''

    args = ['--no-validate', '--good', '5', '--prime', '--above_range', '0:0', '--below_range', '0:0']

    def setUp(self):
        tested.tls_context = None
        tested.return_code = tested.UNDEFINED_RC

    def test_no_validate(self):
        if sys.version_info >= (2,7,9):
            tested.perform_checks(self.args)
            self.assertNotEqual(tested.tls_context, None)

    def test_get_second(self):
        response = Mock(**{'read.return_value': self.TEST_BYTES})
        with patch(tested_name + '.urlopen', return_value=response):
            returned = tested.get_second()
            self.assertEqual(returned, 5)


    def test_check_good(self):
        with patch(tested_name + '.check_good') as patched:
            tested.perform_checks(self.args)
            self.assertEqual(patched.call_count, 1)

    def test_check_prime(self):
        with patch(tested_name + '.check_prime') as patched:
            tested.perform_checks(self.args)
            self.assertEqual(patched.call_count, 1)


    def test_check_range_above(self):
        with patch(tested_name + '.check_range_above') as patched:
            tested.perform_checks(self.args)
            self.assertEqual(patched.call_count, 1)

    def test_check_range_below(self):
        with patch(tested_name + '.check_range_below') as patched:
            tested.perform_checks(self.args)
            self.assertEqual(patched.call_count, 1)

    def test_exception(self):
        with patch(tested_name + '.check_range_below', side_effect=Exception) as patched:
            tested.perform_checks(self.args)
            self.assertEqual(tested.return_code, tested.UNKNOWN_RC)

if __name__ == '__main__':
    unittest.main(buffer=True)
