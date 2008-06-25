# Copyright (c) 2002-2008 Infrae. All rights reserved.
# See also LICENSE.txt
# $Id: SilvaObject.py,v 1.124 2006/01/25 18:13:31 faassen Exp $

# python
from types import StringType
import os

from warnings import warn

from zope.i18n import translate
from zope import component
from zope import interface
from zope.publisher.interfaces.browser import IBrowserView
from zope.publisher.interfaces.browser import IBrowserPage
# Zope
from OFS.interfaces import IObjectWillBeAddedEvent
from zope.app.container.interfaces import IObjectRemovedEvent
from AccessControl import ClassSecurityInfo
from Globals import InitializeClass
from DateTime import DateTime
from StringIO import StringIO
from App.Common import rfc1123_date
# WebDAV
from webdav.common import Conflict
from zExceptions import MethodNotAllowed
# Silva
import SilvaPermissions
from Products.SilvaViews.ViewRegistry import ViewAttribute
from Security import Security
from ViewCode import ViewCode
from interfaces import ISilvaObject, IContent, IPublishable, IAsset
from interfaces import IContent, IContainer, IPublication, IRoot
from interfaces import IVersioning, IVersionedContent, IFolder
from Products.Silva import helpers
from Products.Silva.utility import interfaces as utility_interfaces
# Silva adapters
from Products.Silva.adapters.renderable import getRenderableAdapter
from Products.Silva.adapters.virtualhosting import getVirtualHostingAdapter

from Products.SilvaMetadata.Exceptions import BindingError

from Products.Silva.i18n import translate as _


class XMLExportContext:
    """Simple context class used in XML export.
    """
    pass

class NoViewError(Exception):
    """no view defined"""

class FrankenViewAttribute(ViewAttribute):
    """A view attribute that switches skins and tries to look up Zope
    3 views for fun and profit.

    It enables skin switching, so that the 'bare bones' skin is active
    when we look at preview pages.

    It will also try to look up Zope 3 views and favour them, so that
    you can define e.g. 'tab_edit' for your content type and it will
    work.
    """
    def __init__(self, view_type, default_method, skin=None):
        ViewAttribute.__init__(self, view_type, default_method)
        self._skin = skin

    def _switch_skin(self):
        if self._skin:
            interface.directlyProvides(
                self.REQUEST,
                self._skin, interface.directlyProvidedBy(self.REQUEST))

    def index_html(self):
        """Make Zope happy"""
        return ViewAttribute.index_html(self)

    def __getitem__(self, name):
        """Make Zope happy"""
        self._switch_skin()
        context = self.aq_inner.aq_parent
        request = self.REQUEST
        view = component.queryAdapter((context, request), name=name)
        if view:
            return view.__of__(self.context)()
        else:
            return ViewAttribute.__getitem__(self, name)

