# Copyright (c) 2003-2004 Infrae. All rights reserved.
# See also LICENSE.txt
# $Id: GhostFolder.py,v 1.32 2004/11/19 18:19:49 guido Exp $

from __future__ import nested_scopes

#zope
import OFS.Folder
from AccessControl import ClassSecurityInfo
from Globals import InitializeClass
from Products.PageTemplates.PageTemplateFile import PageTemplateFile
from DateTime import DateTime


# silva
from Products.Silva import Folder
from Products.Silva import SilvaPermissions
from Products.Silva.Ghost import GhostBase
from Products.Silva.helpers import add_and_edit
from Products.Silva import mangle
from Products.Silva.Publishable import Publishable
from Products.Silva.Versioning import VersioningError

from Products.Silva.interfaces import \
    IContainer, IContent, IAsset, IGhost, IPublishable, IVersionedContent, \
    IPublication, ISilvaObject, IGhostFolder, IIcon, IGhostContent
    
from Products.Silva.i18n import translate as _

icon = 'www/silvaghostfolder.gif'

class Sync:

    def __init__(self, gf, h_container, h_ob, g_container, g_ob):
        self.h_container = h_container
        self.h_ob = h_ob
        self.g_container = g_container
        self.g_ob = g_ob

        self.h_id = h_ob.getId()
        if g_ob is not None:
            self.g_id = g_ob.getId()

    def update(self):
        self._do_update()
        return self.g_container._getOb(self.h_id)

    def create(self):
        self._do_create()
        return self.g_container._getOb(self.h_id)

    def finish(self):
        pass

    def _do_update(self):
        raise NotImplementedError, _("implemented in subclasses")

    def _do_create(self):
        raise NotImplementedError, _("implemented in subclasses")

    def __repr__(self):
        return "<%s %s.%s -> %s.%s>" % (
            str(self.__class__).split('.')[-1],
            self.h_container.getId(), self.h_id,
            self.g_container.getId(), self.g_id)


class SyncContainer(Sync):

    def finish(self):
        ordered_ids = [ ob.getId()
            for ob in self.h_ob.get_ordered_publishables() ]
        for index, id in zip(range(len(ordered_ids)), ordered_ids):
            self.g_ob.move_to([id], index)

    def _do_create(self):
        self.g_container.manage_addProduct['Silva'].manage_addGhostFolder(
            self.h_id, self.h_ob.absolute_url())
        self.g_ob = self.g_container._getOb(self.h_id)
        self._do_update()

    def _do_update(self):
        pass
        

class SyncGhost(Sync):

    def _do_update(self):
        content_url = self._get_content_url()
        old_content_url = self.g_ob.get_haunted_url()
        if content_url == old_content_url:
            return
        self.g_ob.create_copy()
        version_id = self.g_ob.get_unapproved_version()
        version = getattr(self.g_ob, version_id)
        version.set_haunted_url(content_url)

    def _do_create(self):
        content_url = self._get_content_url()
        self.g_container.manage_addProduct['Silva'].manage_addGhost(
            self.h_id, content_url)

    def _get_content_url(self):
        return  self.h_ob.get_haunted_url()

    
class SyncContent(SyncGhost):

    def _get_content_url(self):
        return '/'.join(self.h_ob.getPhysicalPath())


class SyncCopy(Sync):
    # this is anything else -- copy it. We cannot check if it was 
    # modified and if copying is really necessary.

    def _do_update(self):
        assert self.g_ob is not None
        self.g_container.manage_delObjects([self.h_id])
        self.create()
    
    def _do_create(self):
        g_ob_new = self.h_ob._getCopy(self.g_container)
        self.g_container._setObject(self.h_id, g_ob_new)


