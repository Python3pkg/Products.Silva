# Copyright (c) 2002-2004 Infrae. All rights reserved.
# See also LICENSE.txt
# $Revision: 1.150.6.6.16.2 $

# Zope
from OFS import Folder, SimpleItem
from AccessControl import ClassSecurityInfo, getSecurityManager
from Products.PageTemplates.PageTemplateFile import PageTemplateFile
from Globals import InitializeClass
from OFS.CopySupport import _cb_decode # HACK
from Products.ZCatalog.CatalogPathAwareness import CatalogPathAware
# Silva
from Products.Silva.Ghost import ghostFactory, canBeHaunted
from Products.Silva.ExtensionRegistry import extensionRegistry
from SilvaObject import SilvaObject
from Publishable import Publishable
import Copying
import SilvaPermissions
import ContainerPolicy
import validate
# misc
import helpers
import re
import urllib
from sys import exc_info

from Products.Silva.ImporterRegistry import get_importer, xml_import_helper
from Products.Silva.ImporterRegistry import get_xml_id, get_xml_title
from Products.Silva.ImportArchive import import_archive_helper
from Products.Silva.Metadata import export_metadata
from Products.Silva import mangle
from Products.ParsedXML.ParsedXML import ParsedXML
from Products.ParsedXML.ParsedXML import createDOMDocument
from Products.ParsedXML.ExtraDOM import writeStream

from interfaces import IPublishable, IContent, IGhost
from interfaces import IVersionedContent, ISilvaObject, IAsset
from interfaces import IContainer, IPublication, IRoot

icon="www/silvafolder.gif"
addable_priority = -.5

