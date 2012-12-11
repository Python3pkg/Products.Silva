# -*- coding: utf-8 -*-

import unittest
from Products.Silva.testing import FunctionalLayer


class TestNameChooser(unittest.TestCase):

    layer = FunctionalLayer

    def setUp(self):
        self.root = self.layer.get_application()
        self.factory = self.root.manage_addProduct['Silva']

    def test_create_invalid_characters(self):
        """ Invalid characters a replaced.
        """
        with self.assertRaises(ValueError):
            self.factory.manage_addMockupVersionedContent('it*em', 'Item')

    def test_create_already_exists(self):
        """ A content with the same name is present in the folder.
        """
        self.factory.manage_addMockupVersionedContent('item', 'Item')
        with self.assertRaises(ValueError):
            self.factory.manage_addMockupVersionedContent('item', 'Item')

    def test_unicode(self):
        self.factory.manage_addMockupVersionedContent(u'item', u'Title')
        item = self.root._getOb('item', None)
        self.assertTrue(item)

    def test_unicode_invalid_characters(self):
        with self.assertRaises(ValueError):
            self.factory.manage_addMockupVersionedContent(u'itéám', u'Title')



def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestNameChooser))
    return suite
