# -*- coding: utf-8 -*-
# Copyright (c) 2002-2010 Infrae. All rights reserved.
# See also LICENSE.txt
# $Id$

# Zope 3
from five import grok
from zope.component import getUtility

# Zope 2
from Acquisition import aq_inner, aq_base
from AccessControl import ClassSecurityInfo, getSecurityManager
from App.class_init import InitializeClass
from zExceptions import Unauthorized

# Silva
from Products.SilvaMetadata.Binding import DefaultMetadataBindingFactory
from Products.Silva.VersionedContent import VersionedContent
from Products.Silva.Version import Version
from Products.Silva import SilvaPermissions

from zope.schema.interfaces import InvalidValue
from zeam.form import silva as silvaforms
from zeam.form.base.errors import Error
from zeam.form.base.widgets import widget_id

from silva.core.views.interfaces import IPreviewLayer
from silva.core import conf as silvaconf
from silva.core.conf.interfaces import IIdentifiedContent
from silva.core.interfaces import (
    IContainer, IContent, IGhost, IGhostAware, IGhostVersion)
from silva.core.references.reference import Reference
from silva.core.references.reference import get_content_id, get_content_from_id
from silva.core.references.interfaces import IReferenceService
from silva.core.views import views as silvaviews
from silva.translations import translate as _

# status codes as returned by get_link_status
LINK_EMPTY = 1   # no link entered (XXX this cannot happen)
LINK_FOLDER = 3  # link points to folder
LINK_GHOST = 4 # link points to ghost
LINK_NO_CONTENT = 5 # link points to something which is not a content
LINK_CONTENT = 6 # link points to content
LINK_NO_FOLDER = 7 # link doesn't point to a folder
LINK_CIRC = 8 # Link results in a ghost haunting itself


class InvalidTarget(InvalidValue):

    def doc(self):
        err_code, = self.args
        if err_code == LINK_EMPTY:
            return _(u"Missing required ghost target.")
        if err_code == LINK_CIRC:
            return _(u"Ghost target creates a circular reference.")
        if err_code == LINK_GHOST:
            return _(u"Ghost target is a ghost.")
        if err_code == LINK_CONTENT or err_code == LINK_NO_FOLDER:
            return _(u"Ghost target should be a container.")
        if err_code == LINK_FOLDER or err_code ==  LINK_NO_CONTENT:
            return _(u"Ghost target should not be a container.")
        return _("Invalid ghost target.")


def validate_target(ghost, target, is_folderish=False, adding=False):
    """Validate a ghost for its given target.
    """
    if target is None:
        return InvalidTarget(LINK_EMPTY)
    # Check for cicular reference. You cannot select an ancestor
    # or descandant of the ghost (or the ghost)
    target_path = target.getPhysicalPath()
    ghost_path = ghost.getPhysicalPath()
    if target_path > ghost_path and not adding:
        if ghost_path == target_path[:len(ghost_path)]:
            return InvalidTarget(LINK_CIRC)
    elif target_path == ghost_path[:len(target_path)]:
            return InvalidTarget(LINK_CIRC)
    if IGhostAware.providedBy(target):
        return InvalidTarget(LINK_GHOST)
    if is_folderish:
        # If we are a container, we expect to have a container as
        # target.
        if IContent.providedBy(target):
            return InvalidTarget(LINK_CONTENT)
        if not IContainer.providedBy(target):
            return InvalidTarget(LINK_NO_FOLDER)
    else:
        # If we are not a container, we expect to have a content
        # as target.
        if IContainer.providedBy(target):
            return InvalidTarget(LINK_FOLDER)
        if not IContent.providedBy(target):
            return InvalidTarget(LINK_NO_CONTENT)


class GhostBase(object):
    """baseclass for Ghosts (or Ghost versions if it's versioned)
    """
    security = ClassSecurityInfo()

    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                              'set_title')
    def set_title(self, title):
        """Don't do anything.
        """
        pass

    security.declareProtected(
        SilvaPermissions.AccessContentsInformation, 'get_title')
    def get_title(self):
        """Get title.
        """
        content = self.get_haunted()
        if content is None:
            return _(u"Ghost target is broken")
        return content.get_title()

    security.declareProtected(
        SilvaPermissions.AccessContentsInformation, 'get_short_title')
    def get_short_title(self):
        """Get short title.
        """
        content = self.get_haunted()
        if content is None:
            return _(u"Ghost target is broken")
        return content.get_short_title()

    security.declareProtected(
        SilvaPermissions.AccessContentsInformation, 'get_title_editable')
    def get_title_editable(self):
        """Get title.
        """
        content = self.get_haunted()
        if content is None:
            return _(u"Ghost target is broken")
        return content.get_title_editable()

    security.declareProtected(
        SilvaPermissions.ChangeSilvaContent, 'set_haunted')
    def set_haunted(self, content):
        """ Set the content as the haunted object
        """
        service = getUtility(IReferenceService)
        reference = service.get_reference(
            aq_inner(self), name=u"haunted", add=True)
        if not isinstance(content, int):
            content = get_content_id(content)
        reference.set_target_id(content)

    security.declareProtected(SilvaPermissions.View, 'get_haunted')
    def get_haunted(self):
        service = getUtility(IReferenceService)
        reference = service.get_reference(
            aq_inner(self), name=u"haunted", add=True)
        return reference.target

    security.declareProtected(SilvaPermissions.View, 'get_link_status')
    def get_link_status(self):
        """Return an error code if this version of the ghost is broken.
        returning None means the ghost is Ok.
        """
        return validate_target(
            self,
            self.get_haunted(),
            IContainer.providedBy(self))


