"""Fusions demandées et conservation des caractéristiques et pas d'analyse."""
import unittest
from test_core import synthetic_course
from bzhaventure.analysis import choose_model
from bzhaventure.gpx import describe_course
from bzhaventure.models import SegmentedModel
from bzhaventure.settings import PROFILE_FAMILIES, PROFILE_LABELS, SOURCE_SAMPLING


class MergedProfilesTests(unittest.TestCase):
    def test_both_pairs_are_merged_and_original_shape_is_retained(self):
        for source,family in PROFILE_FAMILIES.items():
            with self.subTest(source=source):
                d=describe_course(synthetic_course(source))
                self.assertEqual(d['profile'],family)
                self.assertEqual(d['sourceProfile'],source)
                self.assertEqual(d['sampling'],SOURCE_SAMPLING[source][1])
                self.assertEqual(d['profileLabel'],PROFILE_LABELS[family])
        self.assertEqual(len(PROFILE_LABELS),4)

    def test_sawtooth_and_mixed_have_requested_names(self):
        self.assertEqual(describe_course(synthetic_course('sawtooth'))['profileLabel'],'Dents de scie')
        self.assertEqual(describe_course(synthetic_course('mixed'))['profileLabel'],'Mixte')

    def test_prediction_sampling_keeps_target_original_resolution(self):
        bank=SegmentedModel([synthetic_course('flat'),synthetic_course('rolling'),
            synthetic_course('intermediate'),synthetic_course('mountain')],validate=False)
        for source in ('flat','rolling','intermediate','mountain'):
            target=synthetic_course(source)
            model=bank.for_course(target)
            self.assertEqual(model.metadata['sampling'],describe_course(target)['sampling'])
            self.assertEqual(model.metadata['count'],2)

    def test_legacy_selection_keys_resolve_to_their_merged_family(self):
        bank=SegmentedModel([synthetic_course('rolling'),synthetic_course('intermediate')],validate=False)
        self.assertEqual(choose_model(bank,synthetic_course('rolling'),'rolling:short').metadata['profile'],'flat')
        self.assertEqual(choose_model(bank,synthetic_course('intermediate'),'intermediate:short').metadata['profile'],'mountain')
