from Products.SilvaDocument.Document import manage_addDocument
from Products.Silva.Ghost import manage_addGhost
from Products.Silva.GhostFolder import manage_addGhostFolder
from Products.Silva.Folder import manage_addFolder
from Products.Silva.silvaxml.xmlimport import BaseHandler
from Products.Silva.Link import Link
from Products.ParsedXML.ParsedXML import ParsedXML
from Products.Silva import mangle

NS_URI = 'http://infrae.com/ns/silva/0.5'

class SilvaHandler(BaseHandler):
    pass

class FolderHandler(BaseHandler):
    def startElementNS(self, name, qname, attrs):
        if name == (NS_URI, 'folder'):
            id = str(attrs[(None, 'id')])
            self._parent.manage_addProduct['Silva'].manage_addFolder(
                id, '')
            self._result = getattr(self._parent, id)
                
    def endElementNS(self, name, qname):
        if name == (NS_URI, 'folder'):
            self._result.set_title(
                self._metadata['silva-content']['maintitle']
                )
            self.storeMetadata()
                
class VersionHandler(BaseHandler):
    def getOverrides(self):
        return {
            (NS_URI, 'status'): StatusHandler,
            (NS_URI, 'publication_datetime'): PublicationDateTimeHandler,
            (NS_URI, 'expiration_datetime'): ExpirationDateTimeHandler
            }

    def startElementNS(self, name, qname, attrs):
        if name == (NS_URI, 'version'):
            self._id = attrs[(None, 'id')]

    def endElementNS(self, name, qname):
        status = self.getData('status')
        if status == 'unapproved':
            self._parent._unapproved_version = (
                self._id,
                self.getData('publication_datetime'),
                self.getData('expiration_datetime')
                )
        elif status == 'approved':
            self._parent._approved_version = (
                self._id,
                self.getData('publication_datetime'),
                self.getData('expiration_datetime')
                )
        elif status == 'public':
            self._parent._public_version = (
                self._id,
                self.getData('publication_datetime'),
                self.getData('expiration_datetime')
                )
        else:
            previous_versions = self._parent._previous_versions or []
            previous_version = (
                self._id,
                self.getData('publication_datetime'),
                self.getData('expiration_datetime')
                )
            previous_versions.append(previous_version)
            self._parent._previous_versions = previous_versions

class SetHandler(BaseHandler):
    def __init__(self, parent, parent_handler, options={}):
        BaseHandler.__init__(self, parent, parent_handler, options)
        self._metadata_key = None
        
    def startElementNS(self, name, qname, attrs):
        if name == (NS_URI, 'set'):
            self._metadata_set = attrs[(None, 'id')]
            self._parent_handler._metadata[self._metadata_set] = {}
        else:
            # XXX do something other than ignore the namespace
            namespace, self._metadata_key = name
            
    def characters(self, chrs):
        if self._metadata_key is not None:
            self._parent_handler._metadata[
                 self._metadata_set][self._metadata_key] = chrs
        
    def endElementNS(self, name, qname):
        self._metadata_key = None
        
class GhostHandler(BaseHandler):
    def getOverrides(self):
        return {
            (NS_URI, 'content'): GhostContentHandler
            }

    def startElementNS(self, name, qname, attrs):
        if name == (NS_URI, 'ghost'):
            ghost_object = Ghost(attrs[(None, 'id')])
            self._parent.addItem(ghost_object)
            self._result = ghost_object

class GhostContentHandler(BaseHandler):
    def startElementNS(self, name, qname, attrs):
        if name == (NS_URI, 'content'):
            if attrs.has_key((None, 'version_id')):
                id = attrs[(None, 'version_id')]
                version = GhostContent(id)
                self._parent.addVersion(version)
                self._result = version

    def endElementNS(self, name, qname):
        if name == (NS_URI, 'ghost'):
            for key in self._metadata.keys():
                self._result.addMetadata(key, self.getMetadata(key))

class LinkHandler(BaseHandler):
    def getOverrides(self):
        return {
            (NS_URI, 'content'): LinkContentHandler
            }

    def startElementNS(self, name, qname, attrs):
        if name == (NS_URI, 'link'):
            id = attrs[(None, 'id')].encode('utf-8')
            if not mangle.Id(self._parent, id).isValid():
                return
            object = Link(id)
            self._parent._setObject(id, object)
            self._result = getattr(self._parent, id)
        
class LinkContentHandler(BaseHandler):
    def getOverrides(self):
        return {
            (NS_URI, 'url'): URLHandler
            }

    def startElementNS(self, name, qname, attrs):
        if name == (NS_URI, 'content'):
            id = attrs[(None, 'version_id')].encode('utf-8')
            self._parent.manage_addProduct['Silva'].manage_addLinkVersion(
                id, '', '')
            self._result = getattr(self._parent, id)

    def endElementNS(self, name, qname):
        if name == (NS_URI, 'content'):
            self._result.set_url(self.getData('url'))
            self._result.set_title(
                self._metadata['silva-content']['maintitle'])

class StatusHandler(BaseHandler):
    def characters(self, chrs):
        self._parent_handler.setData('status', chrs)

class PublicationDateTimeHandler(BaseHandler):
    def characters(self, chrs):
        self._parent_handler.setData('publication_datetime', chrs)

class ExpirationDateTimeHandler(BaseHandler):
    def characters(self, chrs):
        self._parent_handler.setData('expiration_datetime', chrs)

class URLHandler(BaseHandler):
    def characters(self, chrs):
        self._parent_handler.setData('url', chrs)

