# Copyright (c) 2002 Infrae. All rights reserved.
# See also LICENSE.txt
# $Revision: 1.26 $
import os, sys
if __name__ == '__main__':
    execfile(os.path.join(sys.path[0], 'framework.py'))

import SilvaTestCase

from Products.Silva import SilvaPermissions

from Products.Silva.SilvaObject import SilvaObject
from DateTime import DateTime
from Products.SilvaDocument.Document import Document
from Products.ParsedXML.ParsedXML import ParsedXML
from Products.Silva.Ghost import Ghost, GhostVersion

# need to monkey patch preview and view
def preview(self, view_type='public'):
  
  return render_preview(self)

def view(self, view_type='public'):
    return render_view(self)

def render_preview(self):
    version = self.get_previewable()
    if version.REQUEST is None:
        print 'No request'
        print self.id
    if version is None:
        return '%s no view' % self.id
    if self.meta_type == 'Silva Ghost':
        result = version.render_preview()
        if result is None:
            return 'Ghost is broken'
        else:
            return result
    else:
        return "%s %s" % (self.id, version.id)
    
def render_view(self):
    version = self.get_viewable()
    if version is None:
        return '%s no view' % self.id
    if self.meta_type == 'Silva Ghost':
        result = version.render_view()
        if result is None:
            return 'Ghost is broken'
        else:
            return result
    else:
        return "%s %s" % (self.id, version.id)

# awful HACK

def _getCopyParsedXML(self, container):
    """A hack to make copy & paste work (used by create_copy())
    """
    return ParsedXML(self.id, self.index_html())

def _getCopyGhostVersion(self, container):
    return GhostVersion(self.id)

def _verifyObjectPaste(self, ob):
    return

