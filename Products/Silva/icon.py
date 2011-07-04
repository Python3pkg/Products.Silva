# Copyright (c) 2003-2010 Infrae. All rights reserved.
# See also LICENSE.txt
# $Id$

from five import grok
from zope.cachedescriptors.property import CachedProperty
from zope.publisher.interfaces.browser import IBrowserRequest

# Silva
from silva.core import interfaces
from silva.core.views.interfaces import IVirtualSite
from silva.core.interfaces.adapters import IIconResolver


class SilvaIcons(grok.DirectoryResource):
    # This export the globals directory using Zope 3 technology.
    grok.path('icons')
    grok.name('silva.icons')


class IconRegistry(object):
    grok.implements(interfaces.IIconRegistry)

    def __init__(self):
        self.__icons = {}

    def getIcon(self, content):
        if interfaces.IGhost.providedBy(content):
            version = content.getLastVersion()
            if version.get_link_status() == version.LINK_OK:
                kind = 'link_ok'
            else:
                kind = 'link_broken'
            identifier = ('ghost', kind)
        elif interfaces.IGhostFolder.providedBy(content):
            if content.get_link_status() == content.LINK_OK:
                if interfaces.IPublication.providedBy(content):
                    kind = 'publication'
                else:
                    kind = 'folder'
            else:
                kind = 'link_broken'
            identifier = ('ghostfolder', kind)
        elif interfaces.IFile.providedBy(content):
            identifier = ('mime_type', content.get_mime_type())
        elif interfaces.ISilvaObject.providedBy(content):
            identifier = ('meta_type', content.meta_type)
        else:
            if content is None:
                return '++static++/silva.icons/missing.png'
            if interfaces.IAuthorization.providedBy(content):
                content = content.source
            meta_type = getattr(content, 'meta_type', None)
            if meta_type is None:
                raise ValueError(u"No icon for unknown object %r" % content)
            identifier = ('meta_type', meta_type)
        return self.getIconByIdentifier(identifier)

    def getIconByIdentifier(self, identifier):
        icon = self.__icons.get(identifier, None)
        if icon is None:
            raise ValueError(u"No icon for %r" % repr(identifier))
        return icon

    def registerIcon(self, identifier, icon_name):
        """Register an icon.

        NOTE: this will overwrite previous icon declarations
        """
        self.__icons[identifier] = icon_name


registry = IconRegistry()


class IconResolver(grok.Adapter):
    grok.context(IBrowserRequest)
    grok.implements(IIconResolver)

    def __init__(self, request):
        self.request = request

    @CachedProperty
    def _base_url(self):
        site = IVirtualSite(self.request)
        return site.get_root_url()

    def get_tag(self, content):
        return """<img height="16" width="16" src="%s" alt="%s" />""" % (
            self.get_content_url(content),
            getattr(content, 'meta_type', ''))

    def get_content(self, content):
        try:
            return registry.getIcon(content)
        except ValueError:
            return '++static++/silva.icons/silvageneric.gif'

    def get_content_url(self, content):
        """Return a content icon URL.
        """
        return "/".join((self._base_url, self.get_content(content),))
