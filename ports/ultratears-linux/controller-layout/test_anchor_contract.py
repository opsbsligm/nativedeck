#!/usr/bin/env python3
"""Public synthetic tests; no private/game fixtures or original resource bytes."""
import copy
import unittest
from anchor_contract import arithmetic, coverage_points, validate

class AnchorContractTests(unittest.TestCase):
    def doc(self):
        return dict(width=800,height=400,anchors=[dict(id='dpad_center',pixel=[30.,60.],source=[2.,5.])],transform=dict(x='100 + x * 2 + y / 3',y='-5 + y * 0.4'))
    def test_pixel_is_authoritative(self):
        d=self.doc();a=validate(d);ps=coverage_points('CrossKey',a,d)
        d2=copy.deepcopy(d);d2['anchors'][0]['pixel']=[44.,74.];ps2=coverage_points('CrossKey',validate(d2),d2)
        for p,q in zip(ps,ps2):self.assertAlmostEqual(q[0]-p[0],14.);self.assertAlmostEqual(q[1]-p[1],14.)
    def test_explicit_group_points_need_no_projection(self):
        d=self.doc();d['transform']={'x':'unsupported_function(x)','y':'y'};d['group_coverage']={'CrossKey':[[20.,50.],[40.,70.]]}
        self.assertEqual(coverage_points('CrossKey',validate(d),d),d['group_coverage']['CrossKey'])
    def test_bounds_and_radius(self):
        d=self.doc();d['anchors'][0]['coverage_bounds']=[20,40,50,80]
        self.assertEqual(set(map(tuple,coverage_points('CrossKey',validate(d),d))),{(20,40),(20,80),(50,40),(50,80)})
        d['anchors'][0].pop('coverage_bounds');d['anchors'][0]['coverage_radius']=3
        self.assertEqual(set(map(tuple,coverage_points('CrossKey',validate(d),d))),{(27,57),(27,63),(33,57),(33,63)})
    def test_coverage_points_override(self):
        d=self.doc();d['anchors'][0]['coverage_points']=[[1,2],[3,4]]
        self.assertEqual(coverage_points('CrossKey',validate(d),d),[[1,2],[3,4]])
    def test_arbitrary_projection(self):self.assertAlmostEqual(arithmetic('(x+2)/4-y*3',6,2),-4)
    def test_code_and_nonfinite_rejected(self):
        for expr in ["__import__('os')",'x.__class__','[x,y][0]','1e309','x**2']:
            with self.assertRaises(ValueError):arithmetic(expr,1,2)
    def test_duplicate_and_nan_rejected(self):
        d=self.doc();d['anchors'].append(d['anchors'][0])
        with self.assertRaises(ValueError):validate(d)
        d=self.doc();d['anchors'][0]['pixel'][0]=float('nan')
        with self.assertRaises(ValueError):validate(d)

if __name__=='__main__':unittest.main()
