# Copyright (c) 2002 Infrae. All rights reserved.
# See also LICENSE.txt
# $Revision: 1.34 $

# Python
from StringIO import StringIO

# Zope
from OFS import Folder
from AccessControl import ClassSecurityInfo
from Globals import InitializeClass, DevelopmentMode
from DateTime import DateTime

# Silva
import SilvaPermissions
from Versioning import Versioning
from Content import Content

class VersionedContent(Content, Versioning, Folder.Folder):
    security = ClassSecurityInfo()
    
    # there is always at least a single version to start with,
    # created by the object's factory function
    _version_count = 1

    def __init__(self, id):
        """Initialize VersionedContent.

        VersionedContent has no title of its own; its versions do.
        """
        VersionedContent.inheritedAttribute('__init__')(
            self, id, '[VersionedContent title bug]')
        self._cached_data = {}
    
    # MANIPULATORS
    
    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                              'set_title')
    def set_title(self, title):
        """Set title of version under edit.
        """
        editable = self.get_editable()
        if editable is None:
            return
        editable.set_title(title)
        if self.id == 'index':
            container = self.get_container()
            container._invalidate_sidebar(container)
    
    security.declareProtected(SilvaPermissions.ChangeSilvaViewRegistry,
                              'cleanPublicRenderingCache')
    def cleanPublicRenderingCache(self):
        """Cleans all current caching data from the cache.
        Currently this is only necessary for an upgrade of old content object
        which do not have cache yet.
        """
        self._cached_data = {}


    # ACCESSORS
    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                             'get_title')
    def get_title(self):
        """Get title for public use, from published version.
        """
        viewable = self.get_viewable()
        if viewable is None:
            return "[No title available]"
        return viewable.get_title()

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'get_title_editable')
    def get_title_editable(self):
        """Get title for editable or previewable use
        """
        # Ask for 'previewable', which will return either the 'next version'
        # (which may be under edit, or is approved), or the public version, 
        # or, as a last resort, the closed version.
        # This to be able to show at least some title in the Silva edit
        # screens.
        previewable = self.get_previewable()
        if previewable is None:
            return "[No title available]"
        return previewable.get_title()

    security.declareProtected(
        SilvaPermissions.AccessContentsInformation, 'get_short_title')
    def get_short_title(self):
        """Get short_title for public use, from published version.
        """
        # Analogous to get_title
        viewable = self.get_viewable()
        if viewable is None:
            return "[No (short) title available]"
        return viewable.get_short_title()

    security.declareProtected(
        SilvaPermissions.AccessContentsInformation, 'get_short_title_editable')
    def get_short_title_editable(self):
        """Get short_title for editable or previewable use
        """
        # Analogous to get_title_editable
        previewable = self.get_previewable()
        if previewable is None:
            return "[No (short) title available]"
        return previewable.get_short_title()

    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                              'sec_get_last_author_userid')
    def sec_get_last_author_userid(self):
        """Ask last userid of current transaction under edit.
        If it doesn't exist, get published version, or last closed.
        """
        version_id = (self.get_next_version() or
                      self.get_public_version() or
                      self.get_last_closed_version())
        # get the last transaction
        last_transaction = getattr(self,
                                   version_id).undoable_transactions(0, 1)
        if len(last_transaction) == 0:
            return None
        return last_transaction[0]['user_name']
                                        
    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'get_modification_datetime')
    def get_modification_datetime(self):
        """Get content modification date.
        """
        version_id = self.get_next_version() or self.get_public_version()
        if version_id is not None:
            return getattr(self, version_id).bobobase_modification_time()
        else:
            return self.bobobase_modification_time()
        
    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                              'get_editable')
    def get_editable(self):
        """Get the editable version (may be object itself if no versioning).
        """
        # the editable version is the unapproved version
        version_id = self.get_unapproved_version()
        if version_id is None:
            return None # there is no editable version
        return getattr(self, version_id)

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'get_previewable')
    def get_previewable(self):
        """Get the previewable version (may be the object itself if no
        versioning).
        """
        version_id = self.get_next_version()
        if version_id is None:
            version_id = self.get_public_version()
            if version_id is None:
                version_id = self.get_last_closed_version()
                if version_id is None:
                    return None
        return getattr(self, version_id)

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'get_viewable')
    def get_viewable(self):
        """Get the publically viewable version (may be the object itself if
        no versioning).
        """
        version_id = self.get_public_version()
        if version_id is None:
            return None # There is no public document
        return getattr(self, version_id)

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'get_last_closed')
    def get_last_closed(self):
        """Get the last closed version (may be the object itself if
        no versioning).
        """
        version_id = self.get_last_closed_version()
        if version_id is None:
            return None # There is no public document
        return getattr(self, version_id)

    security.declareProtected(SilvaPermissions.View, 'view')
    def view(self, view_type='public'):
        """
        """
        # XXX view_type=edit or add does not work anyway, but ...
        if (view_type in ('edit','add')) or (DevelopmentMode is not None):
            return VersionedContent.inheritedAttribute('view')(self, view_type)

        data, cached_datetime = self._cached_data.get(view_type, (None, None))

        if (cached_datetime is None or
             cached_datetime <=
             self.get_public_version_publication_datetime() or
             cached_datetime <=
             self.service_extensions.get_refresh_datetime()):
            data = VersionedContent.inheritedAttribute('view')(self, view_type)
            cached_datetime = DateTime()
            if self.is_cacheable():
                cached_data = data
            else:
                cached_data = None
            self._cached_data[view_type] = (cached_data, cached_datetime)
            self._cached_data = self._cached_data
        else:
            # XXX is_version_published() triggers a workflow update
            # check that is not necessary, ideally remove it somehow.
            if (data is not None and
                 not self.is_version_published()):
                # do not render versions which have been closed explicitely
                data = None
                self._cached_data[view_type] = (data, DateTime())
                self._cached_data = self._cached_data

            if data is None:
                data = VersionedContent.inheritedAttribute('view')(
                    self, view_type)
        return data
        
    security.declareProtected(SilvaPermissions.View, 'is_cacheable')
    def is_cacheable(self):
        """Return true if the result of the view method can be safely
        cached.
        """
        # by default nothing is safely cacheable
        return 0

