import sys, string
from StringIO import StringIO
from sprout.saxext import xmlimport
from Products.Silva.Ghost import Ghost, GhostVersion
from Products.Silva.GhostFolder import manage_addGhostFolder, GhostFolder
from Products.Silva.Folder import manage_addFolder
from Products.Silva.Publication import manage_addPublication
from Products.Silva.Link import Link, LinkVersion
from Products.Silva import mangle
from DateTime import DateTime

NS_URI = 'http://infrae.com/ns/silva'

theXMLImporter = xmlimport.Importer()

def initializeXMLImportRegistry():
    """Initialize the global importer object.
    """
    importer = theXMLImporter
    importer.registerHandler((NS_URI, 'silva'), SilvaExportRootHandler)
    importer.registerHandler((NS_URI, 'folder'), FolderHandler)
    importer.registerHandler((NS_URI, 'link'), LinkHandler)
    importer.registerHandler((NS_URI, 'ghost'), GhostHandler)
    importer.registerHandler((NS_URI, 'ghost_folder'), GhostFolderHandler)
    importer.registerHandler((NS_URI, 'publication'), PublicationHandler)
    importer.registerHandler((NS_URI, 'version'), VersionHandler)
    importer.registerHandler((NS_URI, 'set'), SetHandler)
    importer.registerHandler((NS_URI, 'file_asset'), FileHandler)
    importer.registerHandler((NS_URI, 'image_asset'), ImageHandler)
    importer.registerHandler((NS_URI, 'auto_toc'), AutoTOCHandler)
    importer.registerHandler(
        (NS_URI, 'unknown_content'),
        UnknownContentHandler)
    
class SilvaBaseHandler(xmlimport.BaseHandler):
    def __init__(self, parent, parent_handler, settings=None, info=None):
        xmlimport.BaseHandler.__init__(
            self,
            parent,
            parent_handler,
            settings,
            info
            )
        self._metadata_set = None
        self._info = info
        self._metadata_key = None
        self._metadata_type = None
        self._metadata = {}
        self._workflow = {}
        
    def setMetadata(self, set, key, value, value_type=None):
        if value_type == 'datetime' and value:
            value = DateTime(value)
        self._metadata[set][key] = value

    def setWorkflowVersion(
        self, version_id, publicationtime, expirationtime, status):
        if publicationtime:
            publicationtime = DateTime(publicationtime)
        if expirationtime:
            expirationtime = DateTime(expirationtime)
            
        self._parent_handler._workflow[version_id] = (
            publicationtime, expirationtime, status)
        
    def getMetadata(self, set, key):
        return self._metadata[set][key]

    def getWorkflowVersion(self, version_id):
        return self._parent_handler._workflow[version_id]

    def setMetadataSet(self, set):
        self._metadata_set = set
        self._metadata[set] = {}
        
    def metadataSet(self):
        return self._metadata_set

    def setMetadataType(self, value_type):
        self._metadata_type = value_type
        
    def metadataType(self):
        return self._metadata_type

    def setMetadataKey(self, key):
        self._metadata_key = key
        
    def metadataKey(self):
        return self._metadata_key
    
    def setWorkflowVersion(
        self, version_id, publicationtime, expirationtime, status):
        if publicationtime:
            publicationtime = DateTime(publicationtime)
        if expirationtime:
            expirationtime = DateTime(expirationtime)
            
        self.parentHandler()._workflow[version_id] = (
            publicationtime, expirationtime, status)
    
    def storeMetadata(self):
        content = self._result
        metadata_service = content.service_metadata
        metadata = {}
        binding = metadata_service.getMetadata(content)
        if binding is not None:
            for set_name in binding.collection.keys():
                set = binding.collection[set_name]
                element_names = self._metadata[set.id].keys()
                # Set data
                errors = binding._setData(
                    namespace_key=set.metadata_uri,
                    data=self._metadata[set.id],
                    reindex=1
                    )

                if errors:
                    raise ValidationError(
                        "%s %s" % (str(content.getPhysicalPath()),str(errors)))

    def storeWorkflow(self):
        content = self._result
        version_id = content.id
        publicationtime, expirationtime, status = self.getWorkflowVersion(
            version_id)
        if status == 'unapproved':
            self.parent()._unapproved_version = (
                version_id,
                publicationtime,
                expirationtime
                )
        elif status == 'approved':
            self.parent()._approved_version = (
                version_id,
                publicationtime,
                expirationtime
                )
        elif status == 'public':
            self.parent()._public_version = (
                version_id,
                publicationtime,
                expirationtime
                )
        else:
            previous_versions = self.parent()._previous_versions or []
            previous_version = (
                version_id,
                publicationtime,
                expirationtime
                )
            previous_versions.append(previous_version)
            self.parent()._previous_versions = previous_versions
                    
    def setMaintitle(self):
        main_title = self.getMetadata('silva-content', 'maintitle')
        if main_title is not None:
            self.result().set_title(main_title)

    def syncGhostfolders(self):
        syncTargets = self._info.getSyncTargets()
        if syncTargets:
            # pop() doesn't seem to work here
            for folder in syncTargets:
                folder.haunt()
                syncTargets.remove(folder)

