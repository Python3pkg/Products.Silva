# Copyright (c) 2003 Infrae. All rights reserved.
# See also LICENSE.txt
# $Revision: 1.59.6.1 $

# Zope
from AccessControl import ClassSecurityInfo
from Products.PageTemplates.PageTemplateFile import PageTemplateFile
from Globals import InitializeClass
# Silva
import Folder
import SilvaPermissions
import ContainerPolicy
# misc
from helpers import add_and_edit

from Products.Silva.ImporterRegistry import get_importer, xml_import_helper, get_xml_id, get_xml_title
from Products.Silva.Metadata import export_metadata
from Products.Silva import mangle

from interfaces import IPublication

icon="www/silvapublication.gif"
addable_priority = -0.5

class Publication(Folder.Folder):
    """Publications function as the major organizing blocks of a Silva site. 
       They are comparable to binders, and can contain folders, documents, and assets. 
       Publications are opaque. They instill a threshold of view, showing
       only the contents of the current publication. This keeps the overview
       screens manageable. Publications have configuration settings that
       determine which core and pluggable objects are available. For
       complex sites, sub-publications can be nested.
    """
    security = ClassSecurityInfo()
    
    meta_type = "Silva Publication"

    __implements__ = IPublication

    _addables_allowed_in_publication = None

    layout_key = None

    def __init__(self, id):
        Publication.inheritedAttribute('__init__')(
            self, id)
        self.layout_key = None
    
    # MANIPULATORS
    
    security.declareProtected(SilvaPermissions.ApproveSilvaContent,
                              'set_layout')
    def set_layout(self, layout_name):
        """Set template layout
        """
        service_layouts = self.get_root().service_layouts
        if service_layouts.has_own_layout(self):
            service_layouts.remove_layout(self)
        if layout_name:
            layout = service_layouts.setup_layout(layout_name, self)
    
    security.declareProtected(SilvaPermissions.ApproveSilvaContent,
                              'copy_layout')
    def copy_layout(self):
        """Copy layout to publication
        to be able to customize it.
        """
        service_layouts = self.get_root().service_layouts
        layout = service_layouts.copy_layout(self)
    
    def get_layout_key(self, own=0):
        layout_key = self.get_own_layout_key()
        if layout_key or (self == self.get_root()):
            return layout_key
        else:
            return self.get_publication().aq_parent.get_publication().get_layout_key()

    def get_own_layout_key(self):
        return self.layout_key

    def set_layout_key(self, value):
        self.layout_key = value 

    def layout_copied(self):
        return self.service_layouts.layout_copied(self)

    def get_layout_folder(self):
        return self.service_layouts.get_layout_folder(self)

    security.declareProtected(SilvaPermissions.ApproveSilvaContent,
                              'set_silva_addables_allowed_in_publication')
    def set_silva_addables_allowed_in_publication(self, addables):
        self._addables_allowed_in_publication = addables
    
    security.declareProtected(SilvaPermissions.ApproveSilvaContent,
                              'to_folder')
    def to_folder(self):
        """Publication becomes a folder instead.
        """
        self._to_folder_or_publication_helper(to_folder=1)
        

    def manage_afterClone(self, item):
        Folder.Folder.inheritedAttribute('manage_afterClone')(self, item)
        service_layouts = self.get_root().service_layouts
        service_layouts.clone_layout(self)

    # ACCESSORS
    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'get_layout')
    def get_layout(self):
        """Get template layout (own or acquired).
        """
        if not hasattr(self, "layout_key"):
            self.layout_key = None
        service_layouts = self.get_root().service_layouts
        return service_layouts.get_layout_name(self)

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'get_layout_description')
    def get_layout_description(self):
        """Get template layout description (own or acquired).
        """
        if not hasattr(self, "layout_key"):
            self.layout_key = None
        service_layouts = self.get_root().service_layouts
        return service_layouts.get_layout_description(self)

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'get_own_layout')
    def get_own_layout(self):
        """Get own template layout (not acquired).
        """
        if not hasattr(self, "layout_key"):
            self.layout_key = None
        service_layouts = self.get_root().service_layouts
        return service_layouts.get_own_layout_name(self)
    
    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'get_publication')
    def get_publication(self):
        """Get publication. Can be used with acquisition to get
        'nearest' Silva publication.
        """
        return self.aq_inner
    
    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'is_transparent')
    def is_transparent(self):
        return 0

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'to_xml')
    def to_xml(self, context):
        """Render object to XML.
        """
        f = context.f
        f.write('<silva_publication id="%s">' % self.id)
        self._to_xml_helper(context)
        export_metadata(self, context)
        f.write('</silva_publication>')

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'get_silva_addables_allowed_in_publication')
    def get_silva_addables_allowed_in_publication(self):
        current = self
        root = self.get_root()
        while 1:
            addables = current._addables_allowed_in_publication
            if addables is not None:
                return addables
            elif current == root:
                return self.get_silva_addables_all()
            current = current.aq_parent

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'is_silva_addables_acquired')
    def is_silva_addables_acquired(self):
        return self._addables_allowed_in_publication is None

InitializeClass(Publication)

manage_addPublicationForm = PageTemplateFile("www/publicationAdd", globals(),
                                             __name__='manage_addPublicationForm')

def manage_addPublication(
    self, id, title, create_default=1, policy_name='None', REQUEST=None):
    """Add a Silva publication."""
    if not mangle.Id(self, id).isValid():
        return
    object = Publication(id)
    self._setObject(id, object)
    object = getattr(self, id)
    object.set_title(title)
    if create_default:
        policy = self.service_containerpolicy.getPolicy(policy_name)
        policy.createDefaultDocument(object, title)
    add_and_edit(self, id, REQUEST)
    return ''

def xml_import_handler(object, node):
    """import publication"""
    
    def factory(object, id, title):
        object.manage_addProduct["Silva"].manage_addPublication(id, title, 0)
    
    return Folder.xml_import_handler(object, node, factory=factory)
        
