# Zope
from OFS import SimpleItem
from AccessControl import ClassSecurityInfo
from Globals import InitializeClass
from Products.PageTemplates.PageTemplateFile import PageTemplateFile
from DateTime import DateTime
# Silva
from VersionedContent import VersionedContent
import Interfaces
import SilvaPermissions
# misc
from helpers import add_and_edit
import urlparse

class Ghost(VersionedContent):
    """Ghost object.
    """
    
    security = ClassSecurityInfo()

    meta_type = "Silva Ghost"

    __implements__ = Interfaces.VersionedContent
    
    def __init__(self, id):
        Ghost.inheritedAttribute('__init__')(self, id, 'No title for ghost')
        
    def set_title(self):
        # FIXME: what to do here?
        pass
    
    def get_title(self):
        """Get title.
        """
        return "Dummy ghost title" 
        ghost_version = self.get_viewable()
        if ghost_version is None:
            return 'Ghost is unpublished'
        content = ghost_version._get_content()
        if content is None:
            return "Ghost target is broken"
        else:
            return content.get_title()

    security.declareProtected(SilvaPermissions.ApproveSilvaContent,
                              'to_xml')
    def to_xml(self, f):
        version_id = self.get_public_version()
        if version_id is None:
            return
        version = getattr(self, version_id)
        content = version._get_content()
        if content is None:
            return
        content.to_xml(f)
        
InitializeClass(Ghost)

class GhostVersion(SimpleItem.SimpleItem):
    """Ghost version.
    """
    
    meta_type = 'Silva Ghost Version'
    
    def __init__(self, id, content_url):
        self.id = id
        self._content_url = content_url

    def set_content_url(self, content_url):
        """Set content url.
        """
        # FIXME: should never ever be allowed to point to a ghost
        # or a container - do a lot of tests

        # simplify url
        scheme, netloc, path, parameters, query, fragment = \
                urlparse.urlparse(content_url)
        steps = path.split('/')
        
        #if steps[1] == 'silva':
        #    steps = steps[2:]
        if len(steps) >= 2 and steps[-2] == 'edit':
            steps = steps[:-2]
        content_url = '/'.join(steps)
        self._content_url = content_url
        
    def get_content_url(self):
        """Get content url.
        """
        return self._content_url

    def _get_content(self):
        """Get the real content object.
        """
        # FIXME: what if we're pointing to something that cannot be viewed publically?
        if self._content_url is None:
            return None
        try:
            content = self.getPhysicalRoot().unrestrictedTraverse(self._content_url)
            if not Interfaces.VersionedContent.isImplementedBy(content) or content.meta_type == 'Silva Ghost':
                return None
            else:
                return content
        # FIXME: should this be a bare exception? should catch all traversal failures..
        except:
            return None
        
    def render(self):
        """Render this version (which is what we point at)
        """
        # FIXME: should only call view if we are allowed to by content
        # FIXME what if content is None?
        # what if we get circular ghosts?
        content = self._get_content()
        if content is None:
            return None # public render code of ghost should give broken message
        else:
            return content.view()
    
manage_addGhostForm = PageTemplateFile("www/ghostAdd", globals(),
                                       __name__='manage_addGhostForm')

def manage_addGhost(self, id, content_url, REQUEST=None):
    """Add a Ghost."""
    if not self.is_id_valid(id):
        return
    object = Ghost(id)
    self._setObject(id, object)
    object = getattr(self, id)
    # add first version
    object._setObject('0', GhostVersion('0', content_url))
    object.create_version('0', None, None)
    add_and_edit(self, id, REQUEST)
    return ''

manage_addGhostVersionForm = PageTemplateFile("www/ghostversionAdd", globals(),
                                              __name__='manage_addGhostVersionForm')

def manage_addGhostVersion(self, id, content_url, REQUEST=None):
    """Add a Ghost version."""
    object = GhostVersion(id, content_url)
    self._setObject(id, object)
    add_and_edit(self, id, REQUEST)
    return ''