class Folder(CatalogPathAware, SilvaObject, Publishable, Folder.Folder):
    """The presentation of the information within a
       publication is structured with folders. They determine the visual
       hierarchy that a Visitor sees. Folders on the top level
       define sections of a publication, subfolders define chapters, etc.
       Note that unlike publications, folders are transparent, meaning you
       can see through them in the sidebar tree navigation and the Publish 
       screen.
    """
    security = ClassSecurityInfo()

    meta_type = "Silva Folder"

    default_catalog = 'service_catalog'

    object_type = 'container'

    # A hackish way to get a Silva tab in between the standard ZMI tabs
    inherited_manage_options = Folder.Folder.manage_options
    manage_options=(
        (inherited_manage_options[0], ) +
        ({'label':'Silva /edit...', 'action':'edit'}, ) +
        inherited_manage_options[1:]
        )

    __implements__ = IContainer
        
    def __init__(self, id):
        Folder.inheritedAttribute('__init__')(
            self, id, "[Containers have no titles, this is a bug]")
        self._ordered_ids = []

    def manage_afterAdd(self, item, container):
        # call after add code on SilvaObject
        self._afterAdd_helper(item, container)
        self._set_creation_datetime()
        # call code on CatalogAware
        Folder.inheritedAttribute('manage_afterAdd')(self, item, container)
        # container added, always invalidate sidebar
        self._invalidate_sidebar(item)
        # Walk recursively through self to find and
        # (if published) close versioned content items
        # this is probably only used when importing a zexp
        self._update_contained_documents_status()

    def manage_beforeDelete(self, item, container):
        # call before delete code on SilvaObject
        self._beforeDelete_helper(item, container)
        # call code on CatalogAware
        Folder.inheritedAttribute('manage_beforeDelete')(self, item, container)
        # container removed, always invalidate sidebar
        self._invalidate_sidebar(item)

    def manage_afterClone(self, item):
        Folder.inheritedAttribute('manage_afterClone')(self, item)
        # XXX is this really necessary?
        self._invalidate_sidebar(item)

    def _invalidate_sidebar(self, item):
        # invalidating sidebar also takes place for folder when index gets
        # changed
        if item.id == 'index':
            item = item.get_container()
        if not IContainer.isImplementedBy(item):
            return
        service_sidebar = self.aq_inner.service_sidebar
        service_sidebar.invalidate(item)
        if (IPublication.isImplementedBy(item) and 
                not IRoot.isImplementedBy(item)):
            service_sidebar.invalidate(item.aq_inner.aq_parent)

    def _update_contained_documents_status(self):
        """Closes all objects that implement VersionedContent (if public) 
        and recurses into subcontainers"""
        for obj in self.objectValues():
            if IVersionedContent.isImplementedBy(obj):
                if obj.is_version_published():
                    obj.close_version()
                    obj.create_copy()
                if obj.is_version_approved():
                    obj.unapprove_version()
            elif IContainer.isImplementedBy(obj):
                obj._update_contained_documents_status()
    
    # MANIPULATORS

    security.declarePrivate('titleMutationTrigger')
    def titleMutationTrigger(self):
        """This trigger is called upon save of Silva Metadata. More
        specifically, when the silva-content - defining titles - set is 
        being editted for this object.
        """
        self._invalidate_sidebar(self)
        
    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                              'move_object_up')
    def move_object_up(self, id):
        """Move object up. Returns true if move succeeded.
        """
        ids = self._ordered_ids
        try:
            i = ids.index(id)
        except ValueError:
            return 0
        if i == 0:
            return 0
        self._invalidate_sidebar(getattr(self, id))
        ids[i], ids[i - 1] = ids[i - 1], ids[i]
        self._ordered_ids = ids
        return 1

    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                              'move_object_down')
    def move_object_down(self, id):
        """move object down.
        """
        ids = self._ordered_ids
        try:
            i = ids.index(id)
        except ValueError:
            return 0
        if i == len(ids) - 1:
            return 0
        self._invalidate_sidebar(getattr(self, id))
        ids[i], ids[i + 1] = ids[i + 1], ids[i]
        self._ordered_ids = ids
        return 1

    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                              'move_to')
    def move_to(self, move_ids, index):
        ids = self._ordered_ids
        # check whether all move_ids are known
        for move_id in move_ids:
            if move_id not in ids:
                return 0
        for id in move_ids:
            if ids.index(id) < index:
                index += 1
                break
        ids_without_moving_ids = []
        move_ids_in_order = []
        for id in ids:
            if id in move_ids:
                move_ids_in_order.append(id)
                ids_without_moving_ids.append(None)
            else:
                ids_without_moving_ids.append(id)
        ids = ids_without_moving_ids
        move_ids = move_ids_in_order
        move_ids.reverse()
        for move_id in move_ids:
            self._invalidate_sidebar(getattr(self, move_id))
            ids.insert(index, move_id)
        ids = [id for id in ids if id is not None]
        self._ordered_ids = ids
        return 1

    def _refresh_ordered_ids(self, item, insert_at=None):
        """Make sure item is in ordered_ids when it should be after
        active status changed.
        """
        if not IPublishable.isImplementedBy(item):
            return
        if IContent.isImplementedBy(item) and item.is_default():
            return
        ids = self._ordered_ids
        id = item.id
        if item.is_active() and id not in ids:
            if insert_at:
                ids.insert(insert_at, id)
            else:
                ids.append(id)
            self._p_changed = 1
        elif not item.is_active() and id in ids:
            ids.remove(id)
            self._p_changed = 1

    def _add_ordered_id(self, item):
        """Add item to the end of the list of ordered ids.
        """
        # this already happens to do what we want
        # this works in case of active objects that were added
        # (they're added to the list of ordered ids)
        # and also for inactive objects
        # (they're not added to the list; nothing happens)
        self._refresh_ordered_ids(item)
        
    def _remove_ordered_id(self, item):
        if not IPublishable.isImplementedBy(item):
            return
        if IContent.isImplementedBy(item) and item.is_default():
            return
        ids = self._ordered_ids
        if item.is_active() and item.id in ids:
            ids.remove(item.id)
            self._ordered_ids = ids

    security.declareProtected(SilvaPermissions.ApproveSilvaContent, 
                              'refresh_active_publishables')
    def refresh_active_publishables(self):
        """Clean up all ordered ids in this container and all subcontainers.
        This method normally does not need to be called, but if something is
        wrong, this can be called in emergency situations. WARNING: all
        ordering information is lost!
        """
        ids = []
        for object in self.objectValues():
            if not IPublishable.isImplementedBy(object):
                continue
            if IContent.isImplementedBy(object) and object.is_default():
                continue
            if object.is_active():
                ids.append(object.id)
            if IContainer.isImplementedBy(object):
                object.refresh_active_publishables()
        self._ordered_ids = ids

    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                              'action_rename')
    def action_rename(self, orig_id, new_id):
        """Change id of object with id orig_id.
        """
        # check if new_id is valid
        if not mangle.Id(self, new_id, 
                instance=getattr(self, orig_id)).isValid():
            return
        # check if renaming (which in essence is the deletion of a url)
        # is allowed
        if not self.is_delete_allowed(orig_id):
            return
        # only change id if necessary
        if orig_id == new_id:
            return
        oids = self._ordered_ids
        try:
            publishable_id = oids.index(orig_id)
        except ValueError:
            # this is not a clean fix but it should work; items like
            # assets can be renamed but are not in the ordered_ids.
            # therefore trying to move them doesn't work, and just ignore
            # that.
            publishable_id = None
        self.manage_renameObject(orig_id, new_id)
        if publishable_id is not None:
            self.move_to([new_id], publishable_id)
        return 1

    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                              'action_delete')
    def action_delete(self, ids):
        """Delete objects.
        """
        # check whether deletion is allowed
        deletable_ids = [id for id in ids if self.is_delete_allowed(id)]
        self.manage_delObjects(deletable_ids)

    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                              'action_cut')
    def action_cut(self, ids, REQUEST):
        """Cut objects.
        """
        # check whether deletion is allowed
        deletable_ids = [id for id in ids if self.is_delete_allowed(id)]
        # FIXME: need to do unit tests for this
        # FIXME: would this lead to a sensible user interface?
        if len(deletable_ids) > 0:
          self.manage_cutObjects(deletable_ids, REQUEST)
        
    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'action_copy')
    def action_copy(self, ids, REQUEST):
        """Copy objects.
        """
        self.manage_copyObjects(ids, REQUEST)
        
    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                              'action_paste')
    def action_paste(self, REQUEST):
        """Paste objects on clipboard.
        """
        # HACK
        # determine if we're cut-paste or copy-pasting, wish we
        # didn't have to..
        if not REQUEST.has_key('__cp'):
            return
        op, ref = _cb_decode(REQUEST['__cp'])

        # copy-paste operation
        # items on clipboard should be unapproved & closed, but
        # only the *copies*
        # (actually in case of a cut-paste the original
        # should not be approved, too)
        messages = []
        ids = []
        for item in self.cb_dataItems():
            if ((op == 0 or item.get_container().is_delete_allowed(item.id)) 
                    and item.meta_type in [addable['name'] for 
                        addable in self.get_silva_addables()]):
                ids.append(item.id)
            elif item.meta_type not in [addable['name'] for 
                    addable in self.get_silva_addables()]:
                messages.append('pasting &#xab;%s&#xbb; is not allowed in '\
                                'this type of container' % item.id)

        if len(ids) == 0:
            return ', '.join(messages).capitalize()
        
        if op == 0:
            # also update title of index documents
            copy_ids = ids
            # modify ids to copy_to if necessary
            paste_ids = []
            ids = self.objectIds()
            for copy_id in copy_ids:
                # keep renaming until we have a unique id (like Zope does, 
                # so copy_of_x and copy2_of_x)
                i = 0
                org_copy_id = copy_id
                while copy_id in ids:
                    i += 1
                    add = ''
                    if i > 1:
                        add = str(i)
                    copy_id = 'copy%s_of_%s' % (add, org_copy_id)
                paste_ids.append(copy_id)
        else:
            # cut-paste operation
            cut_ids = ids
            # check where we're cutting from
            cut_container = item.aq_parent.get_container()
            # if not cutting to the same folder as we came from
            if self != cut_container:
                # modify ids to copy_to if necessary
                paste_ids = []
                ids = self.objectIds()
                for cut_id in cut_ids:
                    # keep renaming until we have a unique id (like Zope 
                    # does, so copy_of_x and copy2_of_x)
                    i = 0
                    org_cut_id = cut_id
                    while cut_id in ids:
                        i += 1
                        add = ''
                        if i > 1:
                            add = str(i)
                        cut_id = 'copy%s_of_%s' % (add, cut_id)
                    paste_ids.append(cut_id)
            else:
                # no changes to cut_ids
                paste_ids = cut_ids
        # now we do the paste
        self.manage_pasteObjects(REQUEST=REQUEST)
        # now unapprove & close everything just pasted
        for paste_id in paste_ids:
            object = getattr(self, paste_id)
            helpers.unapprove_close_helper(object)
            object.sec_update_last_author_info()
            messages.append('pasted &#xab;%s&#xbb;' % paste_id)
        
        return ', '.join(messages).capitalize()
            
    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                              'action_paste')
    def action_paste_to_ghost(self, REQUEST):
        """Paste what is on clipboard to ghost.
        """
        # create ghosts for each item on clipboard
        allowed_meta_types = [addable['name'] for 
            addable in self.get_silva_addables()]
        messages = []
        for item in self.cb_dataItems():
            if item.meta_type in allowed_meta_types:
                ids = self.objectIds()
                paste_id = item.id
                # keep renaming them until they have a unique id, the Zope way
                i = 0
                org_paste_id = paste_id
                while paste_id in ids:
                    i += 1
                    add = ''
                    if i > 1:
                        add = str(i)
                    if canBeHaunted(item):
                        paste_id = 'ghost%s_of_%s' % (add, org_paste_id)
                    else:
                        paste_id = 'copy%s_of_%s' % (add, org_paste_id)
                self._ghost_paste(paste_id, item, REQUEST)
                messages.append('pasted &#xab;%s&#xbb;' % paste_id)
            else:
                messages.append('pasting &#xab;%s&#xbb; is not allowed in '\
                                'this type of container' % item.id)
        return ', '.join(messages).capitalize()

    def _ghost_paste(self, paste_id, item, REQUEST):
        if canBeHaunted(item):
            ghost = ghostFactory(self, paste_id, item)
            if ghost.meta_type == 'Silva Ghost Folder':
                ghost.haunt()
        elif IGhost.isImplementedBy(item):
            content_url = item.get_haunted_url()
            item._factory(self, paste_id, content_url)
        else:
            # this is an object that just needs to be copied
            item = item._getCopy(self)
            item._setId(paste_id)
            self._setObject(paste_id, item)

    security.declareProtected(SilvaPermissions.ApproveSilvaContent,
                              'to_publication')
    def to_publication(self):
        """Turn this folder into a publication.
        """
        self._to_folder_or_publication_helper(to_folder=0)

    def _to_folder_or_publication_helper(self, to_folder):
        container = self.aq_parent
        container_ordered_ids = container._ordered_ids[:]
        orig_id = self.id
        convert_id = 'convert__%s' % orig_id
        if to_folder:
            container.manage_addProduct['Silva'].manage_addFolder(
                convert_id, self.get_title(), create_default=0)
        else:
            # to publication
            container.manage_addProduct['Silva'].manage_addPublication(
                convert_id, self.get_title(), create_default=0)
        ## assure the folder/pub has a _p_jar
        get_transaction().commit(1)
        folder = getattr(container, convert_id)
        # copy all contents into new folder
        cb = self.manage_copyObjects(self.objectIds())
        folder.manage_pasteObjects(cb)
        folder._ordered_ids = self._ordered_ids
        # copy over all properties
        for id, value in self.propertyItems():
            type = self.getPropertyType(id)
            if folder.hasProperty(id):
                folder.manage_delProperties([id])
            # if we still have property it must be required, change it
            if folder.hasProperty(id):
                folder.manage_changeProperties(id=value)
            else:
                # add it
                folder.manage_addProperty(id, value, type)
        # copy over annotations
        # XXX hack as relying on ANNOTATION_MARKER, but okay
        if hasattr(self.aq_base, '_portal_annotations_'):
            folder._portal_annotations_ = self._portal_annotations_
        # copy over authorization info
        folder.__ac_local_roles__ = self.__ac_local_roles__
        folder.__ac_local_groups__ = self.__ac_local_groups__
        # also over copy over View permission information
        acquire = self.acquiredRolesAreUsedBy('View') == 'CHECKED'
        roles = []
        for info in self.rolesOfPermission('View'):
            role = info['name']
            selected = info['selected'] == 'SELECTED'
            if selected:
                roles.append(role)
        if acquire:
            folder.manage_permission('View', [], acquire)
        else:
            folder.manage_permission('View', roles, acquire)
        
        # now remove this object from the container
        container.manage_delObjects([self.id])
        # and rename the copy
        container.manage_renameObject(convert_id, orig_id)
        # now restore ordered ids of container to original state
        container._ordered_ids = container_ordered_ids
        return folder
        
    # ACCESSORS
    
    security.declareProtected(
        SilvaPermissions.ChangeSilvaContent, 'can_set_title')    
    def can_set_title(self):
        """Check to see if the title can be set by user, meaning:
        * he is Editor/ChiefEditor/Manager, or
        * he is Author _and_ the Folder does not contain published content
          or approved content recursively (self.is_published()).
        """
        user = getSecurityManager().getUser()
        if user.has_permission(SilvaPermissions.ApproveSilvaContent, self):
            return 1
        
        return not self.is_published() and not self.is_approved()

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'get_silva_addables')
    def get_silva_addables(self):
        """Get a list of addable Silva objects.
        """
        result = []
        allowed = self.get_silva_addables_allowed()
        for addable_dict in extensionRegistry.get_addables():
            meta_type = addable_dict['name']
            if allowed and meta_type not in allowed:
                continue
            if (self._is_silva_addable(addable_dict) and
                addable_dict['instance']._is_allowed_in_publication):
                # add the docstring to the dict so it is available 
                # in pythonscripts
                addable_dict['doc'] = addable_dict['instance'].__doc__
                result.append(addable_dict)
        return result

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'get_silva_addables_all')
    def get_silva_addables_all(self):
        result = [addable_dict['name']
                  for addable_dict in extensionRegistry.get_addables()
                  if self._is_silva_addable(addable_dict)]
        return result

    def _is_silva_addable(self, addable_dict):
        """Given a dictionary from filtered_meta_types, check whether this
        specifies a silva addable.
        """
        return (
            addable_dict.has_key('instance') and
            ISilvaObject.isImplementedByInstancesOf(
            addable_dict['instance']) and
            not self.get_root().is_silva_addable_forbidden(
            addable_dict['name']) and
            self.service_view_registry.has_view('add', addable_dict['name'])
            )

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'get_silva_addables_allowed')
    def get_silva_addables_allowed(self):
        secman = getSecurityManager()
        addables = self.get_silva_addables_allowed_in_publication()
        allowed = [name for name in addables if secman.checkPermission('Add %ss' % name, self)]
        return allowed

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'get_container')
    def get_container(self):
        """Get the container an object is in. Can be used with
        acquisition to get the 'nearest' container.
        FIXME: currently the container of a container is itself. Is this the 
        right behavior? It leads to subtle bugs..
        """
        return self.aq_inner

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'get_real_container')
    def get_real_container(self):
        """Get the container, even if we're a container.

        If we're the root object, returns None.
        
        Can be used with acquisition to get the 'nearest' container.
        """
        container = self.get_container()
        if container is self:
            return container.aq_parent.get_container()
        return container
    
    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'container_url')
    def container_url(self):
        """Get url for container.
        """
        return self.absolute_url()

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'is_transparent')
    def is_transparent(self):
        return 1

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'is_published')
    def is_published(self):
        # NOTE: this is inefficient if there's a big unpublished hierarchy..
        # Folder is published if anything inside is published
        default = self.get_default()
        if default and default.aq_explicit.is_published():
            return 1
        for object in self.get_ordered_publishables():        
            if object.is_published():
                return 1
        return 0

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'is_approved')
    def is_approved(self):
        # Folder is approved if anything inside is approved
        default = self.get_default()
        if default and self.get_default().is_approved():
            return 1
        for object in self.get_ordered_publishables():        
            if object.is_approved():
                return 1
        return 0

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'is_delete_allowed')
    def is_delete_allowed(self, id):
        """Delete is only allowed if the object with id:
           - does not have an approved version
           - does not have a published version
           - if it is a container, does not contain anything of the
             above, recursively
        """
        object = getattr(self, id)
        return object.is_deletable()

    def is_deletable(self):
        """deletable if all containing objects are deletable

            NOTE: this will be horribly slow for large trees
        """
        for object in self.get_ordered_publishables():
            if not object.is_deletable():
                return 0
        return 1
        

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'get_default')
    def get_default(self):
        """Get the default content object of the folder.
        """
        if not hasattr(self.aq_base, 'index'):
            return None
        else:
            return getattr(self, 'index')

    security.declareProtected(
        SilvaPermissions.AccessContentsInformation, 'get_default_viewable')
    def get_default_viewable(self):
        """Get the viewable version of the default content object
        of this container.
        """
        # Returns None if there's no default, or the default has no
        # viewable version.
        default = self.get_default()
        if default is None:
            return None
        return default.get_viewable()
    
    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'get_modification_datetime')
    def get_modification_datetime(self, update_status=1):
        """Folders don't really have a modification datetime.
        """
        return None
    
    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'get_ordered_publishables')
    def get_ordered_publishables(self):
        return map(self._getOb, self._ordered_ids)

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'get_nonactive_publishables')
    def get_nonactive_publishables(self):
        result = []
        for object in self.objectValues():
            if (IPublishable.isImplementedBy(object) and
                not object.is_active()):
                result.append(object)
        result.sort(lambda x, y: cmp(x.getId(), y.getId()))
        return result

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'get_silva_asset_types')
    def get_silva_asset_types(self):
        result = [addable_dict['name']
                  for addable_dict in extensionRegistry.get_addables()
                    if IAsset.isImplementedByInstancesOf(addable_dict['instance'])]
        return result

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'get_assets')
    def get_assets(self):
        result = []
        for object in self.objectValues(self.get_silva_asset_types()):
            result.append(object)
        result.sort(lambda x,y: cmp(x.getId(), y.getId()))
        return result

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'get_assets_of_type')
    def get_assets_of_type(self, meta_type):
        result = []
        assets = self.get_assets()
        for object in assets:
            if object.meta_type == meta_type:
                result.append(object)
        return result

    # FIXME: what if the objects returned are not accessible with my
    # permissions? unlikely as my role is acquired?
    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'get_tree')
    def get_tree(self, depth=-1):
        """Get flattened tree of contents.
        The 'depth' argument limits the number of levels, defaults to unlimited
        """
        l = []
        self._get_tree_helper(l, 0, depth)
        return l

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'get_container_tree')
    def get_container_tree(self, depth=-1):
        l = []
        self._get_container_tree_helper(l, 0, depth)
        return l

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'get_public_tree')
    def get_public_tree(self, depth=-1):
        l = []
        self._get_public_tree_helper(l, 0, depth)
        return l

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'get_status_tree')
    def get_status_tree(self, depth=-1):
        '''get Silva tree'''
        l = []
        self._get_status_tree_helper(l, 0, depth)
        return l

    def _get_tree_helper(self, l, indent, depth):
        for item in self.get_ordered_publishables():
            if item.getId() == 'index':
                # default document should not be inserted
                continue
            if (IContainer.isImplementedBy(item) and
                item.is_transparent()):
                l.append((indent, item))
                if depth == -1 or indent < depth:
                    item._get_tree_helper(l, indent + 1, depth)
            else:
                l.append((indent, item))

    def _get_container_tree_helper(self, l, indent, depth):
        for item in self.get_ordered_publishables():
            if not IContainer.isImplementedBy(item):
                continue
            if item.is_transparent():
                l.append((indent, item))
                if depth == -1 or indent < depth:
                    item._get_container_tree_helper(l, indent + 1, depth)
            else:
                l.append((indent, item))

    def _get_public_tree_helper(self, l, indent, depth):
        for item in self.get_ordered_publishables():
            if not item.is_published():
                continue
            if (IContainer.isImplementedBy(item) and
                item.is_transparent()):
                l.append((indent, item))
                if depth == -1 or indent < depth:
                    item._get_public_tree_helper(l, indent + 1, depth)
            else:
                l.append((indent, item))

    def _get_status_tree_helper(self, l, indent, depth):
        if IContainer.isImplementedBy(self):
            default = self.get_default()
            if default is not None:
                l.append((indent, default))

        for item in self.get_ordered_publishables():
            l.append((indent, item))
            if not IContainer.isImplementedBy(item):
                continue
            if (depth == -1 or indent < depth) and item.is_transparent():
                item._get_status_tree_helper(l, indent+1, depth)

    def create_ref(self, obj):
        """Create a moniker for the object.
        """
        return Copying.create_ref(obj)

    def resolve_ref(self, ref):
        """Resolve reference to object.
        """
        return Copying.resolve_ref(self.getPhysicalRoot(), ref)

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'to_xml')
    def to_xml(self, context):
        """Render object to XML.
        """
        f = context.f
        f.write('<silva_folder id="%s">' % self.id)
        self._to_xml_helper(context)
        export_metadata(self, context)
        f.write('</silva_folder>')

    def _to_xml_helper(self, context):
        if context.last_version:
            title = self.get_title_editable()
        else:
            title = self.get_title()
            
        context.f.write('<title>%s</title>' % helpers.translateCdata(title))
        default = self.get_default()
        if default is not None:
            default.to_xml(context)
        for object in self.get_ordered_publishables():
            if (IPublication.isImplementedBy(object) and 
                    not context.with_sub_publications):
                continue
            object.to_xml(context)
        #for object in self.get_assets():
        #    pass

    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                              'xml_validate')
    def xml_validate(self, xml):
        """Return true if XML is valid.
        """
        return validate.validate(xml)
    
    security.declareProtected(SilvaPermissions.ChangeSilvaContent, 
        'xml_import')
    def xml_import(self, xml):
        """Import XML"""
        dom = createDOMDocument(xml)
        import_root = dom.documentElement
        if import_root.nodeName == u'silva':
            import_root = import_root.firstChild
        while import_root:
            # since some exceptions raised are strings or so, we're going to
            # convert them to 'Exception' here
            try:
                xml_import_helper(self, import_root)
            except Exception:
                raise
            except:
                obj, info, tb = exc_info()
                raise Exception, info, tb
            import_root = import_root.nextSibling

    security.declareProtected(
        SilvaPermissions.ChangeSilvaContent, 'archive_file_import')
    def archive_file_import(self, file, title='', recreate_dirs=1):
        """Import archive file (currently zip format) and
        create Assets from its contents. Use given title for 
        all assets created
        """
        return import_archive_helper(self, file, title, recreate_dirs)

    security.declarePublic('url_encode')
    def url_encode(self, string):
        """A wrapper for the urllib.quote function
        
        to be used in Python scripts and PT's
        """
        return urllib.quote(string)
                
