from StringIO import StringIO
# Zope
import Globals
from AccessControl import ModuleSecurityInfo, ClassSecurityInfo
# Silva Adapters
from Products.Silva.adapters import adapter, interfaces, assetdata
from Products.Silva.adapters import interfaces
from Products.Silva import SilvaPermissions

class ZipfileExportAdapter(adapter.Adapter):
    """ Adapter for silva objects to facilitate
    the export to zipfiles. 
    """

    __implements__ = (interfaces.IZipfileExporter, )
    
    security = ClassSecurityInfo()

    security.declareProtected(
        SilvaPermissions.ChangeSilvaContent, 'exportToZip')    
    def exportToZip(self, context, settings=None):
        from zipfile import ZipFile, ZIP_DEFLATED
        from Products.Silva.silvaxml import xmlexport
        inMemZip = StringIO()
        archive = ZipFile(inMemZip, "wb", ZIP_DEFLATED)

        # export context to xml and add xml to zip
        if settings == None:
            settings = xmlexport.ExportSettings()
        exporter = xmlexport.theXMLExporter
        info = xmlexport.ExportInfo()
        exportRoot = xmlexport.SilvaExportRoot(context)
        # XXX this way of using writestr depends on python 2.3.x!!!
        archive.writestr(
            'silva.xml', 
            exporter.exportToString(exportRoot, settings, info)
            )
        
        # process data from the export, i.e. export binaries
        for path, id in info.getAssetPaths():
            asset = context.restrictedTraverse(path)
            # XXX Code will change when AssetDataAdapters are phased out
            adapter = assetdata.getAssetDataAdapter(asset)
            if adapter is not None:
                asset_path = 'assets/%s' % id
                archive.writestr(
                    asset_path,
                    adapter.getData())
        for path, id in info.getZexpPaths():
            ob = context.restrictedTraverse(path)
            obid = ob.id
            if callable(obid):
                obid = obid()
            archive.writestr(
                'zexps/' + id,
                ob.aq_parent.manage_exportObject(
                    obid,
                    download=True))
        archive.close()
        return inMemZip.getvalue()
        
Globals.InitializeClass(ZipfileExportAdapter)

def getZipfileExportAdapter(context):
    return ZipfileExportAdapter(context).__of__(context)
    
