# python
import sys, string, smtplib

# zope
from OFS import SimpleItem
from AccessControl import ClassSecurityInfo
from Products.PageTemplates.PageTemplateFile import PageTemplateFile
import Globals, zLOG
from DateTime import DateTime

# silva
from IMembership import IMember, IMemberService, IMemberMessageService
from Content import Content
from Membership import cloneMember
import SilvaPermissions
from helpers import add_and_edit

# other products
from Products.Formulator.Form import ZMIForm
from Products.Formulator.Errors import FormValidationError
from Products.Formulator import StandardFields


class SimpleMember(Content, SimpleItem.SimpleItem):
    """Silva Simple Member"""

    __implements__ = IMember

    security = ClassSecurityInfo()

    meta_type = 'Silva Simple Member'
    
    def __init__(self, id):
        self.id = id
        self._title = id
        self._fullname = None
        self._email = None
        self._creation_datetime = self._modification_datetime = DateTime()
        self._is_approved = 0

    def manage_afterAdd(self, item, container):
        # make the user chiefeditor of his own object
        self.sec_assign(self.id, 'ChiefEditor')

    def manage_beforeDelete(self, item, container):
        pass
        
    security.declareProtected(SilvaPermissions.ChangeSilvaAccess,
                              'security_trigger')
    def security_trigger(self):
        pass

    security.declareProtected(SilvaPermissions.ChangeSilvaAccess,
                              'set_fullname')
    def set_fullname(self, fullname):
        """set the full name"""
        self._fullname = fullname
        self._p_changed = 1

    security.declareProtected(SilvaPermissions.ChangeSilvaAccess,
                              'set_email')
    def set_email(self, email):
        """ set the email address.
           (does not test, if email address is valid)
        """
        self._email = email
        self._p_changed = 1

    security.declareProtected(SilvaPermissions.ChangeSilvaAccess,
                              'approve')
    def approve(self):
        """Approve the member"""
        self._is_approved = 1
        self._p_changed = 1
    
    # ACCESSORS
    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'userid')
    def userid(self):
        """userid
        """
        return self.id

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'fullname')
    def fullname(self):
        """fullname
        """
        if self._fullname is None:
            return self.id
        return self._fullname

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'email')
    def email(self):
        """email
        """
        return self._email

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'is_approved')
    def is_approved(self):
        """is_approved
        """
        return self._is_approved
    
Globals.InitializeClass(SimpleMember)

manage_addSimpleMemberForm = PageTemplateFile(
    "www/simpleMemberAdd", globals(),
    __name__='manage_addSimpleMemberForm')

def manage_addSimpleMember(self, id, REQUEST=None):
    """Add a Simple Member."""
    object = SimpleMember(id)
    self._setObject(id, object)
    add_and_edit(self, id, REQUEST)
    return ''

class SimpleMemberService(SimpleItem.SimpleItem):
    __implements__ = IMemberService

    security = ClassSecurityInfo()

    meta_type = 'Silva Simple Member Service'
    
    manage_options = (
        {'label':'Edit', 'action':'manage_editForm'},
        ) + SimpleItem.SimpleItem.manage_options

    security.declareProtected('View management screens', 'manage_editForm')
    manage_editForm = PageTemplateFile(
        'www/extendedMemberServiceEdit', globals(),  __name__='manage_editForm')

    security.declareProtected('View management screens', 'manage_main')
    manage_main = manage_editForm

    def __init__(self, id):
        self.id = id
        self._allow_subscription = 0

    # XXX will be used by access tab and should be opened wider if this
    # is central service..
    security.declareProtected(SilvaPermissions.ApproveSilvaContent,
                              'find_members')
    def find_members(self, search_string):
        userids = self.get_valid_userids()
        result = []
        for userid in userids:
            if userid.find(search_string) != -1:
                result.append(self.get_cached_member(userid))
        return result

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'is_user')
    def is_user(self, userid):
        return userid in self.get_valid_userids()

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'get_member')
    def get_member(self, userid):
        if not self.is_user(userid):
            return None
        # get member, add it if it doesn't exist yet
        members = self.Members.aq_inner
        member = getattr(members, userid, None)
        if member is None:
            members.manage_addProduct['Silva'].manage_addSimpleMember(userid)
            member = getattr(members, userid)
        return member

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'get_cached_member')
    def get_cached_member(self, userid):
        """Returns a cloned member object, which can be stored in the ZODB"""
        return cloneMember(self.get_member(userid)).__of__(self)

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'allow_subscription')
    def allow_subscription(self):
        return self._allow_subscription 

    security.declareProtected(SilvaPermissions.ChangeSilvaAccess,
                              'set_allow_subscription')
    def set_allow_subscription(self, value):
        """sets allow_subscription"""
        self._allow_subscription = value

    security.declareProtected('View management screens',
                              'manage_allowSubscription')
    def manage_allowSubscription(self, REQUEST):
        """manage method to set allow_subscription"""
        self.set_allow_subscription(int(REQUEST['allow_subscription']))

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'get_subscription_url')
    def get_subscription_url(self):
        """Return the url for the subscription form, relative from resources
        directory (so including the escaped productname!!)
        """
        return 'Silva/become_visitor'

