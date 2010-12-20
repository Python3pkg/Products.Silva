# -*- coding: utf-8 -*-
# Copyright (c) 2008-2010 Infrae. All rights reserved.
# See also LICENSE.txt
# $Id$

import unittest
from pkg_resources import resource_listdir

from zope.interface.verify import verifyObject
from zope.testing import doctest

from Testing import ZopeTestCase
from Testing.ZopeTestCase.zopedoctest.functional import getRootFolder, sync
from AccessControl.SecurityManagement import newSecurityManager, \
    noSecurityManager

import five.grok.testing

from Products.Silva.tests.layer import SilvaLayer, setUp, tearDown
from Products.Silva.tests.SilvaBrowser import SilvaBrowser
from Products.Silva.tests.SilvaTestCase import SilvaFunctionalTestCase

def logAsUser(app, username):
    """Login as the given user.
    """
    if username is None:
        noSecurityManager()
    else:
        uf = app.root.acl_users
        user = uf.getUserById(username).__of__(uf)
        newSecurityManager(None, user)


extraglobs = {'logAsUser': logAsUser,
              'SilvaBrowser': SilvaBrowser,
              'verifyObject': verifyObject,
              'getRootFolder': getRootFolder,
              'sync': sync,
              'grok': five.grok.testing.grok,}


def suiteFromPackage(name, module_base="Products.Silva.tests"):
    files = resource_listdir(module_base, name)
    suite = unittest.TestSuite()
    for filename in files:
        if not filename.endswith('.py'):
            continue
        if filename.endswith('_fixture.py'):
            continue
        if filename == '__init__.py':
            continue

        dottedname = '%s.%s.%s' % (module_base, name, filename[:-3])
        test = ZopeTestCase.FunctionalDocTestSuite(
            dottedname,
            test_class=SilvaFunctionalTestCase,
            setUp=setUp,
            tearDown=tearDown,
            extraglobs=extraglobs,
            optionflags=doctest.ELLIPSIS + doctest.NORMALIZE_WHITESPACE)

        test.layer = SilvaLayer
        suite.addTest(test)
    return suite

def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(suiteFromPackage('grok'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')