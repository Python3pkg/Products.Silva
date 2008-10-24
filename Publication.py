# Copyright (c) 2003-2008 Infrae. All rights reserved.
# See also LICENSE.txt
# $Id$

# Zope 3
from zope.interface import implements

# Zope 2
from AccessControl import ClassSecurityInfo
from Globals import InitializeClass, DTMLFile
from zExceptions import BadRequest
import transaction
import Acquisition

# Silva
from Products.Silva import Folder
from Products.Silva import SilvaPermissions
from Products.Silva.helpers import add_and_edit
from Products.Silva import mangle
from Products.Silva.i18n import translate as _
from Products.Silva.interfaces import IPublication, IRoot, ISiteManager
from Products.Silva.interfaces import IInvisibleService

from silva.core import conf as silvaconf

class OverQuotaException(BadRequest):
    """Exception triggered when you're overquota.
    """
    pass

class AcquisitionMethod(Acquisition.Explicit):
    """This class let you have an acquisition context on a method.
    """
    def __init__(self, parent, method_name):
        self.parent = parent
        self.method_name = method_name

    def __call__(self, *args, **kwargs):
        instance = self.parent.aq_inner
        method = getattr(instance, self.method_name)
        return method(*args, **kwargs)


class Publication(Folder.Folder):
    __doc__ = _("""Publications are special folders. They function as the
       major organizing blocks of a Silva site. They are comparable to
       binders, and can contain folders, documents, and assets.
       Publications are opaque. They instill a threshold of view, showing
       only the contents of the current publication. This keeps the overview
       screens manageable. Publications have configuration settings that
       determine which core and pluggable objects are available. For
       complex sites, sub-publications can be nested.
    """)
    security = ClassSecurityInfo()

    meta_type = "Silva Publication"

    implements(IPublication)

    _addables_allowed_in_publication = None

    silvaconf.priority(-5)
    silvaconf.icon('www/silvapublication.gif')
    silvaconf.factory('manage_addPublication')


    @property
    def manage_options(self):
        # A hackish way to get a Silva tab in between the standard ZMI tabs
        base_options = super(Publication, self).manage_options
        manage_options = (base_options[0], )
        if ISiteManager(self).isSite():
            manage_options += ({'label':'Services', 'action':'manage_services'},)
        return manage_options + base_options[1:]

    security.declareProtected(SilvaPermissions.ViewManagementScreens,
                              'manage_main')
    manage_main = DTMLFile(
        'www/folderContents', globals())

    security.declareProtected(SilvaPermissions.ViewManagementScreens,
                              'manage_services')
    manage_services = DTMLFile(
        'www/folderServices', globals())


    def __init__(self, id):
        Publication.inheritedAttribute('__init__')(
            self, id)

    # MANIPULATORS

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

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'validate_wanted_quota')
    def validate_wanted_quota(self, value, REQUEST=None):
        """Validate the wanted quota is correct the current
        publication.
        """
        if value < 0:
            return False        # Quota can't be negative.
        if (not value) or IRoot.providedBy(self):
            return True         # 0 means no quota, Root don't have
                                # any parents.
        parent = self.aq_parent.get_publication()
        quota = parent.get_current_quota()
        if quota and quota < value:
            return False
        return True

    def get_wanted_quota_validator(self):
        """Return the quota validator with an acquisition context
        (needed to be used in Formulator).
        """
        return AcquisitionMethod(self, 'validate_wanted_quota')


    def _verify_quota(self, REQUEST=None):

        quota = self.get_current_quota()
        if quota and self.used_space > (quota * 1024 * 1024):
            # No comments.
            if (not REQUEST) and hasattr(self, 'REQUEST'):
                REQUEST = self.REQUEST
            if REQUEST:
                transaction.abort()
                REQUEST.form.clear()
                REQUEST.form['message_type'] = 'error'
                REQUEST.form['message'] = _('You are overquota.')
                REQUEST.RESPONSE.write(unicode(REQUEST.PARENTS[0].index_html()).encode('utf-8'))
                REQUEST.close()
            raise OverQuotaException


    # ACCESSORS

    security.declarePublic('objectItemsContents')
    def objectItemsContents(self, spec=None):
        """Don't display services by default in the Silva root.
        """
        return [item for item in Publication.inheritedAttribute('objectItems')(self)
                if not item[0].startswith('service_')]

    security.declarePublic('objectItemsServices')
    def objectItemsServices(self, spec=None):
        """Display services separately.
        """
        return [item for item in Publication.inheritedAttribute('objectItems')(self)
                if item[0].startswith('service_')
                and not IInvisibleService.providedBy(item[1])]

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'get_current_quota')
    def get_current_quota(self):
        """Return the current quota value on the publication.
        """
        service_metadata = self.service_metadata
        binding = service_metadata.getMetadata(self)
        try:
            return int(binding.get('silva-quota', element_id='quota') or 0)
        except KeyError:        # This publication object doesn't have
                                # this metadata set
            return self.aq_parent.get_current_quota()

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
                              'get_silva_addables_allowed_in_publication')
    def get_silva_addables_allowed_in_publication(self):
        current = self
        root = self.get_root()
        while 1:
            if IPublication.providedBy(current):
                addables = current._addables_allowed_in_publication
                if addables is not None:
                    return addables
            if current == root:
                return self.get_silva_addables_all()
            current = current.aq_parent

    security.declareProtected(SilvaPermissions.ReadSilvaContent,
                              'is_silva_addables_acquired')
    def is_silva_addables_acquired(self):
        return self._addables_allowed_in_publication is None

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'get_document_chapter_links')
    def get_document_chapter_links(self, depth=0):
        """returns a dict for document links (accessibility).

        This will return chapter, section, subsection and subsubsection
        links in a dictionary.

        These can be used by Mozilla in the accessibility toolbar.
        """
        types = ['chapter', 'section', 'subsection', 'subsubsection']

        result = {}
        tree = self.get_container_tree(depth)
        for depth, container in tree:
            if not container.is_published():
                continue
            if not result.has_key(types[depth]):
                result[types[depth]] = []
            result[types[depth]].append({
                'title': container.get_title(),
                'url': container.absolute_url()
                })
        return result

    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'get_document_index_links')
    def get_document_index_links(self, toc_id='index', index_id=None):
        """Returns a dictionary for document links.

        This will return the contents and index links, if
        available.

        These can be used by Mozilla in the accessibility toolbar.
        """
        result = {}
        # get the table of contents
        contents = self._getOb(toc_id, None)
        if contents is not None and contents.is_published():
            result['contents'] = contents.absolute_url()

        # get the index
        if index_id is None:
            indexers = self.objectValues(['Silva Indexer'])
            if indexers:
                index = indexers[0]
            else:
                index = None
        else:
             index = self._getOb(index_id, None)

        if index is not None and index.is_published():
            result['index'] = index.absolute_url()

        return result