class SilvaExportRootHandler(SilvaBaseHandler):
    pass

class FolderHandler(SilvaBaseHandler):
    def startElementNS(self, name, qname, attrs):
        if name == (NS_URI, 'folder'):
            id = attrs[(None, 'id')].encode('utf-8')
            uid = generateUniqueId(id, self.parent())
            self.parent().manage_addProduct['Silva'].manage_addFolder(
                uid, '', create_default=0)
            self.setResult(getattr(self.parent(), uid))
                
    def endElementNS(self, name, qname):
        if name == (NS_URI, 'folder'):

            self.setMaintitle()
            self.storeMetadata()
            self.syncGhostfolders()

class PublicationHandler(SilvaBaseHandler):
    def startElementNS(self, name, qname, attrs):
        if name == (NS_URI, 'publication'):
            id = str(attrs[(None, 'id')])
            uid = generateUniqueId(id, self.parent())
            self.parent().manage_addProduct['Silva'].manage_addPublication(
                uid, '', create_default=0)
            self.setResult(getattr(self.parent(), uid))
                
    def endElementNS(self, name, qname):
        if name == (NS_URI, 'publication'):
            self.setMaintitle()
            self.storeMetadata()
            self.sync_ghostfolders()

class AutoTOCHandler(SilvaBaseHandler):
    def startElementNS(self, name, qname, attrs):
        if name == (NS_URI, 'auto_toc'):
            id = str(attrs[(None, 'id')])
            uid = generateUniqueId(id, self.parent())
            self.parent().manage_addProduct['Silva'].manage_addAutoTOC(
                uid, '')
            self.setResult(getattr(self.parent(), uid))
            
    def endElementNS(self, name, qname):
        if name == (NS_URI, 'auto_toc'):
            self.setMaintitle()
            self.storeMetadata()
            
class VersionHandler(SilvaBaseHandler):
    def getOverrides(self):
        return {
            (NS_URI, 'status'): StatusHandler,
            (NS_URI, 'publication_datetime'): PublicationDateTimeHandler,
            (NS_URI, 'expiration_datetime'): ExpirationDateTimeHandler
            }

    def startElementNS(self, name, qname, attrs):
        if name == (NS_URI, 'version'):
            self.setData('id', attrs[(None, 'id')])

    def endElementNS(self, name, qname):
        self.setWorkflowVersion(
            self.getData('id'),
            self.getData('publication_datetime'),
            self.getData('expiration_datetime'),
            self.getData('status'))

class SetHandler(SilvaBaseHandler):
    def startElementNS(self, name, qname, attrs):
        if name == (NS_URI, 'set'):
            self.parentHandler().setMetadataSet(attrs[(None, 'id')])
        else:
            self.parentHandler().setMetadataKey(name[1])
            if attrs.has_key((None, 'type')):
                self.parentHandler().setMetadataType(attrs[(None, 'type')])
            else:
                self.parentHandler().setMetadataType(None)
        self.setResult(None)
            
    def characters(self, chrs):
        self._chars = chrs
       
    def endElementNS(self, name, qname):
        value = getattr(self, '_chars', None)

        if self.parentHandler().metadataKey() is not None:
             self.parentHandler().setMetadata(
             self.parentHandler().metadataSet(),
             self.parentHandler().metadataKey(),
             value,
             self.parentHandler().metadataType())

        self.parentHandler().setMetadataKey(None)
        self.parentHandler().setMetadataType(None)
        self._chars = None
        
