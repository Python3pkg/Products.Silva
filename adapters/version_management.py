import Globals
from AccessControl import ModuleSecurityInfo, ClassSecurityInfo
from Products.Silva.adapters import adapter
from Products.Silva.adapters.interfaces import IVersionManagement
from Products.Silva.interfaces import IVersion
from Products.Silva.Versioning import VersioningError
from Products.Silva import SilvaPermissions

module_security = ModuleSecurityInfo('Products.Silva.adapters.version_management')

class VersionManagementAdapter(adapter.Adapter):
    """Adapter to manage Silva versions (duh?)"""
    
    __implements__ = IVersionManagement
    security = ClassSecurityInfo()

    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                                'getVersionById')
    def getVersionById(self, id):
        return getattr(self.context, id)

    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                                'getPublishedVersion')
    def getPublishedVersion(self):
        id = self.context.get_public_version()
        if id is not None:
            return getattr(self.context, id)

    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                                'getUnapprovedVersion')
    def getUnapprovedVersion(self):
        id = self.context.get_unapproved_version()
        if id is not None:
            return getattr(self.context, id)

    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                                'getApprovedVersion')
    def getApprovedVersion(self):
        id = self.context.get_approved_version()
        if id is not None:
            return getattr(self.context, id)

    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                                'getVersionIds')
    def getVersionIds(self):
        objects = self.context.objectValues()
        ret = []
        for object in objects:
            if IVersion.isImplementedBy(object):
                ret.append(object.id)
        return ret

    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                                'getVersions')
    def getVersions(self, sort_attribute='id'):
        objects = [o for o in self.context.objectValues() if 
                    IVersion.isImplementedBy(o)]
        if sort_attribute == 'id':
            objects.sort(lambda a, b: cmp(int(a.id), int(b.id)))
        elif sort_attribute:
            objects.sort(
                lambda a, b: 
                    cmp(
                        getattr(a, sort_attribute), 
                        getattr(b, sort_attribute)
                    )
                )
        return objects

    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                                'revertEditableToOld')
    def revertEditableToOld(self, copy_id):
        if self.getApprovedVersion() is not None:
            raise VersioningError, 'approved version available'
        if not hasattr(self.context, copy_id):
            raise AttributeError, copy_id
        current_version = self.getUnapprovedVersion()
        # move the current editable version to _previous_versions
        if current_version is not None:
            # throw away publication and expiration time, they can only get 
            # in the way later
            # XXX disabled for now, seems more logical
            current_version_id = current_version.id
            version_tuple = self.context._unapproved_version # (current_version_id, None, None)
            if self.context._previous_versions is None:
                self.context._previous_versions = []
            self.context._previous_versions.append(version_tuple)
            self.context._reindex_version(current_version_id)
        # just hope for the best... scary API
        new_version_id = self._createUniqueId()
        self.context.manage_clone(getattr(self.context, copy_id), new_version_id)
        self.context._unapproved_version = (new_version_id, None, None)

    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                                'deleteVersion')
    def deleteVersion(self, id):
        approved = self.getApprovedVersion()
        if approved is not None and approved.id == id:
            raise VersioningError, 'version is approved'
        published = self.getPublishedVersion()
        if published is not None and published.id == id:
            raise VersioningError, 'version is public'
        # remove any reference from the version list
        # we can skip approved and published, since we checked those above
        unapproved = self.getUnapprovedVersion()
        if unapproved is not None and unapproved.id == id:
            self.context._unapproved_version = (None, None, None)
        else:
            for version in self.context._previous_versions:
                if version[0] == id:
                    self.context._previous_versions.remove(version)
        self.context.manage_delObjects([id])

    security.declareProtected(SilvaPermissions.ViewManagementScreens,
                                'deleteOldVersions')
    def deleteOldVersions(self, number_to_keep=0):
        versions = self.getVersionIds()
        unapproved = self.getUnapprovedVersion()
        approved = self.getApprovedVersion()
        public = self.getPublishedVersion()
        if unapproved is not None and unapproved.id in versions:
            versions.remove(unapproved.id)
        if approved is not None and unapproved.id in versions:
            versions.remove(approved.id)
        if public is not None and public.id in versions:
            versions.remove(public.id)
        if len(versions) > number_to_keep:
            if number_to_keep > 0:
                versions = versions[:-number_to_keep]
            self.context.manage_delObjects(versions)

    def _createUniqueId(self):
        # for now we use self.context._version_count, we may
        # want to get rid of that nasty trick in the future though...
        newid = str(self.context._version_count)
        self.context._version_count += 1
        return newid
    
Globals.InitializeClass(VersionManagementAdapter)

module_security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                                  'getVersionManagementAdapter')
def getVersionManagementAdapter(context):
    return VersionManagementAdapter(context).__of__(context)
    
