# Copyright (c) 2002 Infrae. All rights reserved.
# See also LICENSE.txt
# $Revision: 1.12 $
# Zope
from AccessControl import ClassSecurityInfo
from Globals import InitializeClass
# Silva interfaces
from IContent import IContent
# Silva
from SilvaObject import SilvaObject
from Publishable import Publishable
import SilvaPermissions

class Content(SilvaObject, Publishable):

    security = ClassSecurityInfo()
    
    __implements__ = IContent

    # use __init__ of SilvaObject
    
    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                             'is_default')
    def is_default(self):
        return self.id == 'index'

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'get_content')
    def get_content(self):
        """Get the content. Can be used with acquisition to get
        the 'nearest' content."""
        return self.aq_inner

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'content_url')
    def content_url(self):
        """Get content URL."""
        return self.absolute_url()

    security.declarePrivate('get_indexables')
    def get_indexables(self):
        return []
    
InitializeClass(Content)
