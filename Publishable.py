import Interfaces
from AccessControl import ClassSecurityInfo
from Globals import InitializeClass
import SilvaPermissions

class Publishable:
    """Mixin class that can be provided to implement the Publishable
    interface.
    """
    security = ClassSecurityInfo()
        
    __implements__ = Interfaces.Publishable

    _active_flag = 1

    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                              'activate')
    def activate(self):
        if not self.can_activate():
            return
        self._active_flag = 1
        # refresh container of parent (may be parent itself)
        # we use parent so we don't get *this* publishable container
        self.aq_parent.get_container()._refresh_ordered_ids(self)

    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                              'deactivate')
    def deactivate(self):
        if not self.can_deactivate():
            return
        if Interfaces.Versioning.isImplementedBy(self):
            # if we want to deactivate an approved version, revoke
            # approval first
            if self.is_version_approved():
                self.unapprove_version() 
        self._active_flag = 0
        # FIXME: should we deactivate all contents if this is a container?

        # refresh container of parent (may be parent itself)
        # we use parent so we don't get *this* publishable container
        self.aq_parent.get_container()._refresh_ordered_ids(self)
        
    # ACCESSORS

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'is_active')
    def is_active(self):
        return self._active_flag

    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                              'can_activate')
    def can_activate(self):
        return not self._active_flag

    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                              'can_deactivate')
    def can_deactivate(self):
        if not self._active_flag:
            return 0
        # can't deactivate default
        if Interfaces.Content.isImplementedBy(self) and self.is_default():
            return 0
        # can't deactivate something published
        if self.is_published():
            return 0
        return 1

    # FIXME: perhaps make this less public?
    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'is_published')
    def is_published(self):
        if Interfaces.Versioning.isImplementedBy(self):
            return self.is_version_published()
        else:
            # FIXME: should always be published if no versioning supported?
            return 1

    security.declareProtected(SilvaPermissions.ApprovemanaSilvaContent,
                              'can_approve')
    def can_approve(self):
        """Return true if we can approve version.
        NOTE: this method is defined by the Versioning interface, but
        this is the default implementation for versioned publishables.
        """
        # if this object or any of its containers is inactive, can't approve it        
        if not self.is_active():
            return 0
        # check all containers to see if they are inactive as well
        object = self.aq_parent
        while Interfaces.Container.isImplementedBy(object):
            if not object.is_active():
                return 0
            object = object.aq_parent
        # all containers were active, so we can indeed approve
        return 1

InitializeClass(Publishable)
