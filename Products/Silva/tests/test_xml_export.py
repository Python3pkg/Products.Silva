# -*- coding: utf-8 -*-
# Copyright (c) 2002-2012 Infrae. All rights reserved.
# See also LICENSE.txt

# Python
from zipfile import ZipFile
import re
import io
import unittest

from zope.component import getAdapter, getUtility

# Silva
from Products.Silva.testing import FunctionalLayer, TestCase, TestRequest

from silva.core import interfaces
from silva.core.interfaces.errors import ExternalReferenceError
from silva.core.services.interfaces import IMetadataService
from silva.core.xml.xmlexport import Exporter, registry


DATETIME_RE = re.compile(
    r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z')


class SilvaXMLTestCase(TestCase):
    """Basic TestCase to test XML export features.
    """
    layer = FunctionalLayer

    def setUp(self):
        self.root = self.layer.get_application()
        self.layer.login('author')

    def getNamespaces(self):
        # this is needed because we don't know the namespaces registered
        # with the exported.  These are dynamic and depend on the extensions
        # which are using the exporter.  This function is an attempt at
        # dynamically inserting the namespaces, and hopefully gets the
        # order correct.
        nss = []
        for prefix, uri in sorted(registry.getNamespaces(True)):
            nss.append('xmlns:%s="%s"' % (prefix, uri))
        return ' '.join(nss)

    def getVersion(self):
        return 'Silva %s' % self.root.get_silva_software_version()

    def genericize(self, string):
        return DATETIME_RE.sub(r'YYYY-MM-DDTHH:MM:SS', string)

    def assertExportFail(self, content, error=ExternalReferenceError):
        exporter = Exporter(content, TestRequest())
        with self.assertRaises(error):
            exporter.getString()
        return exporter

    def assertExportEqual(self, content, filename):
        """Verify that the xml result of an export is the same than
        the one contained in a test file.
        """
        exporter = Exporter(content, TestRequest())
        with self.layer.open_fixture(filename) as xml_file:
            expected_xml = xml_file.read().format(
                namespaces=self.getNamespaces(),
                version=self.getVersion())
            actual_xml = self.genericize(exporter.getString())
            self.assertXMLEqual(expected_xml, actual_xml)
        return exporter


class XMLExportTestCase(SilvaXMLTestCase):
    """Test XML Exporter.
    """

    def setUp(self):
        super(XMLExportTestCase, self).setUp()
        factory = self.root.manage_addProduct['Silva']
        factory.manage_addFolder(
            'folder', 'This is <boo>a</boo> folder',
            policy_name='Silva AutoTOC')

    def test_folder_autotoc_index(self):
        """Export a folder.
        """
        factory = self.root.folder.manage_addProduct['Silva']
        factory.manage_addFolder('folder', 'This is &another; a subfolder')
        factory = self.root.folder.folder.manage_addProduct['Silva']
        factory.manage_addAutoTOC('index', 'This is &another; a subfolder')

        exporter = self.assertExportEqual(
            self.root.folder,
            'test_export_folder.silvaxml')
        self.assertEqual(exporter.getZexpPaths(), [])
        self.assertEqual(exporter.getAssetPaths(), [])

    def test_fallback(self):
        """Test the fallback exporter: create a Zope 2 folder in a
        Silva folder and export it.
        """
        factory = self.root.folder.manage_addProduct['Silva']
        factory.manage_addMockupVersionedContent('mockup', 'Mockup Content')

        exporter = self.assertExportEqual(
            self.root.folder,
            'test_export_fallback.silvaxml')
        self.assertEqual(
            exporter.getZexpPaths(),
            [(('', 'root', 'folder', 'mockup'), '1.zexp')])
        self.assertEqual(
            exporter.getAssetPaths(),
            [])
        self.assertEqual(
            exporter.getProblems(),
            [])

    def test_indexer(self):
        """Export an indexer.
        """
        factory = self.root.folder.manage_addProduct['Silva']
        factory.manage_addIndexer('indexer', 'Index of this site')

        metadata = getUtility(IMetadataService).getMetadata(
            self.root.folder.indexer)
        metadata.setValues(
            'silva-extra',
            {'content_description': 'Index the content of your website.',
             'comment': 'Nothing special is required.'})

        exporter = self.assertExportEqual(
            self.root.folder,
            'test_export_indexer.silvaxml')
        self.assertEqual(exporter.getZexpPaths(), [])
        self.assertEqual(exporter.getAssetPaths(), [])
        self.assertEqual(exporter.getProblems(), [])

    def test_ghost(self):
        """Export a ghost.
        """
        factory = self.root.folder.manage_addProduct['Silva']
        factory.manage_addLink(
            'link', 'New website', url='http://infrae.com/', relative=False)
        factory.manage_addGhost(
            'ghost', None, haunted=self.root.folder.link)

        exporter = self.assertExportEqual(
            self.root.folder,
            'test_export_ghost.silvaxml')
        self.assertEqual(exporter.getZexpPaths(), [])
        self.assertEqual(exporter.getAssetPaths(), [])
        self.assertEqual(exporter.getProblems(), [])

    def test_ghost_outside_of_export(self):
        """Export a ghost that link something outside of export tree.
        """
        factory = self.root.manage_addProduct['Silva']
        factory.manage_addLink(
            'link', 'New website', url='http://infrae.com/', relative=False)
        factory = self.root.folder.manage_addProduct['Silva']
        factory.manage_addGhost(
            'ghost', None, haunted=self.root.folder.link)

        self.assertExportFail(self.root.folder)

    def test_ghost_folder(self):
        """Export a ghost folder.
        """
        self.layer.login('chiefeditor')
        factory = self.root.folder.manage_addProduct['Silva']
        factory.manage_addFolder('container', 'Content')
        factory.manage_addGhostFolder(
            'ghost', None, haunted=self.root.folder.container)
        factory = self.root.folder.container.manage_addProduct['Silva']
        factory.manage_addAutoTOC('index', 'Content')
        factory.manage_addLink(
            'link', 'Infrae', url='http://infrae.com', relative=False)
        factory.manage_addFile('file', 'Torvald blob')

        self.root.folder.ghost.haunt()
        self.layer.login('author')

        exporter = self.assertExportEqual(
            self.root.folder,
            'test_export_ghostfolder.silvaxml')
        self.assertEqual(
            exporter.getZexpPaths(),
            [])
        self.assertEqual(
            exporter.getAssetPaths(),
            [(('', 'root', 'folder', 'container', 'file'), '1')])
        self.assertEqual(
            exporter.getProblems(),
            [])

    def test_ghost_folder_outside_of_export(self):
        """Export a ghost folder but not the ghosted folder.
        """
        self.layer.login('chiefeditor')
        factory = self.root.folder.manage_addProduct['Silva']
        factory.manage_addFolder('container', 'Content')
        factory = self.root.manage_addProduct['Silva']
        factory.manage_addGhostFolder(
            'ghost', None, haunted=self.root.folder.container)
        factory = self.root.folder.container.manage_addProduct['Silva']
        factory.manage_addLink(
            'link', 'Infrae', url='http://infrae.com', relative=False)
        factory.manage_addFile('file', 'Torvald blob')

        self.root.ghost.haunt()
        self.layer.login('author')
        self.assertExportFail(self.root.ghost)

    def test_link_relative(self):
        """Export a link with to an another Silva object.
        """
        factory = self.root.folder.manage_addProduct['Silva']
        factory.manage_addFile('file', 'Torvald file')
        factory.manage_addFolder('new', 'New changes')
        factory = self.root.folder.new.manage_addProduct['Silva']
        factory.manage_addLink(
            'link', 'Last file',
            relative=True, target=self.root.folder.file)

        exporter = self.assertExportEqual(
            self.root.folder,
            'test_export_link.silvaxml')
        self.assertEqual(
            exporter.getZexpPaths(),
            [])
        self.assertEqual(
            exporter.getAssetPaths(),
            [(('', 'root', 'folder', 'file'), '1')])
        self.assertEqual(
            exporter.getProblems(),
            [])

    def test_link_relative_outside_of_export(self):
        """Export a link with to an another Silva object.
        """
        factory = self.root.manage_addProduct['Silva']
        factory.manage_addFile('file', 'Torvald file')
        factory = self.root.folder.manage_addProduct['Silva']
        factory.manage_addLink(
            'link', 'Last file', relative=True, target=self.root.file)

        self.assertExportFail(self.root.folder)

    def test_broken_references(self):
        """Test export of broken references.
        """
        factory = self.root.folder.manage_addProduct['Silva']
        factory.manage_addLink('link', 'Broken Link', relative=True)
        factory.manage_addGhost('ghost', None)

        exporter = self.assertExportEqual(
            self.root.folder, 'test_export_broken_references.silvaxml')
        self.assertEqual(exporter.getZexpPaths(), [])
        self.assertEqual(exporter.getAssetPaths(), [])
        self.assertEqual(exporter.getProblems(), [])


class ZipTestCase(TestCase):
    """Test Zip import/export.
    """
    layer = FunctionalLayer

    def setUp(self):
        self.root = self.layer.get_application()
        factory = self.root.manage_addProduct['Silva']
        factory.manage_addFolder('folder', 'Folder')

    def test_zip_export(self):
        """Import/export a Zip file.
        """
        # XXX This test needs improvement.
        with self.layer.open_fixture('test1.zip') as zip_import:
            importer = interfaces.IArchiveFileImporter(self.root.folder)
            succeeded, failed = importer.importArchive(zip_import)

        self.assertItemsEqual(
            succeeded,
            ['testzip/Clock.swf', 'testzip/bar/image2.jpg',
             'testzip/foo/bar/baz/image5.jpg', 'testzip/foo/bar/image4.jpg',
             'testzip/foo/image3.jpg', 'testzip/image1.jpg',
             'testzip/sound1.mp3'])
        self.assertItemsEqual(failed, [])

        exporter = getAdapter(
            self.root.folder, interfaces.IContentExporter, name='zip')
        export = exporter.export(TestRequest(), stream=io.BytesIO())
        export.seek(0)

        zip_export = ZipFile(export, 'r')
        self.assertItemsEqual(
            ['assets/1.jpg', 'assets/2.jpg', 'assets/3.jpg',
             'assets/4.jpg', 'assets/5.swf', 'assets/6.jpg',
             'assets/7.mp3', 'silva.xml'],
            zip_export.namelist())
        zip_export.close()


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(ZipTestCase))
    suite.addTest(unittest.makeSuite(XMLExportTestCase))
    return suite
