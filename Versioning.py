# Copyright (c) 2002 Infrae. All rights reserved.
# See also LICENSE.txt
# $Revision: 1.35 $
# Zope
from DateTime import DateTime
from AccessControl import ClassSecurityInfo
from Globals import InitializeClass
import ExtensionClass
# Silva interfaces
from IVersioning import IVersioning
from IPublishable import IPublishable
# Silva
import SilvaPermissions

class VersioningError(Exception):
    pass

empty_version = (None, None, None)

class RequestForApprovalInfo:
    """ simple helper class storing information about the
    current request for approval
    """

    def __init__(self):
        self.request_pending = None
        self.requester = None
        self.request_messages = []
        self.request_date = None

empty_request_for_approval_info = RequestForApprovalInfo()

class Versioning:
    """Mixin baseclass to make object contents versioned.
    """
    security = ClassSecurityInfo()

    __implements__ = IVersioning
    
    _unapproved_version = empty_version
    _approved_version = empty_version
    _public_version = empty_version
    _previous_versions = None
    _request_for_approval_info = empty_request_for_approval_info
    
    # MANIPULATORS
    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                              'create_version')
    def create_version(self, version_id,
                       publication_datetime,
                       expiration_datetime):
        """Add unapproved version
        """
        self._update_publication_status()
        if self._approved_version != empty_version:
            raise VersioningError,\
                  'There is an approved version already; unapprove it. (%s)' %\
                  (self._approved_version[0])
        if self._unapproved_version != empty_version:
            raise VersioningError,\
                  'There already is an unapproved version (%s).' %\
                  (self._unapproved_version[0])
        # if a version with this name already exists, complain
        if (self._public_version and
            version_id == self._public_version[0]):
            raise VersioningError,\
                  'The public version has that id already (%s).' %\
                 (self._public_version[0])
        previous_versions = self._previous_versions or []
        for previous_version in previous_versions:
            if version_id == previous_version[0]:
                raise VersioningError,\
                      'A previous version has that id already (%s).' %\
                      (self._previous_version[0])
    
        self._unapproved_version = (version_id,
                                    publication_datetime,
                                    expiration_datetime)
        # overwrite possible previous info ...
        self._request_for_approval_info = RequestForApprovalInfo()
        self._index_version(self._unapproved_version)
        
    security.declareProtected(SilvaPermissions.ApproveSilvaContent,
                              'approve_version')
    def approve_version(self):
        """Aprove the current unapproved version.
        """
        self._update_publication_status()
        if self._unapproved_version == empty_version:
            raise VersioningError,\
                  'There is no unapproved version to approve.'
        if self._approved_version != empty_version:
            raise VersioningError,\
                  'There already is an approved version.'
        if self._unapproved_version[1] is None:
            raise VersioningError,\
                  'Cannot approve version without publication datetime.'
        if IPublishable.isImplementedBy(self):
            if not self.can_approve():
                raise VersioningError,\
                      'Cannot approve version; not allowed.'
        self._approved_version = self._unapproved_version
        self._unapproved_version = empty_version
        if self._request_for_approval_info != empty_request_for_approval_info:
            self._request_for_approval_info.request_pending = None
            self._request_for_approval_info = self._request_for_approval_info
        self._reindex_version(self._approved_version)

        # fix publication time settings; publication times in the past
        # are moved to the present to avoid strance cache behaviour.
        # XXX this is actually needed by VersionedContent
        publication_datetime = self._approved_version[1]
        publish_now = 0
        if publication_datetime is not None:
            publish_now = not (publication_datetime.isFuture())
        if publish_now:
            self._approved_version = \
                                   (self._approved_version[0],
                                    DateTime(),
                                    self._approved_version[2])
        # send messages
        info = self._get_editable_rfa_info()
        if info.requester is None:
            return # no requester found, so don't send messages
        if publish_now:
            publication_date_str="The version has been published right now.\n"
        else:
            publication_date_str = 'The version will be published at %s\n' % \
                                  _format_date_helper(publication_datetime)
        expiration_datetime = self._approved_version[2]
        if expiration_datetime is None:
            expiration_date_str=''
        else:
            expiration_date_str = 'The version will expire at %s\n' % \
                                  _format_date_helper(expiration_datetime)
            
        editor = self.REQUEST.AUTHENTICATED_USER.getUserName()
        text = "\nVersion was approved for publication by %s.\n%s%s" % \
                (editor, publication_date_str, expiration_date_str)
        self._send_message(editor, info.requester,
                           "Version approved", text)
        
    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                              'unapprove_version')
    def unapprove_version(self):
        """Unapprove an approved but not yet public version.
        """
        self._update_publication_status()
        if self._approved_version == empty_version:
            raise VersioningError,\
                  'No approved version to unapprove.'
        if self._unapproved_version != empty_version:
            raise VersioningError,\
                  ('Should never happen: unapproved version %s found while '
                   'approved version %s exists at the same time.') % \
                   (self._unapproved_version[0], self._approved_version[0])
        self._unapproved_version = self._approved_version
        self._approved_version = empty_version
        self._reindex_version(self._unapproved_version)

        # send messages to editor
        # XXX should the last author be informed, too?
        author = self.REQUEST.AUTHENTICATED_USER.getUserName()
        text = "\nVersion was unapproved by %s." % author
        self._send_message_to_editors(author, 'Unapproved', text)
        if self._request_for_approval_info.requester is not None:
            self._send_message(author,
                               self._request_for_approval_info.requester,
                               'Unapproved', text)

    security.declareProtected(SilvaPermissions.ApproveSilvaContent,
                              'close_version')
    def close_version(self):
        """Close public version.
        """
        self._update_publication_status()
        if self._public_version == empty_version:
            raise VersioningError,\
                  'No public version to close.'
        previous_versions = self._previous_versions or []
        if previous_versions:
            last_closed_version = previous_versions[-1]
        else:
            last_closed_version = empty_version            
        previous_versions.append(self._public_version)
        self._public_version = empty_version
        self._previous_versions = previous_versions

        # remove it from the catalog (if required)
        # this way the catalog only contains unapproved, approved 
        # and public versions
        self._unindex_version(self._previous_versions[-1])

    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                              'create_copy')
    def create_copy(self):
        """Create new version of public version.
        """
        if self.get_next_version() is not None:
            return    
        # get id of public version to copy
        version_id_to_copy = self.get_public_version()
        # if there is no public version, get id of last closed version
        # (which should always be there)
        if version_id_to_copy is None:
            version_id_to_copy = self.get_last_closed_version()
            # there is no old version left!
            if version_id_to_copy is None:
                # FIXME: could create new empty version..
                raise  VersioningError, "Should never happen!"
        # copy published version
        new_version_id = str(self._version_count)
        self._version_count = self._version_count + 1
        # FIXME: this only works if versions are stored in a folder as
        # objects; factory function for VersionedContent objects should
        # create an initial version with name '0', too.
        # only testable in unit tests after severe hacking..
        self.manage_clone(getattr(self, version_id_to_copy),
                          new_version_id, self.REQUEST)
        self.create_version(new_version_id, None, None)

    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                              'revert_to_previous')
    def revert_to_previous(self):
        """Create a new version of public version, throw away the current one
        """
        # get the id of the version to revert to
        version_id_to_copy = (self.get_public_version() or
                              self.get_last_closed_version())
        if version_id_to_copy is None:
            raise VersioningError, "Should never happen!"
        # get the id of the current version
        current_version_id = self.get_unapproved_version()
        if current_version_id is None:
            raise VersioningError, "No unapproved version available"
        self._unindex_version((current_version_id,))
        # delete the current version
        self.manage_delObjects([current_version_id])
        # and copy the previous using the current id
        self.manage_clone(getattr(self, version_id_to_copy),
                          current_version_id, self.REQUEST)
        self._index_version((current_version_id,))
    
    def _get_editable_rfa_info(self):
        """ helper method: return the request for approval information,
        this creates a new one, if necessary; notifes Zope that this
        has changed in advance ... i.e. do not call this method
        if You do not want to change the information.
        """
        if self._request_for_approval_info == empty_request_for_approval_info:
            self._request_for_approval_info = RequestForApprovalInfo()
        else:
            # Zope should be notified that it has changed
            self._request_for_approval_info = self._request_for_approval_info
        return self._request_for_approval_info
    
    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                              'request_version_approval')
    def request_version_approval(self, message):
        """Request approval for the current unapproved version
        Raises VersioningError, if there is no such version,
        or it is already approved.
        Returns None otherwise
        """
        # called implicitely: self._update_publication_status()
        if self.get_unapproved_version() is None:
            raise VersioningError,\
                  'There is no unapproved version to request approval for.'

        if self.is_version_approval_requested():
            raise VersioningError,\
                  'The version is already requested for approval.'

        last_author = self.sec_get_last_author_info()

        info = self._get_editable_rfa_info()
        info.requester = self.REQUEST.AUTHENTICATED_USER.getUserName()
        info.request_date = DateTime()
        info.request_pending=1
        self._set_approval_request_message(message)
        publication_datetime = self._unapproved_version[1]
        if publication_datetime is None:
            publication_date_str=''
        else:
            publication_date_str = \
                     'The version has a proposed publication date of %s\n' % \
                     _format_date_helper(publication_datetime)
        expiration_datetime = self._unapproved_version[2]
        if expiration_datetime is None:
            expiration_date_str=''
        else:
            expiration_date_str = \
               'The version has a proposed expiration date of %s\n' % \
               _format_date_helper(expiration_datetime)
        # send messages
        text = "\nApproval was requested by %s.\n%s%s\nMessage:\n%s" % \
                (info.requester,
                 publication_date_str, expiration_date_str, message)
        self._send_message_to_editors(info.requester,
                                      'Approval requested', text)
        # XXX inform user, too (?)
        self._send_message(info.requester, last_author.userid(),
                           'Approval requested', text)

    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                              'withdraw_version_approval')
    def withdraw_version_approval(self, message):
        """Withdraw a previous request for approval
        Implementation should raise VersioningError, if the
        currently unapproved version has no request for approval yet,
        or if there is no unapproved version.
        """
        
        self._update_publication_status()
        if self.get_unapproved_version is None:
            raise VersioningError,\
                  'There is no unapproved version to request approval for.'

        if not self.is_version_approval_requested():
            raise VersioningError,\
                  'The version is not requested for approval.'
        info = self._get_editable_rfa_info()
        orginal_requester = info.requester
        info.requester = self.REQUEST.AUTHENTICATED_USER.getUserName()
        info.request_pending=None
        self._set_approval_request_message(message)
        # send messages
        text = "\nRequest for approval was withdrawn by %s.\nMessage:\n%s" \
               % (info.requester, message)
        self._send_message_to_editors(info.requester,
                                      'Approval withdrawn by author', text)
        self._send_message(info.requester, orginal_requester,
                           'Approval withdrawn by author', text)

    security.declareProtected(SilvaPermissions.ApproveSilvaContent,
                              'reject_version_approval')
    def reject_version_approval(self, message):
        """Reject a previous request for approval
        Implementation should raise VersioningError, if the
        currently unapproved version has no request for approval yet,
        or if there is no unapproved version.
        """
        
        self._update_publication_status()
        if self.get_unapproved_version is None:
            raise VersioningError,\
                  'There is no unapproved version to request approval for.'

        if not self.is_version_approval_requested():
            raise VersioningError,\
                  'The version is not requested for approval.'
        info = self._get_editable_rfa_info()
        original_requester = info.requester
        info.requester = self.REQUEST.AUTHENTICATED_USER.getUserName()
        info.request_pending=None
        self._set_approval_request_message(message)
        # send message back to requester
        text = "Request for approval was rejected by %s.\nMessage:\n%s" \
               % (info.requester, message)
        self._send_message(info.requester, original_requester,
                           "Approval rejected by editor", text)

    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                              'set_unapproved_version_publication_datetime')
    def set_unapproved_version_publication_datetime(self, dt):
        """Set publication datetime for unapproved, or None for no
        publication at all yet.
        """
        if self._unapproved_version == empty_version:
            raise VersioningError,\
                  'No unapproved version.'
        version_id, publication_datetime, expiration_datetime = \
                    self._unapproved_version
        self._unapproved_version = version_id, dt, expiration_datetime
        self._reindex_version(self._unapproved_version)
        
    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                              'set_unapproved_version_expiration_datetime')
    def set_unapproved_version_expiration_datetime(self, dt):
        """Set expiration datetime, or None for no expiration.
        """
        if self._unapproved_version == empty_version:
            raise VersioningError,\
                  'No unapproved version.'
        version_id, publication_datetime, expiration_datetime = \
                    self._unapproved_version
        self._unapproved_version = version_id, publication_datetime, dt
        self._reindex_version(self._unapproved_version)
        
    security.declareProtected(SilvaPermissions.ApproveSilvaContent,
                              'set_approved_version_publication_datetime')
    def set_approved_version_publication_datetime(self, dt):
        """Set publication datetime for approved.
        """
        if self._approved_version == empty_version:
            raise VersioningError,\
                  'No approved version.'
        if dt is None:
            raise VersioningError,\
                  'Must specify publication datetime.'
        if not dt.isFuture():
            dt = DateTime()
        version_id, publication_datetime, expiration_datetime = \
                    self._approved_version
        self._approved_version = version_id, dt, expiration_datetime
        self._reindex_version(self._approved_version)
        
    security.declareProtected(SilvaPermissions.ApproveSilvaContent,
                              'set_approved_version_expiration_datetime')
    def set_approved_version_expiration_datetime(self, dt):
        """Set expiration datetime, or None for no expiration.
        """
        if self._approved_version == empty_version:
            raise VersioningError,\
                  'No approved version.'
        version_id, publication_datetime, expiration_datetime = \
                    self._approved_version
        self._approved_version = version_id, publication_datetime, dt
        self._reindex_version(self._approved_version)
        
    security.declareProtected(SilvaPermissions.ApproveSilvaContent,
                              'set_next_version_publication_datetime')
    def set_next_version_publication_datetime(self, dt):
        """Set publication datetime of next version.
        """
        if self._approved_version[0]:
            version_id, publication_datetime, expiration_datetime = \
                        self._approved_version
            self._approved_version = version_id, dt, expiration_datetime
            self._reindex_version(self._approved_version)
        elif self._unapproved_version[0]:
            version_id, publication_datetime, expiration_datetime = \
                        self._unapproved_version
            self._unapproved_version = version_id, dt, expiration_datetime
            self._reindex_version(self._unapproved_version)
        else:
            raise VersioningError,\
                  'No next version.'
            
    security.declareProtected(SilvaPermissions.ApproveSilvaContent,
                              'set_next_version_expiration_datetime')
    def set_next_version_expiration_datetime(self, dt):
        """Set expiration datetime of next version.
        """
        if self._approved_version[0]:
            version_id, publication_datetime, expiration_datetime = \
                        self._approved_version
            self._approved_version = version_id, publication_datetime, dt
            self._reindex_version(self._approved_version)
        elif self._unapproved_version[0]:
            version_id, publication_datetime, expiration_datetime = \
                        self._unapproved_version
            self._unapproved_version = version_id, publication_datetime, dt
            self._reindex_version(self._unapproved_version)
        else:
            raise VersioningError,\
                  'No next version.'

    def _set_approval_request_message(self, message):
        """Allows to add a message concerning the
        current request for approval.
        setting the currently approved message
        overwrites any previous message for this content.
        The implementation cleans the message
        if a new version is created.
        """
        # very weak check ... allows to call this method
        # before or after requesting approval, or the like.
        if self.get_next_version() is None:
            raise VersioningError, \
                  "There is no version to add messages for."
        
        info = self._get_editable_rfa_info()
        info.request_messages.append(message)

    
    def _update_publication_status(self):
        now = DateTime()
        # get publication datetime of approved version
        publication_datetime = self._approved_version[1]
        # if it is time make approved version public
        if publication_datetime and now >= publication_datetime:
            if self._public_version != empty_version:
                if not self._previous_versions:
                    self._previous_versions = []
                    last_closed_version = empty_version
                else:
                    last_closed_version = self._previous_versions[-1]
                self._previous_versions.append(self._public_version)
                # unindex version (now last closed)
                self._unindex_version(self._public_version)
            self._public_version = self._approved_version
            self._approved_version = empty_version
            # reindex approved version that is now public
            self._reindex_version(self._public_version)
        # get expiration datetime of public version 
        expiration_datetime = self._public_version[2]
        # expire public version if expiration datetime reached
        if expiration_datetime and now >= expiration_datetime:
            # make sure to add it to the previous versions
            previous_versions = self._previous_versions or []
            if previous_versions:
                last_closed_version = self._previous_versions[-1]
            else:
                last_closed_version = empty_version
            previous_versions.append(self._public_version)
            self._public_version = empty_version
            self._previous_versions = previous_versions
            # reindex last closed and now newly last closed version
            self._unindex_version(last_closed_version)
            
    # ACCESSORS

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'is_version_approved')
    def is_version_approved(self):
        """Check whether version is approved.
        """
        self._update_publication_status()
        return self._approved_version != empty_version

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'is_version_published')
    def is_version_published(self):
        """Check whether version is published.
        """
        self._update_publication_status()
        return self._public_version != empty_version


    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'is_version_approval_requested')
    def is_version_approval_requested(self):
        """Check if there exists an unapproved version
        which has a request for approval.
        """        
        return self._request_for_approval_info.request_pending is not None

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'get_unapproved_version')
    def get_unapproved_version(self, update_status=1):
        """Get the unapproved version.
        """
        if update_status:
            self._update_publication_status()
        return self._unapproved_version[0]

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'get_unapproved_version_publication_datetime')
    def get_unapproved_version_publication_datetime(self, update_status=1):
        """Get publication datetime."""
        if update_status:
            self._update_publication_status()
        return self._unapproved_version[1]

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'get_unapproved_version_expiration_datetime')
    def get_unapproved_version_expiration_datetime(self, update_status=1):
        """Get version datetime."""
        if update_status:
            self._update_publication_status()
        return self._unapproved_version[2]

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'get_approved_version')
    def get_approved_version(self, update_status=1):
        """Get the approved version.
        """
        if update_status:
            self._update_publication_status()
        return self._approved_version[0]

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'get_approved_version_publication_datetime')
    def get_approved_version_publication_datetime(self, update_status=1):
        """Get publication datetime."""
        if update_status:
            self._update_publication_status()
        return self._approved_version[1]

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'get_approved_version_expiration_datetime')
    def get_approved_version_expiration_datetime(self, update_status=1):
        """Get version datetime."""
        if update_status:
            self._update_publication_status()
        return self._approved_version[2]

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'get_next_version')
    def get_next_version(self, update_status=1):
        """Get either approved version if available, or unapproved
        version if not, or None if no next version.
        """
        if update_status:
            self._update_publication_status()
        return self._approved_version[0] or self._unapproved_version[0]

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'get_next_version_publication_datetime')
    def get_next_version_publication_datetime(self, update_status=1):
        """Get publication datetime."""
        if update_status:
            self._update_publication_status()
        return self._approved_version[1] or self._unapproved_version[1]

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'get_next_version_expiration_datetime')
    def get_next_version_expiration_datetime(self, update_status=1):
        """Get version datetime."""
        if update_status:
            self._update_publication_status()
        return self._approved_version[2] or self._unapproved_version[2]

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'get_next_version_status')
    def get_next_version_status(self):
        """Get status of next version.
        """
        if self.get_unapproved_version() is not None:
            if self.is_version_approval_requested():
                return "request_pending"
            else:
                return "not_approved"
        elif self.get_approved_version() is not None:
            return "approved"
        else:
            return "no_next_version"

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'get_public_version')
    def get_public_version(self, update_status=1):
        """Get the public version.
        """
        if update_status:
            self._update_publication_status()
        return self._public_version[0]

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'get_public_version_publication_datetime')
    def get_public_version_publication_datetime(self, update_status=1):
        """Get publication datetime."""
        if update_status:
            self._update_publication_status()
        return self._public_version[1]

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'get_public_version_expiration_datetime')
    def get_public_version_expiration_datetime(self, update_status=1):
        """Get version datetime."""
        if update_status:
            self._update_publication_status()
        return self._public_version[2]

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'get_public_version_status')
    def get_public_version_status(self):
        if self.get_public_version() is not None:
            return "published"
        elif self.get_previous_versions():
            return "closed"
        else:
            return "no_public_version"

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'get_previous_versions')
    def get_previous_versions(self):
        """Get list of previous versions, index 0 most recent.
        """
        if self._previous_versions is None:
            return []
        else:
            return [version[0] for version in self._previous_versions]
        
    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'get_last_closed_version')
    def get_last_closed_version(self, update_status=1):
        """Get the last closed version or None if no such thing.
        """
        if update_status:
            self._update_publication_status()
        versions = self.get_previous_versions()
        if len(versions) < 1:
            return None
        else:
            return versions[-1]

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'get_approval_requester')
    def get_approval_requester(self):
        """Return the id of the user requesting approval
        of the currently unapproved version."""
        return self._request_for_approval_info.requester

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'get_approval_requester')
    def get_approval_request_message(self):
        """Get the current message associated with
        request for approval; i.e. argument passed as message
        on the last change to the approval status
        ({request,withdraw,reject}_version_approval, or approve_version)
        May be None, if there is currently no such message.
        """
        messages = self._request_for_approval_info.request_messages
        if len(messages)==0:
            return None
        else:
            return messages[-1]

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'get_approval_requester')
    def get_approval_request_datetime(self):
        """Get the date when the currently unapproved version
        did get a request for approval as a DateTime object,
        or None if there is no such version or request.
        """
        return self._request_for_approval_info.request_date

    def _send_message_to_editors(self, from_userid, subject, text):
        service_messages = getattr(self, 'service_messages', None)
        if service_messages is None:
            return
        # find out some information about the object and add it to the
        # message
        text = "Object: %s\n%s/edit/tab_preview\n%s" % (
            self.get_title_editable(),
            self.absolute_url(), text)
        # XXX this may not get the right people, but what does?
        for userid in self.sec_get_nearest_of_role('ChiefEditor'):
            if userid==from_userid:
                continue
            service_messages.send_message(
                from_userid, userid, subject, text)

    def _send_message(self, from_userid, to_userid, subject, text):
        service_messages = getattr(self, 'service_messages', None)
        if service_messages is None:
            return
        if from_userid==to_userid:
            return
        # find out some information about the object and add it to the
        # message
        text = "Object: %s\n%s/edit/tab_preview\n%s" % (
            self.get_title_editable(),
            self.absolute_url(), text)
        service_messages.send_message(from_userid, to_userid, subject, text)

    def _index_version(self, version):
        pass
        
    def _reindex_version(self, version):
        pass

    def _unindex_version(self, version):
        pass


def _format_date_helper(date):
    # XXX cut & paste from service_utils/backend_datetime_to_str
    return "%02d %s %04d %02d:%02d" % \
           (date.day(), date.aMonth().lower(), date.year(),
            date.hour(), date.minute() )


InitializeClass(Versioning)



