import Globals
from Acquisition import aq_parent, aq_inner
from AccessControl import ModuleSecurityInfo, ClassSecurityInfo,\
     getSecurityManager
from AccessControl.PermissionRole import rolesForPermissionOn
from AccessControl.Permission import Permission
from Products.Silva import SilvaPermissions
from Products.Silva import roleinfo
from Products.Silva.IRoot import IRoot
from Products.Silva.adapters import adapter
from Products.Silva.adapters import interfaces

from DateTime import DateTime
from types import ListType

module_security = ModuleSecurityInfo('Products.Silva.adapters.security')

class ViewerSecurityAdapter(adapter.Adapter):
    __implements__ = interfaces.IViewerSecurity

    security = ClassSecurityInfo()

    security.declareProtected(SilvaPermissions.ApproveSilvaContent,
                              'setAcquired')
    def setAcquired(self):
        # if we're root, we can't set it to acquire, just give
        # everybody permission again
        if IRoot.isImplementedBy(self.context):
            self.context.manage_permission(
                SilvaPermissions.View,
                roles=roleinfo.ALL_ROLES,
                acquire=0)
        else:
            self.context.manage_permission(
                SilvaPermissions.View,
                roles=(),
                acquire=1)
    
    security.declareProtected(SilvaPermissions.ApproveSilvaContent,
                              'setMinimumRole')
    def setMinimumRole(self, role):
        if role == 'Anonymous':
            self.setAcquired()
        else:
            self.context.manage_permission(
                SilvaPermissions.View,
                roles=roleinfo.getRolesAbove(role),
                acquire=0)

    security.declareProtected(SilvaPermissions.ApproveSilvaContent,
                              'isAcquired')
    def isAcquired(self):
        if (IRoot.isImplementedBy(self.context) and
            self.getMinimumRole() == 'Anonymous'):
            return 1
        # it's unbelievable, but that's the Zope API..
        p = Permission(SilvaPermissions.View, (), self.context)
        return type(p.getRoles(default=[])) is ListType
                
    security.declareProtected(SilvaPermissions.ApproveSilvaContent,
                              'getMinimumRole')
    def getMinimumRole(self):
        # XXX this only works if rolesForPermissionOn returns roles
        # in definition order..
        return str(rolesForPermissionOn(SilvaPermissions.View, self.context)[0])
    
    security.declareProtected(SilvaPermissions.ApproveSilvaContent,
                              'getMinimumRoleAbove')
    def getMinimumRoleAbove(self):
        if IRoot.isImplementedBy(self.context):
            return 'Anonymous'
        else:
            parent = aq_parent(aq_inner(self.context))
            return getViewerSecurityAdapter(parent).getMinimumRole()

Globals.InitializeClass(ViewerSecurityAdapter)

# XXX in the future we want to define a getAdapter
# ViewerSecurityAdapter should then be defined for every ISilvaObject
# (probably we'd define another adapter on IRoot and refactor this one)
module_security.declareProtected(
    SilvaPermissions.ApproveSilvaContent,
    'getViewerSecurityAdapter')
def getViewerSecurityAdapter(context):
    return ViewerSecurityAdapter(context).__of__(context)

# 20 minutes, expressed as a fraction of a day
LOCK_DURATION = (1./24./60.)*20.

# XXX this adapter still depends on variable _lock_info being defined
# on the Security mixin.

class LockAdapter(adapter.Adapter):
    __implements__ = interfaces.ILockable
        
    security = ClassSecurityInfo()
    
    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                              'createLock')
    def createLock(self):
        if self.isLocked():
            return 0
        username = getSecurityManager().getUser().getUserName()
        dt = DateTime()
        self.context._lock_info = username, dt
        return 1

    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                              'breakLock')
    def breakLock(self):
        self.context._lock_info = None

    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                              'isLocked')
    def isLocked(self):
        if self.context._lock_info is None:
            return 0
        username, dt = self.context._lock_info
        current_dt = DateTime()
        if current_dt - dt >= LOCK_DURATION:
            return 0
        current_username = getSecurityManager().getUser().getUserName()
        return username != current_username

Globals.InitializeClass(LockAdapter)

module_security.declareProtected(
    SilvaPermissions.ChangeSilvaContent,
    'getLockAdapter')
def getLockAdapter(context):
    return LockAdapter(context).__of__(context)