class GhostMetadataBindingFactory(DefaultMetadataBindingFactory):
    grok.context(IGhostAware)
    read_only = True

    def get_content(self):
        haunted = self.context.get_haunted()
        if haunted is not None:
            if IPreviewLayer.providedBy(haunted.REQUEST):
                return haunted.get_previewable()
            return haunted.get_viewable()
        return None


class Ghost(VersionedContent):
    __doc__ = _("""Ghosts are special documents that function as a
       placeholder for an item in another location (like an alias,
       symbolic link, shortcut). Unlike a hyperlink, which takes the
       Visitor to another location, a ghost object keeps the Visitor in the
       current publication, and presents the content of the ghosted item.
       The ghost inherits properties from its location (e.g. layout
       and stylesheets).
    """)

    meta_type = "Silva Ghost"
    security = ClassSecurityInfo()

    grok.implements(IGhost)
    silvaconf.icon('icons/silvaghost.gif')
    silvaconf.version_class('GhostVersion')

    security.declareProtected(
        SilvaPermissions.AccessContentsInformation, 'get_short_title')
    def get_title(self):
        """Get short_title for public use, from published version.
        """
        content = self.get_haunted()
        if content is None:
            return _(u"Ghost target is broken")
        return content.get_title()

    security.declareProtected(
        SilvaPermissions.AccessContentsInformation, 'get_short_title')
    def get_short_title(self):
        """Get short_title for public use, from published version.
        """
        content = self.get_haunted()
        if content is None:
            return _(u"Ghost target is broken")
        return content.get_short_title()

    security.declareProtected(
        SilvaPermissions.AccessContentsInformation, 'get_haunted')
    def get_haunted(self):
        if IPreviewLayer.providedBy(self.REQUEST):
            version = self.get_previewable()
        else:
            version = self.get_viewable()
        if version is not None:
            return version.get_haunted()
        return None

    security.declareProtected(
        SilvaPermissions.AccessContentsInformation, 'is_published')
    def is_published(self):
        public = self.get_viewable()
        if public is None:
            return False
        haunted = public.get_haunted()
        if haunted is None:
            return False
        return haunted.is_published()

    security.declareProtected(
        SilvaPermissions.AccessContentsInformation, 'get_modification_datetime')
    def get_modification_datetime(self):
        """Return modification datetime.
        """
        content = self.get_haunted()

        if content is not None:
            return content.get_modification_datetime()
        return super(Ghost, self).get_modification_datetime()


InitializeClass(Ghost)


class GhostVersion(GhostBase, Version):
    """Ghost version.
    """
    meta_type = 'Silva Ghost Version'
    grok.implements(IGhostVersion)

    security = ClassSecurityInfo()

    security.declareProtected(
        SilvaPermissions.AccessContentsInformation, 'fulltext')
    def fulltext(self):
       target = self.get_haunted()
       if target is not None:
           public_version = target.get_viewable()
           if public_version and hasattr(aq_base(public_version), 'fulltext'):
               return public_version.fulltext()
       return ""


class IGhostSchema(IIdentifiedContent):

    haunted = Reference(
        IContent,
        title=_(u"target"),
        description=_(u"The silva object the ghost is mirroring."),
        required=True)


def TargetValidator(field_name, is_folderish=False, adding=False):

    class Validator(object):

        def __init__(self, form, fields):
            self.form = form
            self.fields = fields

        def validate(self, data):
            """Validate ghost target before setting it.
            """
            # This is not beauty, but it works.
            content_id = data.get(field_name)
            if content_id is silvaforms.NO_VALUE:
                # If there value is required it is already checked
                return []
            error = validate_target(
                self.form.context,
                get_content_from_id(content_id),
                is_folderish,
                adding)
            if error is not None:
                identifier = widget_id(self.form, self.fields[field_name])
                return [Error(error.doc(), identifier)]
            return []

    return Validator


class GhostAddForm(silvaforms.SMIAddForm):
    """Add form for a ghost
    """
    grok.name(u"Silva Ghost")
    grok.context(IGhost)

    fields = silvaforms.Fields(IGhostSchema)
    dataValidators = [
        TargetValidator('haunted', is_folderish=False, adding=True)]

    def _add(self, parent, data):
        factory = parent.manage_addProduct['Silva']
        return factory.manage_addGhost(
            data['id'], 'Ghost', haunted=data['haunted'])


class GhostEditForm(silvaforms.SMIEditForm):
    """ Edit form for Ghost
    """
    grok.context(IGhost)
    fields = silvaforms.Fields(IGhostSchema).omit('id')
    dataValidators = [
        TargetValidator('haunted', is_folderish=False, adding=False)]


class GhostView(silvaviews.View):
    grok.context(IGhost)

    broken_message = _(u"This 'ghost' is unavailable. "
                       u"Please inform the site manager.")

    def render(self):
        content = self.content.get_haunted()
        if content is None:
            return self.broken_message
        permission = self.is_preview and 'Read Silva content' or 'View'
        if getSecurityManager().checkPermission(permission, content):
            return content.view()
        raise Unauthorized(
            u"You do not have permission to "
            u"see the target of this ghost")


def ghost_factory(container, identifier, target):
    """add new ghost to container

        container: container to add ghost to (must be acquisition wrapped)
        id: (str) id for new ghost in container
        target: object to be haunted (ghosted), acquisition wrapped
        returns created ghost

        actual ghost created depends on haunted object
        on IContainer a GhostFolder is created
        on IVersionedContent a Ghost is created
    """
    factory = container.manage_addProduct['Silva']
    if IGhostAware.providedBy(target):
        target = target.get_haunted()
    if target is not None:
        if IContainer.providedBy(target):
            factory = factory.manage_addGhostFolder
        elif IContent.providedBy(target):
            factory = factory.manage_addGhost
        factory(identifier, None, haunted=target)
        return container._getOb(identifier)
    return None
