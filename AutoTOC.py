# Copyright (c) 2002-2006 Infrae. All rights reserved.
# See also LICENSE.txt
# $Id: AutoTOC.py,v 1.15 2006/01/24 16:14:12 faassen Exp $

from zope.interface import implements

# Zope
from Globals import InitializeClass
from AccessControl import ClassSecurityInfo
from Persistence import Persistent
from OFS.SimpleItem import SimpleItem

# products
from Products.ParsedXML.ParsedXML import ParsedXML

# Silva
from Products.Silva.Content import Content
from Products.Silva import SilvaPermissions
from Products.Silva.i18n import translate as _
from Products.Silva.interfaces import IAutoTOC, IContainerPolicy

class AutoTOC(Content, SimpleItem):
    __doc__ = _("""This is a special document that automagically displays a
       table of contents. Usually it&#8217;s used as an &#8216;index&#8217;
       document. In that case the parent folder shows a table of contents
       when accessed (e.g. http://www.x.yz/silva/myFolder/).""")
    security = ClassSecurityInfo()

    meta_type = "Silva AutoTOC"

    implements(IAutoTOC)

    def __init__(self, id):
        AutoTOC.inheritedAttribute('__init__')(self, id,
            '[Title is stored in metadata. This is a bug.]')

    # ACCESSORS
    security.declareProtected(SilvaPermissions.View, 'is_cacheable')
    def is_cacheable(self):
        """Return true if this document is cacheable.
        That means the document contains no dynamic elements like
        code, toc, etc.
        """
        return 0

    def is_deletable(self):
        """always deletable"""
        return 1

    def can_set_title(self):        
        """always settable"""
        # XXX: we badly need Publishable type objects to behave right.
        return 1
    
InitializeClass(AutoTOC)

class AutoTOCPolicy(Persistent):

    implements(IContainerPolicy)

    def createDefaultDocument(self, container, title):
        container.manage_addProduct['Silva'].manage_addAutoTOC(
            'index', title)
        container.index.sec_update_last_author_info()
