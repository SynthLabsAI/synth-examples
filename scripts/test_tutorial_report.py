"""No-spend checks for usage accounting; block repeats are not extra calls."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'examples/review-lab'))
from report import session_usage


class ReportTests(unittest.TestCase):
    def test_duplicate_blocks_and_stream_updates(self):
        def line(id, count):
            return json.dumps({'type': 'assistant', 'message': {'id': id,
                'usage': {'input_tokens': 100, 'output_tokens': count}}})
        result = session_usage([line('one', 1), line('one', 4), line('one', 4), line('two', 2)])
        self.assertEqual(result['input_tokens'], 200)
        self.assertEqual(result['output_tokens'], 6)
        self.assertEqual(result['messages'], 2)

    def test_missing_usage_is_not_zero(self):
        self.assertIsNone(session_usage(['{"type":"user"}']))

    def test_invalid_counter_rejected(self):
        for count in [-1, True, '20']:
            with self.assertRaises(ValueError):
                session_usage([json.dumps({'type':'assistant', 'message':{'id':'x','usage':{'input_tokens':count}}})])


if __name__ == '__main__':
    unittest.main()
