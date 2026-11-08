"""Morphologie du relief, frontières de distance et pondération prédictive."""
import unittest

from test_core import synthetic_course
from bzhaventure.analysis import model_catalog
from bzhaventure.gpx import adapt_course, describe_course, elapsed, resample_course
from bzhaventure.models import SegmentedModel, relief_similarity
from bzhaventure.prediction import predict
from bzhaventure.settings import CLASSIFICATION_VERSION, DISTANCE_CLASSES, PROFILE_LABELS


def wave(amplitude, period, length=20000, pace=.5):
    axis = [length*i/2000 for i in range(2001)]
    points = [(48, x/100000, 100+amplitude*(1-abs(2*((x%period)/period)-1)), x*pace) for x in axis]
    return adapt_course([(axis,points,points)])


class MorphologyTests(unittest.TestCase):
    def test_five_distance_classes_have_exact_boundaries(self):
        for length, expected in [(19999,'very_short'),(20000,'short'),(49999,'short'),
                                 (50000,'medium'),(100000,'long'),(160000,'ultra')]:
            with self.subTest(length=length):
                self.assertEqual(describe_course(synthetic_course('flat',length=length))['distanceClass'],expected)

    def test_equal_elevation_density_can_have_different_relief_shapes(self):
        coast = describe_course(wave(60,1000))
        mountain = describe_course(wave(600,10000))
        self.assertEqual(coast['profile'],'sawtooth')
        self.assertEqual(mountain['profile'],'mountain')
        self.assertLess(abs(coast['ascentDensity']/mountain['ascentDensity']-1),.1)

    def test_isolated_small_altitude_noise_does_not_create_hills(self):
        axis = list(range(0,10001,10))
        points = [(48,x/100000,100+(1 if i%2 else -1),x*.5) for i,x in enumerate(axis)]
        result = describe_course(adapt_course([(axis,points,points)]))
        self.assertEqual(result['profile'],'flat')
        self.assertEqual(result['climbCount'],0)

    def test_composition_and_mixed_profile_are_explicit(self):
        for profile in PROFILE_LABELS:
            descriptor = describe_course(synthetic_course(profile))
            self.assertEqual(descriptor['version'],CLASSIFICATION_VERSION)
            self.assertEqual(descriptor['profile'],profile)
            self.assertAlmostEqual(sum(descriptor['climbShares'].values()),0 if profile=='flat' else 1)
            self.assertEqual(sum(descriptor['climbCounts'].values()),descriptor['climbCount'])

    def test_long_ascent_with_moderate_gain_is_mountain(self):
        axis = list(range(0,12001,25))
        points = [(48,x/100000,100+350*(1-abs(x/6000-1)),x*.5) for x in axis]
        descriptor = describe_course(adapt_course([(axis,points,points)]))
        self.assertEqual(descriptor['profile'],'mountain')
        self.assertGreater(descriptor['climbShares']['large'],.99)

    def test_segment_break_does_not_create_an_artificial_ascent(self):
        first = synthetic_course('flat',length=10000)
        axis, original, _ = first[0]
        upper = [(p[0],p[1],p[2]+2000,p[3]+10000) for p in original]
        descriptor = describe_course(adapt_course([first[0],(axis,upper,upper)]))
        self.assertEqual(descriptor['profile'],'flat')
        self.assertEqual(descriptor['ascent'],0)

    def test_classification_is_independent_of_prediction_sampling(self):
        course = wave(60,1000)
        initial = describe_course(course)
        for step in (25,100,250):
            self.assertEqual(describe_course(resample_course(course,step)),initial)


class MorphologicalModelTests(unittest.TestCase):
    def test_nearer_morphology_receives_more_training_weight(self):
        close = wave(50,500,pace=.4)
        other = wave(90,800,pace=.8)
        target = wave(50,500)
        descriptor = describe_course(target)
        self.assertEqual(descriptor['profile'],describe_course(other)['profile'])
        self.assertEqual(relief_similarity(describe_course(close),descriptor),1)
        self.assertLess(relief_similarity(describe_course(other),descriptor),1)
        model = SegmentedModel([close,other],validate=False).for_course(target)
        self.assertTrue(model.metadata['morphologyWeighted'])
        self.assertGreater(model.metadata['referenceWeights'][0],model.metadata['referenceWeights'][1])
        self.assertGreater(predict(target,model,5000)[-1][1],0)

    def test_all_twenty_groups_are_available_in_catalogue(self):
        courses = [synthetic_course('intermediate'),synthetic_course('sawtooth')]
        bank = SegmentedModel(courses,validate=False)
        references = [dict(name=str(i),actual=elapsed(c),estimated=None) for i,c in enumerate(courses)]
        progress = []
        catalog = model_catalog(bank,references,lambda *args:progress.append(args))
        self.assertEqual(len(catalog),len(PROFILE_LABELS)*len(DISTANCE_CLASSES))
        self.assertEqual(len({(m['profile'],m['distanceClass']) for m in catalog}),20)
        self.assertTrue(all(event[-1]==20 for event in progress))
