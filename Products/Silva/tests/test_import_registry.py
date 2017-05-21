# -*- coding: utf-8 -*-
# Copyright (c) 2003-2013 Infrae. All rights reserved.
# See also LICENSE.txt

import unittest

from Products.Silva.MimetypeRegistry import mimetypeRegistry as registry
from Products.Silva.testing import FunctionalLayer


class MimetypeRegistryTestCase(unittest.TestCase):
    layer = FunctionalLayer

    def setUp(self):
        self.root = self.layer.get_application()
        self.layer.login('editor')

    def test_register(self):
        marker = object()
        factory = object()
        mimetype = 'application/x-test-mimetype-1'

        self.assertEqual(registry.get(mimetype), registry.DEFAULT.__func__)

        registry.register(mimetype, factory, 'Silva')
        self.assertEqual(registry.get(mimetype), factory)
        self.assertEqual(registry.get(mimetype, marker), factory)

        mimetype2 = 'application/x-test-mimetype-2'
        registry.register(mimetype2, factory, 'Silva')
        self.assertEqual(registry.get(mimetype2), factory)

    def test_unregister(self):
        factory = object()
        mimetype = 'application/x-test-mimetype-1'
        mimetype2 = 'application/x-test-mimetype-2'
        registry.register(mimetype, factory, 'Silva')
        registry.register(mimetype2, factory, 'Silva')
        self.assertEqual(registry.get(mimetype), factory)
        self.assertEqual(registry.get(mimetype2), factory)

        registry.unregister(factory)

        self.assertEqual(registry.get(mimetype), registry.DEFAULT.__func__)
        self.assertEqual(registry.get(mimetype2), registry.DEFAULT.__func__)


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(MimetypeRegistryTestCase))
    return suite
