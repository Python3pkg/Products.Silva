# Copyright (c) 2002 Infrae. All rights reserved.
# See also LICENSE.txt
# $Id: icon.py,v 1.2 2003/08/21 11:01:17 zagy Exp $

"""Sivla icon registry"""

# python
import os
from bisect import insort

# zope
import Globals
import OFS.misc_

# Silva
from Products.Silva.interfaces import \
    IIcon, IFile, ISilvaObject
    

class AdaptationError(Exception):
    """thrown if an object cannot be adapted by an adapter"""

class Adapter:
    
    __adapts__ = None
    
    def __init__(self, adapt):
        assert self.__adapts__ is not None
        if not self.__adapts__.isImplementedBy(adapt):
            raise AdaptationError, "%r doesn't implement %r" % (
                adapt, self.__adapts__)
        self.adapted = adapt
        

class MetaTypeAdapter(Adapter):

    __implements__ = IIcon
    __adapts__ = ISilvaObject
    
    def getIconIdentifier(self):
        return ('meta_type', self.adapted.meta_type)


class SilvaFileAdapter(Adapter):

    __implements__ = IIcon
    __adapts__ = IFile

    def getIconIdentifier(self):
        i = ('mime_type', self.adapted.get_mime_type())
        try:
            registry.getIconByIdentifier(i)
        except KeyError:
            return MetaTypeAdapter(self.adapted).getIconIdentifier()
        else:
            return i

    
class _RegistredAdapter:

    def __init__(self, adapter, priority):
        self.adapter = adapter
        self.priority = priority

    def __cmp__(self, other):
        assert isinstance(other, _RegistredAdapter)
        return -cmp(self.priority, other.priority) # reverse order


class _IconRegistry:

    def __init__(self):
        self._adapters = []
        self._icon_mapping = {}
    
    def getIcon(self, object):
        adapter = self.getAdapter(object)
        identifier = adapter.getIconIdentifier()
        return self.getIconByIdentifier(identifier)

    def getIconByIdentifier(self, identifier):
        icon = self._icon_mapping.get(identifier, None)
        if icon is None:
            raise KeyError, "No icon for %r" % (identifier, )
        return icon

    def getAdapter(self, object):
        if IIcon.isImplementedBy(object):
            # no need to adapt
            return object
        for ra in self._adapters:
            adapter_class = ra.adapter
            try:
                adapter = adapter_class(object)
            except AdaptationError:
                adapter = None
            else:
                break
        if adapter is None:
            raise ValueError, "No adapter for %r" % object
        return adapter
        
    def registerAdapter(self, adapter, priority):
        """registeres adapter with priority

            adapter: adapter instance
            priority: the larger the higher
        """
        insort(self._adapters, _RegistredAdapter(adapter, priority))
        

    def registerIcon(self, identifier, product, icon, context):
        """register icon

            identifier: icon identifier as returned from getIconIdentifier()
            product: the product the icon resides (i.e. 'Silva')
            icon: path to icon (i.e. 'www/root.png')
            context: module context of icon (i.e. globals())

            raises ValueError if product doesn't exist
            NOTE: this will overwrite previous icon declarations
        """
        # NOTE: code copied from App.ProductContext, modified though
        name = os.path.split(icon)[1]
        icon = Globals.ImageFile(icon, context)
        icon.__roles__ = None
        if not hasattr(OFS.misc_.misc_, product):
            raise ValueError, "The product %r doesn't exist" % product
        getattr(OFS.misc_.misc_, product)[name] = icon
        self._icon_mapping[identifier] = 'misc_/%s/%s' % (product, name)
            

registry = _IconRegistry()