InitializeClass(Folder)

manage_addFolderForm = PageTemplateFile("www/folderAdd", globals(),
                                        __name__='manage_addFolderForm')

def manage_addFolder(
    context, id, title, create_default=1, policy_name='None', REQUEST=None):
    """Add a Folder."""

    if not mangle.Id(context, id).isValid():
        return
    folder = Folder(id)
    context._setObject(id, folder)
    folder = getattr(context, id)
    folder.set_title(title)
    if create_default:
        policy = context.service_containerpolicy.getPolicy(policy_name)
        policy.createDefaultDocument(folder, title)
    helpers.add_and_edit(context, id, REQUEST)
    return ''

def xml_import_handler(object, node, factory=None):
    """Helper for importing folder objects into an other object"""

    def default_factory(object, id, title):
        object.manage_addProduct["Silva"].manage_addFolder(id, title, 0)
    
    id = get_xml_id(node)
    title = get_xml_title(node)
    id = str(mangle.Id(object, id).unique())
    if factory is None:
        factory = default_factory
    assert callable(factory), "Factory is not callable"
    factory(object, id, title)
    newfolder = getattr(object, id)
    for child in node.childNodes:
        if get_importer(child.nodeName):
            xml_import_helper(newfolder, child)
        elif (child.nodeName != u'title' and 
                hasattr(newfolder, 'set_%s' % child.nodeName) and 
                child.childNodes[0].nodeValue):
            getattr(newfolder, 'set_%s' % child.nodeName)(
                                    child.childNodes[0].nodeValue)

    return newfolder