class GhostFolder(GhostBase, Publishable, Folder.Folder):
    """Ghost Folders are similar to Ghosts, but instead of being a 
       placeholder for a document, they create placeholders and/or copies of all 
       the contents of the &#8216;original&#8217; folder. The advantage of Ghost 
       Folders is the contents stay in sync with the original, by manual or 
       automatic resyncing. Note that when a folder is
       ghosted, assets &#8211; such as Images and Files &#8211; are copied
       (physically duplicated) while documents are ghosted."""

    meta_type = 'Silva Ghost Folder'
    __implements__ = IContainer, IGhostFolder
    security = ClassSecurityInfo()

    _active_flag = 1

    # sync map... (haunted objects interface, ghost objects interface, 
    #   update/create class)
    # order is important, i.e. interfaces are checked in this order
    # I wonder if this needs to be pluggable, i.e. if third party components
    # may register special upgraders.
    _sync_map = [
        (IContainer, IContainer, SyncContainer),
        (IGhostContent, IGhostContent, SyncGhost),
        (IContent, IGhostContent, SyncContent),
        (None, None, SyncCopy),
    ]
        

    def __init__(self, id):
        GhostFolder.inheritedAttribute('__init__')(self, id)
        self._content_path = None

    security.declareProtected(
        SilvaPermissions.ChangeSilvaContent, 'haunt')
    def haunt(self):
        """populate the the ghost folder with ghosts
        """
        haunted = self.get_haunted_unrestricted()
        if haunted is None:
            return
        if self.get_link_status() != self.LINK_OK:
            return
        ghost = self
        assert IContainer.isImplementedBy(haunted)
        object_list = self._haunt_diff(haunted, ghost)
        upd = SyncContainer(self, None, haunted, None, self)
        updaters = [upd]
        
       
        while object_list:
            # breadth first search
            h_container, h_id, g_container, g_id = object_list[0]
            del(object_list[0])
            if h_id is None:
                # object was removed from haunted, so just remove it and 
                # continue
                g_container.manage_delObjects([g_id])
                continue
            h_ob = h_container._getOb(h_id)
            
            if g_id is None:
                # object was added to haunted
                g_ob = None
            else:
                # object is there but may have changed
                g_ob = g_container._getOb(g_id)
            g_ob_new = None
            
            for h_if, g_if, update_class in self._sync_map:
                if h_if and not h_if.isImplementedBy(h_ob):
                    continue
                if g_ob is None:
                    # matching haunted interface, no ghost -> create
                    uc = update_class(self, h_container, h_ob,
                        g_container, g_ob)
                    updaters.append(uc)
                    g_ob_new = uc.create()
                    break
                if g_if and not g_if.isImplementedBy(g_ob):
                    # haunted interface machces but ghost interface doesn't
                    continue
                # haunted interface and ghost interface match -> update
                uc = update_class(self, h_container, h_ob, g_container,
                    g_ob)
                updaters.append(uc)
                g_ob_new = uc.update()
                break
            
            msg = _("no updater was called for ${info_tuple}") 
            msg.set_mapping({'info_tuple': 
                repr(((self, h_container, h_ob, g_container, g_ob), ))})
            assert g_ob_new is not None, msg
            if IContainer.isImplementedBy(h_ob):
                object_list.extend(self._haunt_diff(h_ob, g_ob_new))
        for updater in updaters:
            updater.finish()
        
        self._publish_ghosts()
        self._invalidate_sidebar(self)

    def _haunt_diff(self, haunted, ghost):
        """diffes two containers

            haunted: IContainer, container to be haunted
            ghost: IContainer, ghost
        
            returns list of tuple:
            [(haunted, h_id, ghost, g_id)]
            whereby 
                h_id is the haunted object's id or None if a ghost exists but
                    no object to be haunted
                g_id is the ghost's id or None if the ghost doesn't exist but
                    has to be created
                haunted and ghost are the objects passed in
        """
        assert IContainer.isImplementedBy(haunted)
        assert IContainer.isImplementedBy(ghost)
        h_ids = list(haunted.objectIds())
        g_ids = list(ghost.objectIds())
        h_ids.sort()
        g_ids.sort()
        ids = []
        while h_ids or g_ids:
            h_id = None
            g_id = None
            if h_ids:
                h_id = h_ids[0]
            if g_ids:
                g_id = g_ids[0]
            if h_id == g_id or h_id is None or g_id is None:
                ids.append((h_id, g_id))
                if h_ids:
                    del h_ids[0]
                if g_ids:
                    del g_ids[0]
            elif h_id < g_id:
                ids.append((h_id, None))
                del h_ids[0]
            elif h_id > g_id:
                ids.append((None, g_id))
                del g_ids[0]
        objects = [ (haunted,h_id, ghost, g_id)
            for (h_id, g_id) in ids ]
        return objects

    security.declareProtected(SilvaPermissions.View,'get_link_status')
    def get_link_status(self, content=None):
        """return an error code if this version of the ghost is broken.
        returning None means the ghost is Ok.
        """
        if content is None:
            content = self.get_haunted_unrestricted(check=0)
        if self._content_path is None:
            return self.LINK_EMPTY
        if content is None:
            return self.LINK_VOID
        if IGhost.isImplementedBy(content):
            return self.LINK_GHOST
        if IContent.isImplementedBy(content):
            return self.LINK_CONTENT
        if not IContainer.isImplementedBy(content):
            return self.LINK_NO_FOLDER
        if self.isReferencingSelf(content):
            return self.LINK_CIRC
        return self.LINK_OK
               
    def isReferencingSelf(self, content=None):
        """returns True if ghost folder references self or a ancestor of self
        """
        if content is None:
            content = self.get_haunted_unrestricted(check=0)
        if content is None:
            # if we're not referncing anything it is not a circ ref for sure
            return 0
        content_path = content.getPhysicalPath()
        chain = self.aq_chain[:]
        app = self.getPhysicalRoot()
        while chain:
            ancestor = chain[0]
            del(chain[0])
            if ancestor is app:
                # anything farther up the tree is not `referencable'. 
                chain = []
            if ancestor.getPhysicalPath() == content_path:
                return 1
        return 0

    security.declareProtected(
        SilvaPermissions.ChangeSilvaContent, 'to_publication')
    def to_publication(self):
        """replace self with a folder"""
        new_self = self._to_folder_or_publication_helper(to_folder=0)
        self._copy_annotations_from_haunted(new_self)
        
    security.declareProtected(
        SilvaPermissions.ChangeSilvaContent, 'to_folder')
    def to_folder(self):
        """replace self with a folder"""
        new_self = self._to_folder_or_publication_helper(to_folder=1)
        self._copy_annotations_from_haunted(new_self)

    def _copy_annotations_from_haunted(self, new_self):
        marker = []
        a_attr = '_portal_annotations_'
        annotations = getattr(self.get_haunted_unrestricted().aq_base, a_attr,
            marker)
        if annotations is marker:
            return
        setattr(new_self, a_attr, annotations)

    security.declareProtected(
        SilvaPermissions.ReadSilvaContent, 'to_xml')
    def to_xml(self, context):
        f = context.f
        f.write("<silva_ghostfolder id='%s' content_url='%s'>" % (
            self.getId(), self.get_haunted_url()))
        self._to_xml_helper(context)
        f.write("</silva_ghostfolder>")
    
    
    # all this is for a nice side bar
    def is_transparent(self):
        """show in subtree? depends on haunted object"""
        content = self.get_haunted_unrestricted()
        if IContainer.isImplementedBy(content):
            return content.is_transparent()
        return 0
    
    def get_publication(self):
        """returns self if haunted object is a publication"""
        content = self.get_haunted_unrestricted()
        if IPublication.isImplementedBy(content):
            return self.aq_inner
        return self.aq_inner.aq_parent.get_publication()

    def implements_publication(self):
        content = self.get_haunted_unrestricted()
        if ISilvaObject.isImplementedBy(content):
            return content.implements_publication()
        return 0

    def is_deletable(self):
        return 1

    def _publish_ghosts(self):
        activate_list = self.objectValues()
        # ativate all containing objects, depth first
        while activate_list:
            object = activate_list.pop()
            if IContainer.isImplementedBy(object):
                activate_list += object.objectValues()
            if IVersionedContent.isImplementedBy(object):
                if object.is_published():
                    continue
                if not object.get_unapproved_version():
                    object.create_copy()
                object.set_unapproved_version_publication_datetime(
                    DateTime())
                object.approve_version()
                    
    def _factory(self, container, id, content_url):
        return container.manage_addProduct['Silva'].manage_addGhostFolder(id,
            content_url)
       
