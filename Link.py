# Zope
from AccessControl import ClassSecurityInfo
from Globals import InitializeClass
from Products.PageTemplates.PageTemplateFile import PageTemplateFile

# Silva
from VersionedContent import CatalogedVersionedContent
from Version import CatalogedVersion
import SilvaPermissions
from interfaces import IVersionedContent, IVersion
import mangle
from helpers import add_and_edit
from Products.Silva.ImporterRegistry import get_xml_id, get_xml_title
from Products.Silva.Metadata import export_metadata

icon = "www/link.png"

class Link(CatalogedVersionedContent):
    """A Link makes it possible to include links to external sites &#8211; 
       outside of Silva &#8211; in a Table of Contents. The content of a Link 
       is simply a hyperlink, beginning with &#8220;http://....&#8221;.
    """
    security = ClassSecurityInfo()

    meta_type = "Silva Link"

    __implements__ = IVersionedContent

    def __init__(self, id):
        Link.inheritedAttribute('__init__')(self, id)
        self.id = id

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'to_xml')
    def to_xml(self, context):
        """Render object to XML.
        """
        f = context.f

        if context.last_version == 1:
            version_id = self.get_next_version()
            if version_id is None:
                version_id = self.get_public_version()
        else:
            version_id = self.get_public_version()

        if version_id is None:
            return
            
        version = getattr(self, version_id)
        f.write('<silva_link id="%s">' % self.id)
        f.write('<title>%s</title>' % version.get_title())
        f.write('<url>%s</url>' % version.get_url())
        export_metadata(version, context)
        f.write('</silva_link>')

InitializeClass(Link)

manage_addLinkForm = PageTemplateFile("www/linkAdd", globals(),
                                       __name__='manage_addLinkForm')
 
def manage_addLink(self, id, title, url, REQUEST=None):
    """Add a Link."""
    if not mangle.Id(self, id).isValid():
        return
    object = Link(id)
    self._setObject(id, object)
    object = getattr(self, id)
    # add first version
    object.manage_addProduct['Silva'].manage_addLinkVersion(
        '0', title, url)
    object.create_version('0', None, None)
    add_and_edit(self, id, REQUEST)
    return ''

class LinkVersion(CatalogedVersion):
    security = ClassSecurityInfo()
    
    meta_type = "Silva Link Version"

    __implements__ = IVersion

    def __init__(self, id, url):
        LinkVersion.inheritedAttribute('__init__')(self,
                                                   id, 'not the real title')
        self.set_url(url)

    security.declareProtected(SilvaPermissions.ChangeSilvaContent, 'get_url')
    def get_url(self):
        return self._url

    security.declareProtected(SilvaPermissions.View, 'redirect')
    def redirect(self, view_type='public'):
        request = self.REQUEST
        response = request.RESPONSE
       
        if (request['HTTP_USER_AGENT'].startswith('Mozilla/4.77') or
            request['HTTP_USER_AGENT'].find('Konqueror') > -1 or
            request['HTTP_USER_AGENT'].find('Opera') > -1):
            return ('<html><head><META HTTP-EQUIV="refresh" '
                    'CONTENT="0; URL=%s"></head><body bgcolor="#FFFFFF">'
                    '</body></html>') % self._url
        else:
            response.redirect(self._url)
            return ""
        
    # MANIPULATORS
    security.declareProtected(SilvaPermissions.ChangeSilvaContent, 'set_url')
    def set_url(self, url):
        """Set the link to the given URL.

        If the link does *not* start with something that looks
        like a schema (^.*://.*), HTTP is assumed.
        """
        u = url.lower()
        p = u.find('://')
        schema = u[:p]
        if p < 0:
            # prepend http schema
            url = 'http://' + url
        self._url = url

InitializeClass(LinkVersion)

manage_addLinkVersionForm = PageTemplateFile(
    "www/linkversionAdd", globals(),
    __name__='manage_addLinkVersionForm')
                                                                                
def manage_addLinkVersion(self, id, title, url, REQUEST=None):
    """Add a Link version."""
    object = LinkVersion(id, url)
    self._setObject(id, object)
    self._getOb(id).set_title(title)
    add_and_edit(self, id, REQUEST)
    return ''

def xml_import_handler(object, node):
    id = get_xml_id(node)
    title = get_xml_title(node)
    url = ''
    for child in node.childNodes:
        if child.nodeName == u'url':
            url = child.childNodes[0].nodeValue;
   
    id = str(mangle.Id(object, id).unique())
    object.manage_addProduct['Silva'].manage_addLink(id, title, url)
    
    newdoc = getattr(object, id)
    newdoc.sec_update_last_author_info()
    
    return newdoc

