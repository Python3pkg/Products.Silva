# Copyright (c) 2002 Infrae. All rights reserved.
# See also LICENSE.txt
# $Revision: 1.22.8.1 $
import os, sys
if __name__ == '__main__':
    execfile(os.path.join(sys.path[0], 'framework.py'))

from Testing import ZopeTestCase
import SilvaTestCase

from DateTime import DateTime

class SilvaObjectTestCase(SilvaTestCase.SilvaTestCase):
    """Test the SilvaObject interface.
    """
    def afterSetUp(self):

        self.folder = self.add_folder(self.root, 'folder','Folder',
                                      policy_name='Silva Document')
        self.publication = self.add_publication(self.root,
                                                'publication','Publication')
        self.document = self.add_document(self.root, 'document','Document')
        self.document2 = self.add_document(self.root, 'document2','')
        
        # add some stuff to test breadcrumbs
        self.subfolder = self.add_folder(self.folder, 'subfolder', 'Subfolder')
        self.subsubdoc = self.add_document(self.subfolder,
                                           'subsubdoc', 'Subsubdoc')


##     def test_set_title(self):
##         self.document.set_title('Document2')
##         self.assertEquals(self.document.get_title_editable(), 'Document2')
##         self.folder.set_title('Folder2')
##         self.assertEquals(self.folder.get_title_editable(), 'Folder2')
##         self.assertEquals(self.folder.index.get_title_editable(), 'Folder2')
##         self.root.set_title('Root2')
##         self.assertEquals(self.root.get_title_editable(), 'Root2')
##         self.publication.set_title('Publication2')
##         self.assertEquals(self.publication.get_title_editable(), 'Publication2')
##         
##         self.folder.index.set_title('Set by default')
##         self.assertEquals(self.folder.index.get_title(),
##                           'Set by default')
##         self.assertEquals(self.folder.get_title(),
##                           'Set by default')
        
##     def test_title(self):
##         self.assertEquals(self.document.get_title_editable(), 'Document')
##         self.assertEquals(self.folder.get_title_editable(), 'Folder')
##         self.assertEquals(self.root.get_title_editable(), 'Root')
##         self.assertEquals(self.publication.get_title_editable(), 'Publication')
##         self.assertEquals(self.folder.index.get_title_editable(), 'Folder')
        
##     def test_title3(self):
##         # Test get_title_or_id
##         self.assertEquals(self.document.get_title_or_id_editable(), 'Document')
##         self.assertEquals(self.document2.get_title_or_id_editable(), 'document2')


    def test_title_on_version(self):
        self.add_document(self.folder, 'adoc', 'document')
	self.folder.adoc.set_unapproved_version_publication_datetime(
            DateTime() - 1)
        self.folder.adoc.approve_version()
        self.folder.adoc.create_copy()
        self.folder.adoc.set_title('document2')
        self.assertEquals(self.folder.adoc.get_title_editable(), 'document2')
        self.assertEquals(self.folder.adoc.get_title(), 'document')


#    def test_title4(self):
#        self.folder.index.set_unapproved_version_publication_datetime(
#            DateTime() - 1)
#        self.folder.index.approve_version()
#        self.folder.index.create_copy()
#        self.folder.index.set_title('folder 2')
#        self.assertEquals(self.folder.get_title_editable(), 'folder 2')
#        self.assertEquals(self.folder.index.get_title_editable(), 'folder 2')
#        self.assertEquals(self.folder.get_title(), 'Folder')
#        self.assertEquals(self.folder.index.get_title(), 'Folder')
        
#    def test_title5(self):
#        self.folder.index.set_unapproved_version_publication_datetime(
#            DateTime() - 1)
#        self.folder.index.approve_version()
#        self.folder.index.create_copy()
#        self.folder.set_title('folder 2')
#        self.assertEquals(self.folder.get_title_editable(), 'folder 2')
#        self.assertEquals(self.folder.index.get_title_editable(), 'folder 2')
#        self.assertEquals(self.folder.get_title(), 'Folder')
#        self.assertEquals(self.folder.get_title(), 'Folder')

    def test_title6(self):
        self.folder.set_title('folder 2')
        self.assertEquals(self.folder.get_title_editable(), 'folder 2')
           
    #def test_get_creation_datetime(self):
    #    pass

    #def test_get_modification_datetime(self):
    #    pass

    def test_get_breadcrumbs(self):
        self.assertEquals([self.root],
                          self.root.get_breadcrumbs())
        self.assertEquals([self.root, self.document],
                          self.document.get_breadcrumbs())
        self.assertEquals([self.root, self.publication],
                          self.publication.get_breadcrumbs())
        self.assertEquals([self.root, self.folder],
                          self.folder.get_breadcrumbs())
        self.assertEquals([self.root, self.folder, self.subfolder],
                          self.subfolder.get_breadcrumbs())
        self.assertEquals([self.root, self.folder,
                           self.subfolder, self.subsubdoc],
                          self.subsubdoc.get_breadcrumbs())

if __name__ == '__main__':
    framework()
else:
    # While framework.py provides its own test_suite()
    # method the testrunner utility does not.
    import unittest
    def test_suite():
        suite = unittest.TestSuite()
        suite.addTest(unittest.makeSuite(SilvaObjectTestCase))
        return suite

