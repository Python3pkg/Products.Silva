import os, sys
if __name__ == '__main__':
    execfile(os.path.join(sys.path[0], 'framework.py'))

import SilvaTestCase
from DateTime import DateTime 

from Products.Silva.interfaces import IVersion
# XXX unfortunately have to import these to hack the security machinery
from Products.SilvaDocument.Document import Document
from Products.Silva.Folder import Folder
from Products.Silva.Image import Image

# XXX ugh would really like to avoid this..
Document.cb_isMoveable = lambda self: 1
Folder.cb_isMoveable = lambda self: 1
Image.cb_isMoveable = lambda self: 1
        
class CatalogTestCase(SilvaTestCase.SilvaTestCase):

    def assertStatus(self, path, statuses):
        results = self.catalog.searchResults(version_status=statuses,
                                             path=path)
        # should get as many entries as statuses
        self.assertEquals(len(statuses), len(results))

        # make sure the statuses are the same
        statuses.sort()
        catalog_statuses = []
        for brain in results:
            object = brain.getObject()
            self.assert_(IVersion.isImplementedBy(object))
            catalog_statuses.append(object.version_status())
        catalog_statuses.sort()
        self.assertEquals(statuses, catalog_statuses)

    def assertPath(self, path):
        results = self.catalog.searchResults(path=path)
        for brain in results:
            if brain.getPath() == path:
                return
        self.fail()
        
    def assertNoPath(self, path):
        results = self.catalog.searchResults(path=path)
        for brain in results:
            if brain.getPath() == path:
                self.fail()
        
    def assertPristineCatalog(self):
        # the pristine catalog has no documents, just root
        results = self.catalog.searchResults()
        # the root itself and its index document 
        self.assertEquals(2, len(results))
        
class VersionCatalogTestCase(CatalogTestCase):

    def afterSetUp(self):
        self.silva.manage_addProduct['SilvaDocument'].manage_addDocument(
            'alpha', 'Alpha')
        self.alpha = self.silva.alpha
        
    def test_pristine(self): 
        self.silva.manage_delObjects(['alpha'])
        self.assertPristineCatalog()

    def test_unapproved(self):
        self.assertStatus('/root/alpha', ['unapproved'])

    def test_approved(self):
        # set publication time into the future, so should be approved
        dt = DateTime() + 1
        self.alpha.set_unapproved_version_publication_datetime(dt)
        self.alpha.approve_version()
        self.assertStatus('/root/alpha', ['approved'])

    def test_public(self):
        # set publication time into the past, so should go public right away
        dt = DateTime() - 1
        self.alpha.set_unapproved_version_publication_datetime(dt)
        self.alpha.approve_version()
        self.assertStatus('/root/alpha', ['public'])

    def test_closed(self):
        dt = DateTime() - 1
        self.alpha.set_unapproved_version_publication_datetime(dt)
        self.alpha.approve_version()
        self.alpha.close_version()
        self.assertPristineCatalog()

    def test_new(self):
        dt = DateTime() - 1
        self.alpha.set_unapproved_version_publication_datetime(dt)
        self.alpha.approve_version()
        self.alpha.create_copy()
        self.assertStatus('/root/alpha', ['unapproved', 'public'])
        
    def test_new_approved(self):
        dt = DateTime() - 1
        self.alpha.set_unapproved_version_publication_datetime(dt)
        self.alpha.approve_version()
        self.alpha.create_copy()
        self.alpha.set_unapproved_version_publication_datetime(dt)
        self.alpha.approve_version()
        self.assertStatus('/root/alpha', ['public'])

    def test_rename(self):
        self.silva.manage_renameObject('alpha', 'beta')
        self.assertStatus('/root/alpha', [])
        self.assertStatus('/root/beta', ['unapproved'])

    def test_copy(self):
        cb = self.silva.manage_copyObjects(['alpha'])
        self.silva.manage_pasteObjects(cb)
        self.assert_(hasattr(self.silva, 'copy_of_alpha'))
        self.assertStatus('/root/alpha', ['unapproved'])
        self.assertStatus('/root/copy_of_alpha', ['unapproved'])
        
    def test_cut(self):
        self.silva.manage_addProduct['Silva'].manage_addFolder('sub', 'Sub')
        cb = self.silva.manage_cutObjects(['alpha'])
        self.silva.sub.manage_pasteObjects(cb)
        self.assertStatus('/root/alpha', [])
        self.assertStatus('/root/sub/alpha', ['unapproved'])


class ContainerCatalogTestCase(CatalogTestCase):
    def test_folder1(self):
        self.assertNoPath('/root/sub')
        self.silva.manage_addProduct['Silva'].manage_addFolder('sub', 'Sub')
        self.assertPath('/root/sub')
        self.silva.manage_delObjects(['sub'])
        self.assertNoPath('/root/sub')
        
    def test_folder2(self):
        self.silva.manage_addProduct['Silva'].manage_addFolder('sub', 'Sub')
        self.silva.manage_delObjects(['sub'])
        self.assertNoPath('/root/sub')
        self.assertStatus('/root/sub/index', [])
        
    def test_folder3(self):
        # cut & paste
        self.silva.manage_addProduct['Silva'].manage_addFolder('sub', 'Sub')
        self.silva.manage_addProduct['Silva'].manage_addFolder('sub2', 'Sub')
        cb = self.silva.manage_cutObjects(['sub'])
        self.silva.sub2.manage_pasteObjects(cb)
        # XXX since index objects are not created at the moment,
        # this test will fail. Enable when index is created again
        #self.assertStatus('/root/sub2/sub/index', ['unapproved'])
        #self.assertStatus('/root/sub/index', [])

class AssetCatalogTestCase(CatalogTestCase):
    def test_asset1(self):
        self.silva.manage_addProduct['Silva'].manage_addImage('test', 'Test')
        self.assertPath('/root/test')
        self.silva.manage_renameObject('test', 'test2')
        self.assertNoPath('/root/test')
        self.assertPath('/root/test2')
        
if __name__ == '__main__':
    framework()
else:
    import unittest
    def test_suite():
        suite = unittest.TestSuite()
        suite.addTest(unittest.makeSuite(VersionCatalogTestCase))
        suite.addTest(unittest.makeSuite(ContainerCatalogTestCase))
        suite.addTest(unittest.makeSuite(AssetCatalogTestCase))
        return suite
