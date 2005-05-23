#!/usr/bin/python

import os, sys
if __name__ == '__main__':
    execfile(os.path.join(sys.path[0], 'framework.py'))

from Interface.Verify import verifyClass
from Interface.Exceptions import BrokenImplementation, DoesNotImplement, BrokenMethodImplementation
import SilvaTestCase
from Products.Silva.silvaxml import xmlimport
from Products.Silva.transform.interfaces import IRenderer
xslt = True
try: 	 
    from Products.Silva.transform.renderer.imagesonrightrenderer import ImagesOnRightRenderer
    from Products.Silva.transform.renderer.xsltrendererbase import RenderError
except ImportError: 	
    xslt = False

directory = os.path.dirname(__file__)

class ImagesOnRightRendererTest(SilvaTestCase.SilvaTestCase):

    def test_implements_renderer_interface(self):
        if not xslt:
            return
        images_on_right = ImagesOnRightRenderer()
        try:
            verifyClass(IRenderer, ImagesOnRightRenderer)
        except (BrokenImplementation, DoesNotImplement, BrokenMethodImplementation):
            self.fail("ImagesOnRightRenderer does not implement IRenderer")

    def test_renders_images_on_right(self):
        if not xslt:
            return
        importfolder = self.add_folder(
            self.root,
            'silva_xslt',
            'This is a testfolder',
            policy_name='Auto TOC')
        xmlimport.initializeXMLImportRegistry()
        importer = xmlimport.theXMLImporter
        test_settings = xmlimport.ImportSettings()
        test_info = xmlimport.ImportInfo()
        source_file = open(os.path.join(directory, "data/test_document2.xml"))
        importer.importFromFile(
            source_file, result = importfolder,
            settings = test_settings, info = test_info)
        source_file.close()
        # XXX get a (which?) version
        obj = self.root.silva_xslt.test_document

        images_on_right = ImagesOnRightRenderer()
        self.assertEquals(images_on_right.render(obj), '<table><tr>\n<td valign="top">unapproved<h2 class="heading">This is a rendering test</h2>\n<p class="p">This is a test of the XSLT rendering functionality.</p>\n</td>\n<td valign="top">\n<a href="bar.html"><img src="foo"></a><br>\n</td>\n</tr></table>\n')
        
    def test_error_handling(self):
        
        if not xslt:
            return

        class BrokenImagesOnRightRenderer(ImagesOnRightRenderer):
            def __init__(self):
                ImagesOnRightRenderer.__init__(self)
                self._stylesheet_path = os.path.join(
                    directory,
                    "data/images_to_the_right_broken.xslt")

        importfolder = self.add_folder(
            self.root,
            'silva_xslt',
            'This is a testfolder',
            policy_name='Auto TOC')
        xmlimport.initializeXMLImportRegistry()
        importer = xmlimport.theXMLImporter
        test_settings = xmlimport.ImportSettings()
        test_info = xmlimport.ImportInfo()
        source_file = open(os.path.join(directory, "data/test_document2.xml"))
        importer.importFromFile(
            source_file, result = importfolder,
            settings = test_settings, info = test_info)
        source_file.close()
        # XXX get a (which?) version
        obj = self.root.silva_xslt.test_document

        images_on_right = BrokenImagesOnRightRenderer()
        self.assertRaises(RenderError, images_on_right.render, obj)

if __name__ == '__main__':
    framework()
else:
    import unittest
    def test_suite():
        suite = unittest.TestSuite()
        suite.addTest(unittest.makeSuite(ImagesOnRightRendererTest))
        return suite