InitializeClass(GhostFolder)

    
manage_addGhostFolderForm = PageTemplateFile("www/ghostFolderAdd", globals(),
    __name__='manage_addGhostFolderForm')


def manage_addGhostFolder(dispatcher, id, content_url, REQUEST=None):
    """Add a GhostFolder"""
    if not mangle.Id(dispatcher, id).isValid():
        return
    gf = GhostFolder(id)
    dispatcher._setObject(id, gf)
    gf = getattr(dispatcher, id)
    gf.set_haunted_url(content_url)
    add_and_edit(dispatcher, id, REQUEST)
    return ''

def xml_import_handler(object, node):

    def _get_content_url(node):
        content_url = node.attributes.getNamedItem('content_url').nodeValue
        msg = _("got ${url}, expected a unicode")
        msg.set_mapping({'url': content_url})
        assert type(content_url) == type(u''), msg
        return content_url.encode('us-ascii', 'ignore')
    
    def factory(object, id, title, content_url):
        object.manage_addProduct['Silva'].manage_addGhostFolder(id,
            content_url)
    
    content_url = _get_content_url(node)
    f = lambda object, id, title, content_url=content_url: \
        factory(object, id, title, content_url)
    ghostfolder = Folder.xml_import_handler(object, node, factory=f)
    return ghostfolder