Globals.InitializeClass(SimpleMemberService)

manage_addSimpleMemberServiceForm = PageTemplateFile(
    "www/simpleMemberServiceAdd", globals(),
    __name__='manage_addSimpleMemberServiceForm')

def manage_addSimpleMemberService(self, id, REQUEST=None):
    """Add a Simple Member Service."""
    object = SimpleMemberService(id)
    self._setObject(id, object)
    add_and_edit(self, id, REQUEST)
    return ''

class EmailMessageService(SimpleItem.SimpleItem):
    """Simple implementation of IMemberMessageService that sends email
    messages.
    """
    
    meta_type = 'Silva Email Message Service'

    security = ClassSecurityInfo()

    __implements__ = IMemberMessageService

    manage_options = (
        {'label':'Edit', 'action':'manage_editForm'},
        ) + SimpleItem.SimpleItem.manage_options

    security.declareProtected('View management screens', 'manage_editForm')
    manage_editForm = PageTemplateFile(
        'www/emailMessageServiceEdit', globals(),  __name__='manage_editForm')

    security.declareProtected('View management screens', 'manage_main')
    manage_main = manage_editForm

    def __init__(self, id, title):
        self.id = id
        self.title = title
        self._host = None
        self._port = 25
        self._fromaddr = None
        self._send_email_enabled = 0
        self._debug = 0

        edit_form = ZMIForm('edit', 'Edit')

        host = StandardFields.StringField(
            'host',
            title="Host",
            required=1,
            display_width=20)
        port = StandardFields.IntegerField(
            'port',
            title="Port",
            required=1,
            display_width=20)
        fromaddr = StandardFields.EmailField(
            'fromaddr',
            title="From address",
            required=1,
            display_width=20)
        send_email_enabled = StandardFields.CheckBoxField(
            'send_email_enabled',
            title="Actually send email",
            required=0,
            default=0)
        debug = StandardFields.CheckBoxField(
            'debug',
            title="Debug mode",
            required=0,
            default=0)
        
        for field in [host, port, fromaddr, send_email_enabled, debug]:
            edit_form._setObject(field.id, field)
        self.edit_form = edit_form
        
    security.declareProtected(SilvaPermissions.ViewManagementScreens,
                              'edit_form')
    # MANIPULATORS
    security.declareProtected(SilvaPermissions.ViewManagementScreens,
                              'manage_edit')
    def manage_edit(self, REQUEST):
        """manage method to update data"""
        try:
            result = self.edit_form.validate_all(REQUEST)
        except FormValidationError, e:
            messages = ["Validation error(s)"]
            # loop through all error texts and generate messages for it
            for error in e.errors:
                messages.append("%s: %s" % (error.field.get_value('title'),
                                            error.error_text))
            # join them all together in a big message
            message = string.join(messages, "<br>")
            # return to manage_editForm showing this failure message 
            return self.manage_editForm(self, REQUEST,
                                        manage_tabs_message=message)

        for key, value in result.items():
            setattr(self, '_' + key, value)
        return self.manage_main(manage_tabs_message="Changed settings.")

    # XXX these security settings are not the right thing.. perhaps
    # create a new permission?
    security.declareProtected(SilvaPermissions.ChangeSilvaAccess,
                              'send_message')
    def send_message(self, from_memberid, to_memberid, subject, message):
        if not hasattr(self.aq_base, '_v_messages'):
            self._v_messages = {}
        self._v_messages.setdefault(to_memberid, {}).setdefault(
            from_memberid, []).append((subject, message))

    # XXX have to open this up to the world, unfortunately..
    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'send_pending_messages')
    def send_pending_messages(self):
        if not hasattr(self.aq_base, '_v_messages'):
            self._v_messages = {}
        get_member = self.service_members.get_member
        for to_memberid, message_dict in self._v_messages.items():
            to_email = get_member(to_memberid).email()
            if to_email is None:
                self._debug_log("no email for: %s" % to_memberid)
                continue
            lines = []
            # XXX usually all messages have the same subject yet,
            # but this can be assumed here per se.
            common_subject=None
            reply_to = {}
            for from_memberid, messages in message_dict.items():
                if self._debug:
                    self._debug_log("From memberid: %s " % from_memberid)
                from_email = get_member(from_memberid).email()
                if from_email is not None:
                    reply_to[from_email] = 1
                    lines.append("Message from: %s (email: %s)" %
                                 (from_memberid, from_email))
                else:
                    lines.append("Message from: %s (no email available)" %
                                 from_memberid)
                for subject, message in messages:
                    lines.append(subject)
                    lines.append('')
                    lines.append(message)
                    lines.append('')
                    if common_subject is None:
                        common_subject = subject
                    else:
                        if common_subject != subject:
                            # XXX this is very stupid, but what else?
                            # maybe leave empty?
                            common_subject = 'Notification on status change'

            text = '\n'.join(lines)
            header = {}
            if common_subject is not None:
                header['Subject'] = common_subject
            if reply_to:
                header['Reply-To'] = ', '.join(reply_to.keys())
                # XXX set from header ?
            self._send_email(to_email, text, header=header)

        # XXX if above raises exception: mail queue is not flushed
        # as this line is not reached. bug or feature ?
        self._v_messages = {}


    def _debug_log(self, message, details=''):
        """ simple helper for logging """
        if self._debug:
            zLOG.LOG('Silva messages',zLOG.BLATHER, message, details)

    # ACCESSORS
    security.declareProtected(SilvaPermissions.ViewManagementScreens,
                              'server')
    def server(self):
        """Returns (host, port)"""
        return (self._host, self._port)

    security.declareProtected(SilvaPermissions.ViewManagementScreens,
                              'host')
    def host(self):
        """return self._host"""
        return self._host

    security.declareProtected(SilvaPermissions.ViewManagementScreens,
                              'port')
    def port(self):
        """return self._port"""
        return self._port

    security.declareProtected(SilvaPermissions.ViewManagementScreens,
                              'fromaddr')
    def fromaddr(self):
        """return self._fromaddr"""
        return self._fromaddr

    security.declareProtected(SilvaPermissions.ViewManagementScreens,
                              'debug')
    def debug(self):
        return self._debug

    security.declareProtected(SilvaPermissions.ViewManagementScreens,
                              'send_email_enabled')
    def send_email_enabled(self):
        return self._send_email_enabled
    
    def _send_email(self, toaddr, msg, header={}):
        header['To'] = toaddr
        if not header.has_key('From'):
            header['From'] = self._fromaddr
        if not header.has_key('Sender'):
            header['Sender'] = self._fromaddr

        msg_lines = [ '%s: %s' % (k,v) for k,v in header.items() ]
        msg_lines.append('')
        msg_lines.append(msg)
        msg = '\r\n'.join(msg_lines)
        self._debug_log(msg)
        if self._send_email_enabled:
            try:
                server = smtplib.SMTP(self._host, self._port)
                failures = server.sendmail(self._fromaddr, [toaddr], msg)
                server.quit()
                if failures:
                    # next line raises KeyError if toaddr is no key
                    # in failures -- however this should not happen
                    zLOG.LOG('Silva service_messages',zLOG.PROBLEM,
                             'could not send mail to %s' % toaddr,
                             details=('error[%s]: %s' % failures[toaddr]) )
                             
            except smtplib.SMTPException:
                # XXX seems the documentation failes here
                # if e.g. connection is refused, this raises another
                # kind of exception but smtplib.SMTPException
                zLOG.LOG('Silva service_messages',zLOG.PROBLEM,
                         'sending mail failed', sys.exc_info())
                # XXX how to notify user? do it the hard way for now:
                raise

Globals.InitializeClass(EmailMessageService)

manage_addEmailMessageServiceForm = PageTemplateFile(
    "www/serviceEmailMessageServiceAdd", globals(),
    __name__='manage_addEmailMessageServiceForm')

def manage_addEmailMessageService(self, id, title='', REQUEST=None):
    """Add member message service."""
    object = EmailMessageService(id, title)
    self._setObject(id, object)
    object = getattr(self, id)
    add_and_edit(self, id, REQUEST)
    return ''
