# Copyright (c) 2003-2009 Infrae. All rights reserved.
# See also LICENSE.txt
# $Id $

import SilvaTestCase
import unittest


class LinkTestCase(SilvaTestCase.SilvaTestCase):
    """Test Silva Link object features.
    """

    def test_set_absolute_link(self):
        """Test to set the link url and check its result.
        """

        self.root.manage_addProduct['Silva'].manage_addLink(
            'link', 'Google', 'http://google.com', link_type='absolute')
        content = self.root.link

        link = content.get_editable()
        self.assertEqual(link.get_link_type(), 'absolute')
        self.assertEqual(link.get_url(), 'http://google.com')

        link.set_url('http://launchpad.net')
        self.assertEqual(link.get_url(), 'http://launchpad.net')

        link.set_url('infrae.com')
        self.assertEqual(link.get_url(), 'http://infrae.com')

    def test_set_relative_link(self):
        """Test to set the link url and check its result.
        """

        self.root.manage_addProduct['Silva'].manage_addLink(
            'link', 'Bla', 'folder/bla', link_type='relative')
        content = self.root.link

        link = content.get_editable()
        self.assertEqual(link.get_link_type(), 'relative')
        self.assertEqual(link.get_url(), 'folder/bla')

        link.set_url('infrae.com')
        self.assertEqual(link.get_url(), 'infrae.com')


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(LinkTestCase))
    return suite