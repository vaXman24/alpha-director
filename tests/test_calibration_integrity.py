import importlib.util
import sys
import types
import unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

BASE=Path(__file__).resolve().parents[1]
fake_db=types.ModuleType('db')
sys.modules['db']=fake_db

def load(name, folder='sentinel_files'):
    spec=importlib.util.spec_from_file_location(name,BASE/folder/(name+'.py'))
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

scorer=load('thesis_scorer')
sys.modules['thesis_scorer']=scorer
generator=load('thesis_generator')
calibrator=load('source_calibrator')
NOW=datetime(2026,9,8,12,tzinfo=timezone.utc)
THESIS={'ticker':'TEST','thesis_id':'TEST-1','entry_price':100.,'hard_stop':90.,
        'time_stop':'2026-09-01','probability':0.0,'divergence_flag':'CONSENSUS'}

class ScoringTests(unittest.TestCase):
    def setUp(self):
        fake_db.recent_divergences=Mock(return_value=[{'verdict':'DIVERGENCE_HIGH'}])
        fake_db.recent_signals=Mock(return_value=[{'price':1,'ts':'2020-01-01'}])
        fake_db.update_trail_stop=Mock()

    def exit_at(self,price,**fields):
        with patch.object(scorer,'_current_price',return_value=price), patch.object(scorer,'_check_trim_alerts'):
            return scorer._check_exits(dict(THESIS,**fields),NOW)

    def test_missing_price_stays_open(self):
        self.assertIsNone(self.exit_at(None)[0])

    def test_missing_price_has_no_database_side_effect(self):
        self.exit_at(None)
        fake_db.update_trail_stop.assert_not_called()

    def test_missing_entry_stays_open(self):
        self.assertIsNone(self.exit_at(100,entry_price=None,hard_stop=None)[0])

    def test_gap_below_entry_is_not_win(self):
        self.assertEqual(self.exit_at(80,trail_stop=115)[0],'STOP')

    def test_breakeven_trailing_exit_is_not_win(self):
        self.assertEqual(self.exit_at(100,trail_stop=115)[0],'STOP')

    def test_profitable_trailing_exit_is_win(self):
        self.assertEqual(self.exit_at(110,trail_stop=115)[0],'WIN')

    def test_hard_stop_preserved(self):
        self.assertEqual(self.exit_at(85)[0],'STOP')

    def test_expiry_boundaries_preserved(self):
        for price,outcome in [(111,'WIN'),(100,'DRAW'),(95,'DRAW'),(94,'MISS')]:
            with self.subTest(price=price): self.assertEqual(self.exit_at(price)[0],outcome)

    def test_zero_probability_preserved(self):
        record=scorer._build_outcome_record(THESIS,'WIN',110,NOW)
        self.assertEqual(record['probability_assigned'],0)
        self.assertEqual(record['brier_score'],1)

    def test_entry_divergence_preserved(self):
        record=scorer._build_outcome_record(THESIS,'WIN',110,NOW)
        self.assertEqual(record['divergence_flag'],'CONSENSUS')
        fake_db.recent_divergences.assert_not_called()

    def test_missing_entry_divergence_remains_unknown(self):
        record=scorer._build_outcome_record(dict(THESIS,divergence_flag=None),'WIN',110,NOW)
        self.assertIsNone(record['divergence_flag'])

    def test_invalid_prices_rejected(self):
        for price in [0,-1,float('nan'),float('inf'),'invalid',None]:
            with self.subTest(price=price): self.assertIsNone(scorer._validated_price(price,NOW,NOW))

    def test_stale_future_and_invalid_timestamps_rejected(self):
        for stamp in [NOW-timedelta(days=5),NOW+timedelta(seconds=1),'invalid',None]:
            with self.subTest(stamp=stamp): self.assertIsNone(scorer._validated_price(100,stamp,NOW))

    def test_recent_long_weekend_quote_accepted(self):
        self.assertEqual(scorer._validated_price(100,NOW-timedelta(days=3),NOW),100)

    def test_quote_outage_never_uses_signal_event(self):
        yf=types.ModuleType('yfinance'); yf.Ticker=Mock(side_effect=RuntimeError('fixture'))
        with patch.dict(sys.modules,{'yfinance':yf}):
            self.assertIsNone(scorer._current_price('TEST'))
            self.assertIsNone(generator._price(fake_db,'TEST'))
        fake_db.recent_signals.assert_not_called()

    def test_generator_uses_validated_quote(self):
        with patch.object(scorer,'_current_price',return_value=123.45678):
            self.assertEqual(generator._price(fake_db,'TEST'),123.4568)

class WindowTests(unittest.TestCase):
    DATES=[datetime(2026,9,4),datetime(2026,9,8),datetime(2026,9,9)]
    def test_old_event_not_moved_to_first_available_bar(self):
        self.assertIsNone(calibrator._next_open_idx('2026-01-01',self.DATES))
    def test_next_open_after_holiday(self):
        self.assertEqual(calibrator._next_open_idx('2026-09-04',self.DATES),1)
    def test_no_future_bar_or_empty_window(self):
        self.assertIsNone(calibrator._next_open_idx('2026-09-09',self.DATES))
        self.assertIsNone(calibrator._next_open_idx('2026-09-09',[]))

if __name__=='__main__':
    unittest.main(verbosity=2)