InitializeClass(VersionedContent)

class CatalogedVersionedContent(VersionedContent):
    """This class merely exists to mix VersionedContent with CatalogedVersioning
    """

    default_catalog = 'service_catalog'

    def manage_afterAdd(self, item, container):
        CatalogedVersionedContent.inheritedAttribute('manage_afterAdd')(self, item, container)
        for version in self._get_indexable_versions():
            getattr(self, version).reindex_object()

    def manage_afterClone(self, item):
        CatalogedVersionedContent.inheritedAttribute('manage_afterClone')(self, item)
        for version in self._get_indexable_versions():
            getattr(self, version).reindex_object()

    # Override this method from superclasses so we can remove all versions from the catalog
    def manage_beforeDelete(self, item, container):
        CatalogedVersionedContent.inheritedAttribute('manage_beforeDelete')(self, item, container)
        for version in self._get_indexable_versions():
            getattr(self, version).unindex_object()

    def _get_indexable_versions(self):
        ret = []
        for version in [self.get_unapproved_version(), 
                        self.get_approved_version(), 
                        self.get_public_version()
                        ] + self.get_previous_versions():
            if version:
                ret.append(version)
        return ret

    def _index_version(self, version):
        if version[0] is None:
            return None
        getattr(self, str(version[0])).index_object()
        
    def _reindex_version(self, version):
        if version[0] is None:
            return None
        getattr(self, str(version[0])).reindex_object()

    def _unindex_version(self, version):
        if version[0] is None:
            return None
        getattr(self, str(version[0])).unindex_object()
        
InitializeClass(CatalogedVersionedContent)

