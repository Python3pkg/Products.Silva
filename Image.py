# Copyright (c) 2002 Infrae. All rights reserved.
# See also LICENSE.txt
# $Revision: 1.13 $
from AccessControl import ClassSecurityInfo
from Globals import InitializeClass
from Products.PageTemplates.PageTemplateFile import PageTemplateFile
from DateTime import DateTime
import OFS
# Silva interfaces
from IAsset import IAsset
# Silva
from Asset import Asset
import SilvaPermissions
# misc
from helpers import add_and_edit

class Image(Asset):
    """Image object.
    """    
    security = ClassSecurityInfo()

    meta_type = "Silva Image"

    __implements__ = IAsset
    
    def __init__(self, id, title):
        Image.inheritedAttribute('__init__')(self, id, title)
        self.image = None # should create default image

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'image')
    
    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                              'set_title')
    def set_title(self, title):
        """Set the title of the silva object.
        Overrides SilvaObject set_title() to accomodate the OFS.Image.Image 
        title attribute - which in turn is used in the tag() method.
        """
        self._title = title
        if self.image:
            # have to encode as otherwise unicode will blow up image rendering
            # code
            self.image.title = self.get_title_html()
        
    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                              'set_image')
    def set_image(self, file):
        """Set the image object.
        """
        self.image = OFS.Image.Image('image', self.get_title_html(), file)

    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                              'set_zope_image')
    def set_zope_image(self, zope_img):
        """Set the image object with zope image.
        """
        self.image = zope_img

    
InitializeClass(Image)
    
manage_addImageForm = PageTemplateFile("www/imageAdd", globals(),
                                       __name__='manage_addImageForm')

def manage_addImage(self, id, title, file=None, REQUEST=None):
    """Add an Image."""
    if not self.is_id_valid(id):
        return
    object = Image(id, title)
    self._setObject(id, object)
    object = getattr(self, id)

    if file:
        object.set_image(file)

    add_and_edit(self, id, REQUEST)
    return ''