InitializeClass(Publication)

from silva.core.views import views as silvaviews
from five import grok

class ManageLocalSite(silvaviews.SMIView):

    silvaconf.require('zope2.ViewManagementScreens')

    def update(self):
        self.manager = ISiteManager(self.context)
        if 'makesite' in self.request.form:
            self.manager.makeSite()
        if 'unmakesite' in self.request.form:
            self.manager.unmakeSite()

    def isSite(self):
        return self.manager.isSite()


managelocalsite = grok.PageTemplate("""
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:metal="http://xml.zope.org/namespaces/metal"
      xmlns:tal="http://xml.zope.org/namespaces/tal"
      xmlns:i18n="http://xml.zope.org/namespaces/i18n"
      metal:use-macro="context/@@standard_macros/page">
  <body>
    <div metal:fill-slot="body">
      <form action="." tal:attributes="action request/URL" method="post"
            enctype="multipart/form-data">
        <div class="row">
          <div class="controls">
            <input type="submit" value="Make site" name="makesite"
                   i18n:attributes="value" tal:condition="not:realview/isSite" />
            <input type="submit" value="Unmake site" name="unmakesite"
                   i18n:attributes="value" tal:condition="realview/isSite" />
          </div>
        </div>
      </form>
    </div>
  </body>
</html>

""")


def manage_addPublication(
    self, id, title, create_default=1, policy_name='None', REQUEST=None):
    """Add a Silva publication."""
    if not mangle.Id(self, id).isValid():
        return
    publication = Publication(id)
    self._setObject(id, publication)
    publication = getattr(self, id)
    publication.set_title(title)
    if create_default:
        policy = self.service_containerpolicy.getPolicy(policy_name)
        policy.createDefaultDocument(publication, title)
    add_and_edit(self, id, REQUEST)
    return ''