class SilvaObject(Security, ViewCode):
    """Inherited by all Silva objects.
    """
    security = ClassSecurityInfo()

    # FIXME: this is for backward compatibility with old objects
    _title = "No title yet"

    # allow edit view on this object
    edit = ViewAttribute('edit', 'tab_edit')

    security.declareProtected(
        SilvaPermissions.ReadSilvaContent, 'edit')

    # and public as well
    public = ViewAttribute('public', 'render')

    # whether the object should be shown in the addables-pulldown
    _is_allowed_in_publication = 1

    # location of the xml schema
    _xml_namespace = "http://www.infrae.com/xml"
    _xml_schema = "silva-0.9.3.xsd"

    def __init__(self, id):
        self.id = id
        self._v_creation_datetime = DateTime()
        
    def __repr__(self):
        return "<%s instance %s>" % (self.meta_type, self.id)

    # MANIPULATORS

    def _set_creation_datetime(self):
        timings = {}
        ctime = getattr(self, '_v_creation_datetime', None)
        if ctime is None:
            return
        try:
            binding = self.service_metadata.getMetadata(self)
        except BindingError:
            # Non metadata object, don't do anything
            return
        if binding is None:
            return
        for elem in ('creationtime', 'modificationtime'):
            old = binding.get('silva-extra', element_id=elem)
            if old is None:
                timings[elem] = ctime
        binding.setValues('silva-extra', timings)

    security.declareProtected(
        SilvaPermissions.ChangeSilvaContent, 'set_title')
    def set_title(self, title):
        """Set the title of the silva object.
        """
        # FIXME: Ugh. I get unicode from formulator but this will not validate
        # when using the metadata system. So first make it into utf-8 again..
        title = title.encode('utf-8')
        binding = self.service_metadata.getMetadata(self)
        binding.setValues(
            'silva-content', {'maintitle': title})
        if self.id == 'index':
            container = self.get_container()
            container._invalidate_sidebar(container)

    security.declarePrivate('titleMutationTrigger')
    def titleMutationTrigger(self):
        """This trigger is called upon save of Silva Metadata. More
        specifically, when the silva-content - defining titles - set is
        being editted for this object.
        """
        if self.id == 'index':
            container = self.get_container()
            container._invalidate_sidebar(container)

    security.declareProtected(
        SilvaPermissions.ChangeSilvaContent, 'set_renderer_name')
    def set_renderer_name(self, renderer_name):
        """Set the name of the renderer selected for object.
        """
        if renderer_name == '(Default)':
            renderer_name = None
        self.get_editable()._renderer_name = renderer_name
            
    # ACCESSORS

    security.declareProtected(
        SilvaPermissions.AccessContentsInformation, 'get_silva_object')
    def get_silva_object(self):
        """Get the object. Can be used with acquisition to get the Silva
        Document for a Version object.
        """
        return self.aq_inner

    security.declareProtected(
        SilvaPermissions.AccessContentsInformation, 'silva_object_url')
    def silva_object_url(self):
        """Get url for silva object.
        """
        return self.get_silva_object().absolute_url()

    security.declareProtected(
        SilvaPermissions.AccessContentsInformation, 'get_title')
    def get_title(self):
        """Get the title of the silva object.
        """
        return self.service_metadata.getMetadataValue(
            self, 'silva-content', 'maintitle')

    def title(self):
        return self.get_title()

    security.declareProtected(
        SilvaPermissions.AccessContentsInformation, 'get_short_title')
    def get_short_title(self):
        """Get the title of the silva object.
        """
        title = self.service_metadata.getMetadataValue(
            self, 'silva-content', 'shorttitle')
        if not title:
            title = self.service_metadata.getMetadataValue(
                self, 'silva-content', 'maintitle')
        if not title:
            title = self.id
        return title

    security.declareProtected(
        SilvaPermissions.AccessContentsInformation, 'get_title_or_id')
    def get_title_or_id(self):
        """Get title or id if not available.
        """
        title = self.get_title()
        if not title.strip():
            title = self.id
        return title

    security.declareProtected(
        SilvaPermissions.AccessContentsInformation, 'get_title_editable')
    def get_title_editable(self):
        """Get the title of the editable version if possible.
        """
        return self.get_title()

    security.declareProtected(
        SilvaPermissions.AccessContentsInformation, 'get_title_editable')
    def get_short_title_editable(self):
        """Get the short title of the editable version if possible.
        """
        return self.get_short_title()

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'get_title_or_id_editable')
    def get_title_or_id_editable(self):
        """Get the title of the editable version if possible, or id if
        not available.
        """
        return self.get_title_or_id()

    security.declareProtected(
        SilvaPermissions.ReadSilvaContent, 'can_set_title')
    def can_set_title(self):
        """Check to see if the title can be set
        """
        return 1

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'get_creation_datetime')
    def get_creation_datetime(self):
        """Return creation datetime."""
        version = self.get_previewable()
        return self.service_metadata.getMetadataValue(
            version, 'silva-extra', 'creationtime')

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'get_modification_datetime')
    def get_modification_datetime(self, update_status=1):
        """Return modification datetime."""
        version = self.get_previewable()
        return self.service_metadata.getMetadataValue(
            version, 'silva-extra', 'modificationtime')

    security.declareProtected(
        SilvaPermissions.AccessContentsInformation, 'get_breadcrumbs')
    def get_breadcrumbs(self, ignore_index=1):
        """Get information used to display breadcrumbs. This is a
        list of items from the Silva Root or the object being the root of
        the virtual host - which ever comes first.
        """
        adapter = getVirtualHostingAdapter(self)
        root = adapter.getVirtualRoot()
        if root is None:
            root = self.get_root()

        result = []
        item = self
        while ISilvaObject.providedBy(item):
            if ignore_index: # Should the index be included?
                if not (IContent.providedBy(item) and item.is_default()):
                    result.append(item)
            else:
                result.append(item)

            if item == root: # XXX does equality always work in Zope?
                break
            item = item.aq_parent
            #if using SilvaLayout, eventually an items parent will be the
            #view class.  This needs to be skipped over.  I'm not sure
            #which is the "correct" interface (IBrowserView or IBrowserPage),
            #but they both seem to work.
            if IBrowserView.providedBy(item) or IBrowserPage.providedBy(item):
                item = item.aq_parent.aq_parent
        result.reverse()
        return result

    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                              'get_editable')
    def get_editable(self):
        """Get the editable version (may be object itself if no versioning).
        """
        return self

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'get_previewable')
    def get_previewable(self):
        """Get the previewable version (may be the object itself if no
        versioning).
        """
        return self

    security.declareProtected(SilvaPermissions.View, 'get_viewable')
    def get_viewable(self):
        """Get the publically viewable version (may be the object itself if
        no versioning).
        """
        return self

    security.declareProtected(
        SilvaPermissions.AccessContentsInformation, 'get_renderer_name')
    def get_renderer_name(self):
        """Get the name of the renderer selected for object.
        
        Returns None if default is used.
        """
        return getattr(self, '_renderer_name', None)
    
    security.declareProtected(SilvaPermissions.ReadSilvaContent, 'preview')
    def preview(self):
        """Render this as preview with the public view.

        If this is no previewable, should return something indicating this.
        """
        content = self.get_previewable()
        try:
            return self.view_version('preview', content)
        except NoViewError:
            # fallback to public 'render' script if no preview available
            return self.view_version('public', content)

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'public_preview')
    def public_preview(self):
        """Public preview.

        By default this does the same as preview, but can be overridden.
        """
        return self.preview()
        
    security.declareProtected(SilvaPermissions.View, 'view')
    def view(self):
        """Render this with the public view. If there is no viewable,
        should return something indicating this.
        """
        content = self.get_viewable()
        return self.view_version('public', content)

    security.declareProtected(
        SilvaPermissions.ReadSilvaContent, 'view_version')
    def view_version(self, view_type, version):
        if version is None:
            msg = _('Sorry, this ${meta_type} is not viewable.',
                    mapping={'meta_type': self.meta_type})
            return '<p>%s</p>' % translate(msg, context=self.REQUEST)
        result = getRenderableAdapter(version).view()
        if result is not None:
            return result
        request = self.REQUEST
        request.model = version
        request.other['model'] = version
        
        # Fallback on SilvaViews view
        try:
            view = self.service_view_registry.get_view(
                view_type, version.meta_type)
        except KeyError:
            msg = 'no %s view defined' % view_type
            raise NoViewError, msg
        else:
            rendered = view.render()
            try:
                del request.model
            except AttributeError, e:
                pass
            return rendered

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'is_default')
    def is_default(self):
        """returns True if the SilvaObject is a default document
        
            by default return False, overridden on Content where an actual
            check is done
        """
        return False

    # these help the UI that can't query interfaces directly

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'implements_publishable')
    def implements_publishable(self):
        return IPublishable.providedBy(self)

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'implements_asset')
    def implements_asset(self):
        return IAsset.providedBy(self)

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'implements_content')
    def implements_content(self):
        return IContent.providedBy(self)

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'implements_container')
    def implements_container(self):
        return IContainer.providedBy(self)

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'implements_publication')
    def implements_publication(self):
        return IPublication.providedBy(self)

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'implements_root')
    def implements_root(self):
        return IRoot.providedBy(self)

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'implements_versioning')
    def implements_versioning(self):
        return IVersioning.providedBy(self)

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'implements_versioned_content')
    def implements_versioned_content(self):
        return IVersionedContent.providedBy(self)

    security.declareProtected(
        SilvaPermissions.ViewAuthenticated, 'security_trigger')
    def security_trigger(self):
        """This is equivalent to activate_security_hack(), however this
        method's name is less, er, hackish... (e.g. when visible in error
        messages and trace-backs).
        """
        # create a member implicitely, if not already there
        #if hasattr(self.get_root(),'service_members'):
        #    self.get_root().service_members.get_member(
        #        self.REQUEST.AUTHENTICATED_USER.getId())

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'get_zip')
    def get_zip(self, with_sub_publications=0, last_version=0):
        """Get Zipfile with XML-Document for object, and binary files
        in a subdirectory 'assets'.
        """
        warn('you should use export_content with zip as formater'
             ' instead of get_zip', DeprecationWarning)
        return self.export_content('zip', with_sub_publications, last_version)


    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'export_content')
    def export_content(self, export_format, 
                       with_sub_publications=0, 
                       last_version=0):
        """Export content using the exporter export_format.
        """
        from Products.Silva.silvaxml import xmlexport
        settings = xmlexport.ExportSettings()
        settings.setWithSubPublications(with_sub_publications)
        settings.setLastVersion(last_version)

        utility = component.getUtility(utility_interfaces.IExportUtility)()
        exporter = utility.createContentExporter(self, export_format)
        return exporter.export(settings)

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'export_content_format')
    def export_content_format(self, ref=None):
        """Retrieve a list of export format.
        """
        context = self
        if ref:
            context =  self.resolve_ref(ref)
        utility = component.getUtility(utility_interfaces.IExportUtility)()
        return utility.listContentExporter(context)

    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
        'is_deletable')
    def is_deletable(self):
        """always deletable"""
        return 1

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'get_xml')
    def get_xml(self, with_sub_publications=0, last_version=0):
        """Get XML-Document in UTF8-Encoding for object (recursively).

        Note that you get a full document with a processing instruction.
        if you want to get "raw" xml, use the 'to_xml' machinery.
        """
        context = XMLExportContext()
        context.f = StringIO()
        context.with_sub_publications = with_sub_publications
        context.last_version = not not last_version
        w = context.f.write
        # construct xml and return UTF8-encoded string
        w(u'<?xml version="1.0" encoding="UTF-8" ?>\n')
        w(u'<silva xmlns="%s" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            'xsi:schemaLocation="%s %s" '
            #'xml:base="%s" '

            'silva_root="%s" >' % (self._xml_namespace,
                self._xml_namespace, self._xml_schema,
            #    self.absolute_url(),
                self.getPhysicalRoot().absolute_url()))
        self.to_xml(context)
        w(u'</silva>')
        result = context.f.getvalue()
        return result.encode('UTF-8')

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'get_xml_for_objects')
    def get_xml_for_objects(self, objects, with_sub_publications=0, last_version=0):
        """Get XML-Document in UTF8-Encoding for a list of object references

        Note that you get a full document with a processing instruction.
        if you want to get "raw" xml, use the 'to_xml' machinery.
        """
        context = XMLExportContext()
        context.f = StringIO()
        context.with_sub_publications = with_sub_publications
        context.last_version = not not last_version
        w = context.f.write
        # construct xml and return UTF8-encoded string
        w(u'<?xml version="1.0" encoding="UTF-8" ?>\n')
        w(u'<silva xmlns="%s" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            'xsi:schemaLocation="%s %s">' % (self._xml_namespace,
                self._xml_namespace, self._xml_schema))
        for obj in objects:
            obj.to_xml(context)
        w(u'</silva>')
        result = context.f.getvalue()
        return result.encode('UTF-8')

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'to_xml')
    def to_xml(self, context):
        """Handle unknown objects. (override in subclasses)
        """
        context.f.write('<unknown id="%s">%s</unknown>' % (self.id, self.meta_type))

    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
        'is_deletable')
    def is_deletable(self):
        """always deletable"""
        return 1

    # WebDAV support

    security.declarePublic('HEAD')
    def HEAD(self, REQUEST, RESPONSE):
        """ assumes the content type is text/html;
            override HEAD for classes where this is wrong!
        """
        mod_time = rfc1123_date ( self.get_modification_datetime() )
        RESPONSE.setHeader('Content-Type', 'text/html')
        RESPONSE.setHeader('Last-Modified', mod_time)

        return ''

    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                                'LOCK')
    def LOCK(self):
        """WebDAV locking, for now just raise an exception"""
        raise Conflict, 'not yet implemented'

    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                                'UNLOCK')
    def UNLOCK(self):
        """WebDAV locking, for now just raise an exception"""
        raise Conflict, 'not yet implemented'

    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                                'MKCOL')
    def MKCOL(self):
        """WebDAV MKCOL, only supported by certain subclasses"""
        raise MethodNotAllowed, 'method not allowed'

    # commented out to shut up security declaration.
    #security.declareProtected(SilvaPermissions.ReadSilvaContent,
    #                            'PROPFIND')
        
    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                                'PROPPATCH')
    def PROPPATCH(self):
        """PROPPATCH support, currently just fails"""
        raise Conflict, 'not yet implemented'

InitializeClass(SilvaObject)

def object_moved(object, event):
    if object != event.object or IObjectRemovedEvent.providedBy(
        event) or IRoot.providedBy(object):
        return
    newParent = event.newParent

    if (IPublishable.providedBy(object) and not (
        IContent.providedBy(object) and object.is_default())):
        newParent._add_ordered_id(object)
            
    if event.newName == 'index':
        newParent._invalidate_sidebar(newParent)
    if not IVersionedContent.providedBy(object):
        object._set_creation_datetime()

def object_will_be_moved(object, event):
    if object != event.object or IObjectWillBeAddedEvent.providedBy(
        event) or IRoot.providedBy(object):
        return
    container = event.oldParent
    if (IPublishable.providedBy(object) and not (
        IContent.providedBy(object) and object.is_default())):
        container._remove_ordered_id(object)
    if IFolder.providedBy(object):
        container._invalidate_sidebar(object)
    if event.oldName == 'index':
        container._invalidate_sidebar(container)