class GhostHandler(SilvaBaseHandler):
    def getOverrides(self):
        return {
            (NS_URI, 'content'): GhostContentHandler
            }

    def startElementNS(self, name, qname, attrs):
        if name == (NS_URI, 'ghost'):
            id = attrs[(None, 'id')].encode('utf-8')
            uid = generateUniqueId(id, self.parent())
            object = Ghost(uid)
            self.parent()._setObject(id, object)
            object = getattr(self.parent(), uid)
            self.setResult(object)

class GhostContentHandler(SilvaBaseHandler):
    def getOverrides(self):
        return {
            (NS_URI, 'haunted_url'): HauntedUrlHandler,
            (NS_URI, 'content'): NoopHandler,
            }

    def startElementNS(self, name, qname, attrs):
        if name == (NS_URI, 'content'):
            if attrs.has_key((None, 'version_id')):
                id = attrs[(None, 'version_id')].encode('utf8')
                self.parent()._setObject(id, GhostVersion(id))
                version = getattr(self.parent(), id)
                self.setResult(version)

    def endElementNS(self, name, qname):
        if name == (NS_URI, 'content'):
            self.storeWorkflow()
            updateVersionCount(self)

class GhostFolderHandler(SilvaBaseHandler):
    def getOverrides(self):
        return {
            (NS_URI, 'haunted_url'): HauntedUrlHandler,
            (NS_URI, 'content'): NoopHandler,
            }

    def startElementNS(self, name, qname, attrs):
        if name == (NS_URI, 'ghost_folder'):
            id = attrs[(None, 'id')].encode('utf-8')
            uid = generateUniqueId(id, self.parent())
            object = GhostFolder(uid)
            self.parent()._setObject(id, object)
            object = getattr(self.parent(), uid)
            self.setResult(object)
            self._info.addSyncTarget(object)

    def endElementNS(self, name, qname):
        if name == (NS_URI, 'content'):
            self.storeWorkflow()
            updateVersionCount(self)

class HauntedUrlHandler(SilvaBaseHandler):
    def characters(self, chars):
        self.parent().set_haunted_url(chars)

class NoopHandler(SilvaBaseHandler):
    def startElementNS(self, name, qname, attrs):
        pass

    def endElementNS(self, name, qname):
        pass

class LinkHandler(SilvaBaseHandler):
    def getOverrides(self):
        return {
                (NS_URI, 'content'): LinkContentHandler
            }

    def startElementNS(self, name, qname, attrs):
        if name == (NS_URI, 'link'):
            id = attrs[(None, 'id')].encode('utf-8')
            uid = generateUniqueId(id, self.parent())
            object = Link(uid)
            self.parent()._setObject(uid, object)
            self.setResult(getattr(self.parent(), uid))
        
class LinkContentHandler(SilvaBaseHandler):
    def getOverrides(self):
        return {
            (NS_URI, 'url'): URLHandler
            }

    def startElementNS(self, name, qname, attrs):
        if name == (NS_URI, 'content'):
            id = attrs[(None, 'version_id')].encode('utf-8')
            if not mangle.Id(self.parent(), id).isValid():
                return
            version = LinkVersion(id, '')
            self.parent()._setObject(id, version)
            self.setResult(getattr(self.parent(), id))
            updateVersionCount(self)
            
    def endElementNS(self, name, qname):
        if name == (NS_URI, 'content'):
            self.result().set_url(self.getData('url'))
            self.setMaintitle()
            self.storeMetadata()
            self.storeWorkflow()

class ImageHandler(SilvaBaseHandler):
    def getOverrides(self):
        return {
            (NS_URI, 'asset_id'): ZipIdHandler
            }
        
    def startElementNS(self, name, qname, attrs):
        if name == (NS_URI, 'image_asset'):
            self.setData('id', attrs[(None, 'id')])

    def endElementNS(self, name, qname):
        if name == (NS_URI, 'image_asset'):
            id = self.getData('id')
            info = self.getInfo()
            file = StringIO(
                info.ZipFile().read(
                    'assets/' + self.getData('zip_id')))
            self.parent().manage_addProduct['Silva'].manage_addImage(id, '', file)
            