class GhostTestCase(SilvaTestCase.SilvaTestCase):
    """Test the Ghost object.
    """
    def afterSetUp(self):
        # awful HACK to support manage_clone
        ParsedXML._getCopy = _getCopyParsedXML
        Document._verifyObjectPaste = _verifyObjectPaste
        GhostVersion._getCopy = _getCopyGhostVersion
        Ghost._verifyObjectPaste = _verifyObjectPaste
        
        # register silva document
        self.setPermissions([SilvaPermissions.ReadSilvaContent])
        self.doc1 = doc1 = self.add_document(self.root, 'doc1', 'Doc1')
        self.doc2 = doc2 = self.add_document(self.root, 'doc2', 'Doc2')
        self.doc3 = doc3 = self.add_document(self.root, 'doc3', 'Doc3')
        self.folder4 = folder4 = self.add_folder(self.root,
                  'folder4', 'Folder4')
        self.publication5 = publication5 = self.add_publication(self.root,
                  'publication5', 'Publication5')
        self.subdoc = subdoc = self.add_document(folder4,
                  'subdoc', 'Subdoc')
        self.subfolder = subfolder = self.add_folder(folder4,
                  'subfolder', 'Subfolder')
        self.subsubdoc = subsubdoc = self.add_document(subfolder,
                   'subsubdoc', 'Subsubdoc')
        self.subdoc2 = subdoc2 = self.add_document(publication5,
                   'subdoc2', 'Subdoc2')

    def test_ghost(self):
        self.root.manage_addProduct['Silva'].manage_addGhost('ghost1',
            '/root/doc1')
    
        # testing call cases of published (1) and non published (0)
        
        ghost = getattr(self.root, 'ghost1')
        # there is no version published at all there
        # ghost=0, doc=0
        self.assertEquals('This ghost is broken. (/root/doc1)',
            ghost.preview())
        self.assertEquals('Sorry, this document is not published yet.',
            ghost.view())

        # approve version of thing we point to
        self.doc1.set_unapproved_version_publication_datetime(DateTime() + 1)
        self.doc1.approve_version()

        # since there is still no published version, preview and view return
        # None
        # ghost=0, doc=0
        self.assertEquals('This ghost is broken. (/root/doc1)',
            ghost.preview())
        self.assertEquals('Sorry, this document is not published yet.',
            ghost.view())

        # this should publish doc1
        self.doc1.set_approved_version_publication_datetime(DateTime() - 1)
        # ghost=0, doc=1
        self.assertEquals(u'<h2 class="heading">Doc1</h2> \n\n',
            ghost.preview())
        self.assertEquals('Sorry, this document is not published yet.',
            ghost.view())

        # publish ghost version
        ghost.set_unapproved_version_publication_datetime(DateTime() - 1)
        ghost.approve_version()

        # ghost=1, doc=1
        self.assertEquals(u'<h2 class="heading">Doc1</h2> \n\n',
            ghost.preview())
        self.assertEquals(u'<h2 class="heading">Doc1</h2> \n\n',
            ghost.view())

            
        # make new version of doc1 ('1')
        #self.doc1.REQUEST = {}
        self.doc1.create_copy()
        self.doc1.set_title('Doc1 1')

        # shouldn't affect what we're ghosting
        self.assertEquals(u'<h2 class="heading">Doc1</h2> \n\n',
            ghost.preview())
        self.assertEquals(u'<h2 class="heading">Doc1</h2> \n\n',
            ghost.view())

        self.doc1.set_unapproved_version_publication_datetime(DateTime() - 1)
        self.doc1.approve_version()

        # now we're ghosting the version 1
        self.assertEquals(u'<h2 class="heading">Doc1 1</h2> \n\n',
            ghost.preview())
        self.assertEquals(u'<h2 class="heading">Doc1 1</h2> \n\n',
            ghost.view())

        # create new version of ghost
        ghost.create_copy()
        ghost.get_editable().set_content_url('/root/doc2')

        self.assertEquals(u'This ghost is broken. (/root/doc2)',
            ghost.preview())
        self.assertEquals(u'<h2 class="heading">Doc1 1</h2> \n\n',
            ghost.view())

        # publish doc2
        self.doc2.set_unapproved_version_publication_datetime(DateTime() - 1)
        self.doc2.approve_version()

        self.assertEquals(u'<h2 class="heading">Doc2</h2> \n\n',
            ghost.preview())
        self.assertEquals(u'<h2 class="heading">Doc1 1</h2> \n\n',
            ghost.view())


        # approve ghost again
        ghost.set_unapproved_version_publication_datetime(DateTime() - 1)
        ghost.approve_version()

        self.assertEquals(u'<h2 class="heading">Doc2</h2> \n\n',
            ghost.preview())
        self.assertEquals(u'<h2 class="heading">Doc2</h2> \n\n',
            ghost.view())

        # publish a ghost pointing to something that hasn't a published
        # version
        ghost.create_copy()
        ghost.get_editable().set_content_url('/root/doc3')
        ghost.set_unapproved_version_publication_datetime(DateTime() - 1)
        ghost.approve_version()
        self.assertEquals('This ghost is broken. (/root/doc3)',
            ghost.preview())
        self.assertEquals("This 'ghost' document is broken. Please inform the"
            " site administrator.", ghost.view())
        
    def test_broken_link1(self):
        # add a ghost
        self.root.manage_addProduct['Silva'].manage_addGhost('ghost1',
                                                              '/root/doc1/')
        ghost = getattr(self.root, 'ghost1')
        
        # issue 41: test if get_content_url works now
        self.assertEquals('/root/doc1', ghost.get_editable().get_content_url())
        self.assertEquals(None, ghost.get_editable().get_link_status())

        # now delete doc1
        self.root.action_delete(['doc1'])
        # ghost should say 'This ghost is broken'
        self.assertEquals('This ghost is broken. (/root/doc1)', ghost.preview())
        # issue 41: test get_content_url; should catch KeyError
        # and return original inserted url
        self.assertEquals('/root/doc1',
                          ghost.get_previewable().get_content_url())
        self.assertEqual(GhostVersion.LINK_VOID,
                         ghost.get_editable().get_link_status())
        
        # now make ghost point to doc2, and publish ghost and doc2
        self.doc2.set_unapproved_version_publication_datetime(DateTime() - 1)
        self.doc2.approve_version()
        ghost.create_copy()
        ghost.get_editable().set_content_url('/root/doc2')
        ghost.set_unapproved_version_publication_datetime(DateTime() - 1)
        ghost.approve_version()
        # now close & delete doc2
        self.doc2.close_version()
        self.root.action_delete(['doc2'])
        self.assertEquals("This 'ghost' document is broken. Please inform the site administrator.", ghost.view())
        # issue 41: test get_content_url; should catch KeyError
        # and return original inserted url
        self.assertEquals('/root/doc2',
                          ghost.get_previewable().get_content_url())
        self.assertEquals(GhostVersion.LINK_VOID,
                          ghost.get_previewable().get_link_status())


    def test_ghost_title(self):
        self.root.manage_addProduct['Silva'].manage_addGhost('ghost1',
                                                              '/root/doc1')
        # need to publish doc1 first
        self.root.doc1.set_unapproved_version_publication_datetime(DateTime() - 1)
        self.root.doc1.approve_version()
        ghost = getattr(self.root, 'ghost1')
        # FIXME: should we be able to get title of unpublished document?
        self.assertEquals('Doc1', ghost.get_title_editable())
        # now publish ghost
        ghost.set_unapproved_version_publication_datetime(DateTime() - 1)
        ghost.approve_version()
        # should have title of whatever we're pointing at now
        self.assertEquals('Doc1', ghost.get_title())
        # now break link
        self.root.doc1.close_version()
        self.root.action_delete(['doc1'])
        self.assertEquals('Ghost target is broken', ghost.get_title())

    # FIXME: ghost should do read access checks, test for it somehow?

    def test_ghost_points(self):
        # test that the ghost cannot point to the wrong thing;
        # only non-ghost versioned content
        self.root.manage_addProduct['Silva'].manage_addGhost('ghost1', '/root/does_not_exist')
        self.root.manage_addProduct['Silva'].manage_addImage('image6',
                                                              'Test image')
        ghost = getattr(self.root, 'ghost1')
        self.assertEquals('This ghost is broken. (/root/does_not_exist)', ghost.preview())
        self.assertEquals(GhostVersion.LINK_VOID,
                          ghost.get_editable().get_link_status())        
        ghost.get_editable().set_content_url('/root/folder4')
        self.assertEquals('This ghost is broken. (/root/folder4)', ghost.preview())
        self.assertEquals(GhostVersion.LINK_FOLDER,
                          ghost.get_editable().get_link_status())
        ghost.get_editable().set_content_url('/root/ghost1')
        self.assertEquals('This ghost is broken. (/root/ghost1)', ghost.preview())
        self.assertEquals(GhostVersion.LINK_GHOST,
                          ghost.get_editable().get_link_status())
        ghost.get_editable().set_content_url('/root/image6')
        self.assertEquals('This ghost is broken. (/root/image6)', ghost.preview())
        self.assertEquals(GhostVersion.LINK_NO_CONTENT,
  
  ghost.get_editable().get_link_status())

if __name__ == '__main__':
    framework()
else:
    # While framework.py provides its own test_suite()
    # method the testrunner utility does not.
    import unittest
    def test_suite():
        suite = unittest.TestSuite()
        suite.addTest(unittest.makeSuite(GhostTestCase))
        return suite
