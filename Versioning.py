from DateTime import DateTime
import Interfaces
from AccessControl import ClassSecurityInfo
from Globals import InitializeClass
import SilvaPermissions

class VersioningError(Exception):
    pass

empty_version = (None, None, None)

class Versioning:
    """Mixin baseclass to make object contents versioned.
    """
    security = ClassSecurityInfo()

    __implements__ = Interfaces.Versioning
    
    _unapproved_version = empty_version
    _approved_version = empty_version
    _public_version = empty_version
    _previous_versions = None
       
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
        if Interfaces.Publishable.isImplementedBy(self):
            if not self.can_approve():
                raise VersioningError,\
                      'Cannot approve version; not allowed.'
        self._approved_version = self._unapproved_version
        self._unapproved_version = empty_version

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
                   'approved version %s exists at the same time.') % (self._unapproved_version[0],
                                                                      self._approved_version[0])        
        self._unapproved_version = self._approved_version
        self._approved_version = empty_version

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
        previous_versions.append(self._public_version)
        self._public_version = empty_version
        self._previous_versions = previous_versions

    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                              'set_unapproved_version_publication_datetime')
    def set_unapproved_version_publication_datetime(self, dt):
        """Set publication datetime for unapproved, or None for no
        publication at all yet.
        """
        if self._unapproved_version == empty_version:
            raise VersioningError,\
                  'No unapproved version.'
        version_id, publication_datetime, expiration_datetime = self._unapproved_version
        self._unapproved_version = version_id, dt, expiration_datetime

    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                              'set_unapproved_version_expiration_datetime')
    def set_unapproved_version_expiration_datetime(self, dt):
        """Set expiration datetime, or None for no expiration.
        """
        if self._unapproved_version == empty_version:
            raise VersioningError,\
                  'No unapproved version.'
        version_id, publication_datetime, expiration_datetime = self._unapproved_version
        self._unapproved_version = version_id, publication_datetime, dt

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
        version_id, publication_datetime, expiration_datetime = self._approved_version
        self._approved_version = version_id, dt, expiration_datetime

    security.declareProtected(SilvaPermissions.ApproveSilvaContent,
                              'set_approved_version_expiration_datetime')
    def set_approved_version_expiration_datetime(self, dt):
        """Set expiration datetime, or None for no expiration.
        """
        if self._approved_version == empty_version:
            raise VersioningError,\
                  'No approved version.'
        version_id, publication_datetime, expiration_datetime = self._approved_version
        self._approved_version = version_id, publication_datetime, dt

    security.declareProtected(SilvaPermissions.ApproveSilvaContent,
                              'set_next_version_publication_datetime')
    def set_next_version_publication_datetime(self, dt):
        """Set publication datetime of next version.
        """
        if self._approved_version[0]:
            version_id, publication_datetime, expiration_datetime = self._approved_version
            self._approved_version = version_id, dt, expiration_datetime
        elif self._unapproved_version[0]:
            version_id, publication_datetime, expiration_datetime = self._unapproved_version
            self._unapproved_version = version_id, dt, expiration_datetime
        else:
            raise VersioningError,\
                  'No next version.'

    security.declareProtected(SilvaPermissions.ApproveSilvaContent,
                              'set_next_version_expiration_datetime')
    def set_next_version_expiration_datetime(self, dt):
        """Set expiration datetime of next version.
        """
        if self._approved_version[0]:
            version_id, publication_datetime, expiration_datetime = self._approved_version
            self._approved_version = version_id, publication_datetime, dt
        elif self._unapproved_version[0]:
            version_id, publication_datetime, expiration_datetime = self._unapproved_version
            self._unapproved_version = version_id, publication_datetime, dt
        else:
            raise VersioningError,\
                  'No next version.'
        
    def _update_publication_status(self):
        now = DateTime()
        # get publication datetime of approved version
        publication_datetime = self._approved_version[1]
        # if it is time make approved version public
        if publication_datetime and now >= publication_datetime:
            self._public_version = self._approved_version
            self._approved_version = empty_version
        # get expiration datetime of public version 
        expiration_datetime = self._public_version[2]
        # expire public version if expiration datetime reached
        if expiration_datetime and now >= expiration_datetime:
            # make sure to add it to the previous versions
            previous_versions = self._previous_versions or []
            previous_versions.append(self._public_version)
            self._public_version = empty_version
            self._previous_versions = previous_versions
            
    # ACCESSORS

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'is_version_approved')
    def is_version_approved(self):
        """Check whether version is approved.
        """
        self._update_publication_status()
        return self._approved_version != empty_version

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'is_version_published')
    def is_version_published(self):
        """Check whether version is published.
        """
        self._update_publication_status()
        return self._public_version != empty_version

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'get_unapproved_version')
    def get_unapproved_version(self):
        """Get the unapproved version.
        """
        self._update_publication_status()
        return self._unapproved_version[0]

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'get_unapproved_version_publication_datetime')
    def get_unapproved_version_publication_datetime(self):
        """Get publication datetime."""
        self._update_publication_status()
        return self._unapproved_version[1]

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'get_unapproved_version_expiration_datetime')
    def get_unapproved_version_expiration_datetime(self):
        """Get version datetime."""
        self._update_publication_status()
        return self._unapproved_version[2]

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'get_approved_version')
    def get_approved_version(self):
        """Get the approved version.
        """
        self._update_publication_status()
        return self._approved_version[0]

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'get_approved_version_publication_datetime')
    def get_approved_version_publication_datetime(self):
        """Get publication datetime."""
        self._update_publication_status()
        return self._approved_version[1]

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'get_approved_version_expiration_datetime')
    def get_approved_version_expiration_datetime(self):
        """Get version datetime."""
        self._update_publication_status()
        return self._approved_version[2]

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'get_next_version')
    def get_next_version(self):
        """Get either approved version if available, or unapproved
        version if not, or None if no next version.
        """
        self._update_publication_status()
        return self._approved_version[0] or self._unapproved_version[0]

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'get_next_version_publication_datetime')
    def get_next_version_publication_datetime(self):
        """Get publication datetime."""
        self._update_publication_status()
        return self._approved_version[1] or self._unapproved_version[1]

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'get_next_version_expiration_datetime')
    def get_next_version_expiration_datetime(self):
        """Get version datetime."""
        self._update_publication_status()
        return self._approved_version[2] or self._unapproved_version[2]

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'get_next_version_status')
    def get_next_version_status(self):
        """Get status of next version.
        """
        if self.get_unapproved_version() is not None:
            return "not_approved"
        elif self.get_approved_version() is not None:
            return "approved"
        else:
            return "no_next_version"

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'get_public_version')
    def get_public_version(self):
        """Get the public version.
        """
        self._update_publication_status()
        return self._public_version[0]

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'get_public_version_publication_datetime')
    def get_public_version_publication_datetime(self):
        """Get publication datetime."""
        self._update_publication_status()
        return self._public_version[1]

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'get_public_version_expiration_datetime')
    def get_public_version_expiration_datetime(self):
        """Get version datetime."""
        self._update_publication_status()
        return self._public_version[2]

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
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
    def get_last_closed_version(self):
        """Get the last closed version or None if no such thing.
        """
        versions = self.get_previous_versions()
        if len(versions) < 1:
            return None
        else:
            return versions[-1]
        
InitializeClass(Versioning)