class FileHandler(SilvaBaseHandler):
    def getOverrides(self):
        return {
            (NS_URI, 'asset_id'): ZipIdHandler
            }

    def startElementNS(self, name, qname, attrs):
        if name == (NS_URI, 'file_asset'):
            self.setData('id', attrs[(None, 'id')])

    def endElementNS(self, name, qname):
        if name == (NS_URI, 'file_asset'):
            id = self.getData('id')
            info = self.getInfo()
            file = StringIO(
                info.ZipFile().read(
                    'assets/' + self.getData('zip_id')))
            self.parent().manage_addProduct['Silva'].manage_addFile(id, '', file)
            
class UnknownContentHandler(SilvaBaseHandler):
    def getOverrides(self):
        return {
            (NS_URI, 'zexp_id'): ZipIdHandler
            }

    def endElementNS(self, name, qname):
        if name == (NS_URI, 'unknown_content'):
            info = self.getInfo()
            file = StringIO(
                info.ZipFile().read(
                    'zexps/' + self.getData('zip_id')))
            get_transaction().commit(1)
            ob = self.parent()._p_jar.importFile(file)
            id=ob.id
            if hasattr(id, 'im_func'):
                id=id()
            self.parent()._setObject(id, ob)
        
class ZipIdHandler(SilvaBaseHandler):
    def characters(self, chrs):
        self.parentHandler().setData('zip_id', chrs)
    
class StatusHandler(SilvaBaseHandler):
    def characters(self, chrs):
        self.parentHandler().setData('status', chrs)

class PublicationDateTimeHandler(SilvaBaseHandler):
    def characters(self, chrs):
        self.parentHandler().setData('publication_datetime', chrs)

class ExpirationDateTimeHandler(SilvaBaseHandler):
    def characters(self, chrs):
        self.parentHandler().setData('expiration_datetime', chrs)

class URLHandler(SilvaBaseHandler):
    def characters(self, chrs):
        self.parentHandler().setData('url', chrs)

class ImportSettings(xmlimport.BaseSettings):
    pass

class ImportInfo:
    def __init__(self):
        self._asset_paths = {}
        self._zexp_paths = {}
        self._zip_file = None
        self._ghostfolders = [] 

    def setZipFile(self, file):
        self._zip_file = file

    def ZipFile(self):
        return self._zip_file
    
    def addAssetPath(self, zip_id, path):
        self._asset_paths[zip_id] = path
    
    def getAssetZipPath(self, zip_id):
        return self._asset_paths[zip_id]

    def getAssetPaths(self):
        return self._asset_paths.items()
    
    def addZexpPath(self, zip_id, path):
        self._zexp_paths[zip_id] = path
    
    def getZexpZipPath(self, zip_id):
        return self._zexp_paths[zip_id]

    def getZexpPaths(self):
        return self._zexp_paths.items()

    def addSyncTarget(self, ghostfolder):
        self._ghostfolders.append(ghostfolder)

    def getSyncTargets(self):
        return self._ghostfolders
    
def generateUniqueId(org_id, context):
        i = 0
        id = org_id
        ids = context.objectIds()
        while id in ids:
            i += 1
            add = ''
            if i > 1:
                add = str(i)
            id = 'import%s_of_%s' % (add, org_id)
        return id
    
def updateVersionCount(versionhandler):
    # The parent of a version is a VersionedContent object. This VC object
    # has an _version_count attribute to keep track of the number of
    # existing version objects and is the used to determine the id for a
    # new version. However, after importing, this _version_count has the
    # default value (1) and thus should be updated to reflect the highest
    # id of imported versions (+1 of course :)
    parent = versionhandler._parent
    version = versionhandler._result
    id = version.id
    try:
        id = int(id)
    except ValueError:
        # I guess this is the only reasonable thing to do - apparently 
        # this id does not have any numerical 'meaning'.
        return 
    vc = max(parent._version_count, (id + 1))
    parent._version_count = vc
