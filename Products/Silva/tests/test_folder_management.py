# -*- coding: utf-8 -*-
# Copyright (c) 2011 Infrae. All rights reserved.
# See also LICENSE.txt
# $Id$

import unittest

from silva.core.interfaces import IContainerManager
from zope.interface.verify import verifyObject

from Products.Silva.testing import FunctionalLayer
from Products.Silva.testing import assertTriggersEvents, assertNotTriggersEvents


class EditorFolderManagementTestCase(unittest.TestCase):
    layer = FunctionalLayer
    user = 'editor'

    def setUp(self):
        self.root = self.layer.get_application()
        self.layer.login(self.user)

        factory = self.root.manage_addProduct['Silva']
        factory.manage_addFolder('folder', 'Folder')
        factory.manage_addAutoTOC('toc', 'AutoTOC')
        factory.manage_addPublication('publication', 'Publication')

        factory = self.root.folder.manage_addProduct['Silva']
        factory.manage_addFolder('subfolder', 'Sub Folder')
        factory.manage_addAutoTOC('toc', 'AutoTOC')
        factory.manage_addLink('link', 'Link')

    def test_implementation(self):
        manager = IContainerManager(self.root.folder, None)
        self.assertTrue(verifyObject(IContainerManager, manager))
        self.assertNotEqual(manager, None)

        manager = IContainerManager(self.root.toc, None)
        self.assertEqual(manager, None)

    def test_delete_single(self):
        manager = IContainerManager(self.root.folder)

        with assertTriggersEvents(
            'ObjectWillBeRemovedEvent',
            'ObjectRemovedEvent',
            'ContainerModifiedEvent'):
            with manager.deleter() as deleter:
                self.assertEqual(True, deleter.add(self.root.folder.toc))

        self.assertFalse('toc' in self.root.folder.objectIds())

    def test_delete_multiple(self):
        manager = IContainerManager(self.root.folder)

        with assertTriggersEvents(
            'ObjectWillBeRemovedEvent',
            'ObjectRemovedEvent',
            'ContainerModifiedEvent'):
            with manager.deleter() as deleter:
                self.assertEqual(True, deleter.add(self.root.folder.toc))
                self.assertEqual(True, deleter.add(self.root.folder.link))

        self.assertFalse('toc' in self.root.folder.objectIds())
        self.assertFalse('link' in self.root.folder.objectIds())

    def test_delete_invalid(self):
        manager = IContainerManager(self.root.folder)

        with assertNotTriggersEvents(
            'ObjectWillBeRemovedEvent',
            'ObjectRemovedEvent',
            'ContainerModifiedEvent'):
            with manager.deleter() as deleter:
                self.assertEqual(False, deleter.add(self.root.publication))
                self.assertEqual(False, deleter.add(self.root.toc))
                self.assertEqual(False, deleter.add(self.root.folder))

        self.assertTrue('publication' in self.root.objectIds())
        self.assertTrue('toc' in self.root.objectIds())
        self.assertTrue('folder' in self.root.objectIds())


class ChiefEditorFolderManagementTestCase(EditorFolderManagementTestCase):
    """Test folder management as a chiefeditor.
    """
    user = 'chiefeditor'


class ManagerFolderManagementTestCase(ChiefEditorFolderManagementTestCase):
    """Test folder management as a manager.
    """
    user = 'manager'


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(EditorFolderManagementTestCase))
    suite.addTest(unittest.makeSuite(ChiefEditorFolderManagementTestCase))
    suite.addTest(unittest.makeSuite(ManagerFolderManagementTestCase))
    return suite
