from AccessControl import ClassSecurityInfo
from Globals import InitializeClass
import SilvaPermissions

from interfaces import IAccessManager

from Products.Silva.i18n import translate as _

class AccessManager:
    """Mixin class for objects to request local roles on the object"""

    security = ClassSecurityInfo()
    __implements__ = IAccessManager

    # this method needs low permission settings because it should be useable by visitors
    security.declareProtected(SilvaPermissions.ViewAuthenticated,
                              'request_roles_for_user')
    def request_roles_for_user(self, userid, roles):
        """Request a role on the current object and send an e-mail to the nearest chiefeditor/manager"""
        if not hasattr(self, '_requested_roles'):
            self._requested_roles = []
        for role in roles:
            if not (userid, role) in self._requested_roles:
                self._requested_roles.append((userid, role))
                self._p_changed = 1
        # search for the username of the first chief-editor for this object
        ces = self.sec_get_nearest_of_role('ChiefEditor')
        if not ces:
            raise Exception, _('Sorry, no ChiefEditors are available to receive the request.')
        for role in roles:
            for ce in ces:
                # XXX i18n - I'm really not sure if we want to translate this, 
                # since it would mean the ChiefEditor would get emails in the 
                # language the *client* is using...
                """
                message = _(('\'${userid}\' has requested the ${role} role at '
                                'this location:\n${absolute_url}.\n\n'
                                'Go to ${absolute_url}/edit/tab_access\n'
                                'to process the request.'))
                message.set_mapping({'userid': userid,
                                        'role': role,
                                        'absolute_url': 
                                            self.aq_inner.absolute_url()
                                    })
                self.service_messages.send_message(userid, ce, _('Access request'), message)
                """
                # XXX i18n - this is the original code, remove the quotes above and remove the
                # two lines below
                message = '\'%s\' has requested the %s role at this location:\n%s.\n\nGo to %s/edit/tab_access\nto process the request.' % (userid, role, self.aq_inner.absolute_url(), self.aq_inner.absolute_url())
                self.service_messages.send_message(userid, ce, 'Access request', message)
                
        self.service_messages.send_pending_messages()

    security.declareProtected(SilvaPermissions.ChangeSilvaAccess,
                              'allow_role')
    def allow_role(self, userid, role):
        """Allows the role and send an e-mail to the user"""
        member = self.service_members.get_member(userid)
        if not member.is_approved():
            raise Exception, _('Member is not approved')
        self._allow_role_helper(userid, role)

    security.declareProtected(SilvaPermissions.ChangeSilvaAccess,
                              'approve_and_allow')
    def approve_and_allow(self, userid, role):
        """Approves a member and then allows him the role"""
        member = self.service_members.get_member(userid)
        member.approve()
        self._allow_role_helper(userid, role)

    def _allow_role_helper(self, userid, role):
        self.aq_inner.sec_assign(userid, role)
        self._requested_roles.remove((userid, role))
        ces = self.sec_get_nearest_of_role('ChiefEditor')
        if not ces:
            raise Exception, _('No ChiefEditors are available to receive the request.')
        for ce in ces:
            # XXX i18n - this has the same problems as the part above, not
            # sure if we should translate this...
            """
            message = _(('The ${role} has been assigned to you at this '
                            'location:\n${location}\nGet to work.'))
            message.set_mapping({'role': role,
                                    'location': self.aq_inner.absolute_url()})
            self.service_messages.send_message(ce, userid, _('Access granted'), message)
            """
                                    
            # XXX i18n - uncomment the part above and remove the line below to
            # have i18n'ed emails sent out
            self.service_messages.send_message(ce, userid, 'Access granted', 'The %s role has been assigned to you at this location:\n%s\nGet to work.' % (role, self.aq_inner.absolute_url()))

    security.declareProtected(SilvaPermissions.ChangeSilvaAccess,
                              'deny_role')
    def deny_role(self, userid, role):
        """Denies the role and send an e-mail to the user"""
        ces = self.sec_get_nearest_of_role('ChiefEditor')
        if not ces:
            raise Exception, _('No ChiefEditors are available to receive the request.')
        for ce in ces:
            # XXX i18n - see above, perhaps we want to translate this too,
            # but I'm far from sure...
            self.service_messages.send_message(ce, userid, 'Access denied', 'The %s role has been denied for this location:\n %s\nYou can appeal.' % (role, self.aq_inner.absolute_url()))
        self._requested_roles.remove((userid, role))

    security.declareProtected(SilvaPermissions.ChangeSilvaAccess,
                              'send_messages')
    def send_messages(self):
        """Should be called after approval or denial actions are finished.

        Will send pending e-mails
        """
        self.service_messages.send_pending_messages()

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'get_available_roles')
    def get_available_roles(self):
        # XXX this list of roles should really be in roleinfo, but what is it?
        ars = ['Viewer', 'Reader', 'Author', 'Editor']
        userrs = self.sec_get_local_roles_for_userid(
            self.REQUEST.AUTHENTICATED_USER.getId())
        for role in userrs:
            if role in ars:
                ars.remove(role)
        return ars

    security.declareProtected(SilvaPermissions.ChangeSilvaAccess,
                              'requested_roles')
    def requested_roles(self):
        """Returns a list of (userid, role) tuples of all requested roles on this object"""
        if not hasattr(self, '_requested_roles'):
            return []
        return self._requested_roles

    # note the low security restriction on this method, this allows unauthenticated users to add
    #   themselves to acl_users
    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'add_user')
    def add_user(self, userid, password):
        """Adds the user to the userfolder. Note that the user will not get a memberobject using this method"""
        if not hasattr(self, 'service_members') or not self.service_members.allow_authentication_requests():
            raise Exception, _('Requests for authentication to this site are not allowed.')

        userfolder = self.acl_users.aq_inner
        userfolder.userFolderAddUser(userid, password, [], [])

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'is_userid_available')
    def is_userid_available(self, userid):
        """Returns true if the userid is not yet in use"""
        return userid not in self.get_valid_userids()

InitializeClass(AccessManager)
