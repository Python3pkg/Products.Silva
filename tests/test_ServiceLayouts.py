# Copyright (c) 2003 Infrae. All rights reserved.
# See also LICENSE.txt
# $Id $

import os, sys
if __name__ == '__main__':
    execfile(os.path.join(sys.path[0], 'framework.py'))
    moduleFilename = sys.argv[0]
else:
    moduleFilename = __file__
moduleFilename = os.path.abspath(moduleFilename)    
modulePathname = os.path.dirname(moduleFilename)
    
import SilvaTestCase
from Testing import ZopeTestCase


from Products.Silva.LayoutRegistry import layoutRegistry
from Products.Silva.fssite import registerDirectory


layoutTest1 = 'test1'
layoutTest2 = 'test2'
layoutTest1_dir = 'layout_test1'
layoutTest2_dir = 'layout_test2'

import os
layoutTest1Items = ['template', 'test1.html']
layoutTest2Items = ['template', 'test2.html']

layoutRegistry.register(
       layoutTest1, 'test 1 Layout', moduleFilename, layoutTest1_dir)
layoutRegistry.register(
       layoutTest2, 'test 2 Layout', moduleFilename, layoutTest2_dir)

from Products.Silva import Publication, Root
# XXX ugh, awful monkey patch
Publication.Publication.cb_isMoveable = lambda self: 1
# manage_main hacks to copy succeeds
Root.Root.manage_main = lambda *foo, **bar: None

class TestInstallLayouts(SilvaTestCase.SilvaTestCase):


    def afterSetUp(self):
        self.setRoles(['Manager'])
        self.service_layouts = self.root.service_layouts

    def testSetup(self):
        self.failUnless(hasattr(self.root, 'service_layouts'))
        self.failUnless(hasattr(self.root.service_resources, 'Layouts'))
        self.assertEqual(len(self.service_layouts.get_names()), 2)
        self.failUnless(layoutTest1 in self.service_layouts.get_names())
        self.assertEqual(len(self.service_layouts.get_installed_names()),0)

    def testInstall(self):
        self.service_layouts.install(layoutTest1)
        self.assertEqual(len(self.service_layouts.get_installed_names()),1)
        self.failUnless(layoutTest1 in self.service_layouts.get_installed_names())
        self.failUnless(self.service_layouts.is_installed(layoutTest1))
        self.failUnless(hasattr(self.root.service_resources.Layouts, layoutTest1_dir))

    def testUninstall(self):
        self.service_layouts.install(layoutTest1)
        self.service_layouts.uninstall(layoutTest1)
        self.assertEqual(len(self.service_layouts.get_installed_names()),0)
        self.failIf(layoutTest1 in self.service_layouts.get_installed_names())
        self.failIf(self.service_layouts.is_installed(layoutTest1))

class TestServiceLayouts(SilvaTestCase.SilvaTestCase):

    def afterSetUp(self):
        self.setRoles(['Manager'])
        self.service_layouts = self.root.service_layouts
        self.service_layouts.install(layoutTest1)
        self.service_layouts.install(layoutTest2)

    def testSetupInPublication(self):
        self.add_publication(self.root, 'pub', 'publication')
        self.failUnless(self.root.pub)
        self.pub = self.root.pub
        self.failIf(self.service_layouts.layout_items(self.pub))     
        # setup layout
        self.service_layouts.setup_layout(layoutTest1, self.pub)
        for id in layoutTest1Items:
            self.failUnless(id in self.pub.objectIds())
        self.failUnless(self.service_layouts.has_layout(self.pub))
        for id in layoutTest1Items:
            self.failUnless(id in self.service_layouts.layout_items(self.pub))
        # remove layout
        self.service_layouts.remove_layout(self.pub)
        self.failIf(self.service_layouts.has_layout(self.pub))
        self.failIf(self.service_layouts.layout_items(self.pub))     
        for id in layoutTest1Items:
            self.failIf(id in self.pub.objectIds())

    def testSetupOnPublication(self):
        self.add_publication(self.root, 'pub', 'publication')
        self.failUnless(self.root.pub)
        self.pub = self.root.pub
        self.pub.set_layout(layoutTest2)
        self.pub.set_layout(layoutTest1)
        self.checkLayoutTest1(self.pub)

    def checkLayoutTest1(self, pub):
        for id in layoutTest1Items:
            self.failUnless(id in pub.objectIds())
        self.failUnless(self.service_layouts.has_layout(pub))
        for id in layoutTest1Items:
            self.failUnless(id in self.service_layouts.layout_items(pub))

    def checkLayoutTest2(self, pub):
        for id in layoutTest2Items:
            self.failUnless(id in pub.objectIds())
        self.failUnless(self.service_layouts.has_layout(pub))
        for id in layoutTest2Items:
            self.failUnless(id in self.service_layouts.layout_items(pub))

    def testCopyPaste(self):        
        self.add_publication(self.root, 'pub', 'publication')
        self.failUnless(self.root.pub)
        self.pub = self.root.pub
        self.pub.set_layout(layoutTest1)
        self.checkLayoutTest1(self.pub)
        self.root.action_copy(['pub'], self.app.REQUEST)
        self.root.action_paste(self.app.REQUEST)
        self.failUnless(self.root.copy_of_pub)
        self.copy_of_pub = self.root.copy_of_pub
        self.copy_of_pub.set_layout(layoutTest2)
        self.checkLayoutTest1(self.pub)
        self.checkLayoutTest2(self.copy_of_pub)

if __name__ == '__main__':
    framework()
else:
    # While framework.py provides its own test_suite()
    # method the testrunner utility does not.
    import unittest
    def test_suite():
        suite = unittest.TestSuite()
        suite.addTest(unittest.makeSuite(TestInstallLayouts))
        suite.addTest(unittest.makeSuite(TestServiceLayouts))
        return suite

